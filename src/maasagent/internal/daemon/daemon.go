// Copyright (c) 2026 Canonical Ltd
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

package daemon

import (
	"bytes"
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"net"
	"net/http"
	"net/http/pprof"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"github.com/spf13/afero"
	"go.opentelemetry.io/otel/exporters/prometheus"
	"go.opentelemetry.io/otel/metric"
	metricnoop "go.opentelemetry.io/otel/metric/noop"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
	semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
	"go.opentelemetry.io/otel/trace"
	tracenoop "go.opentelemetry.io/otel/trace/noop"
	"golang.org/x/sync/errgroup"
	"maas.io/core/src/maasagent/internal/atomicfile"
	"maas.io/core/src/maasagent/internal/certutil"
	"maas.io/core/src/maasagent/internal/client"
	"maas.io/core/src/maasagent/internal/pathutil"
	"maas.io/core/src/maasagent/internal/token"
)

type enroller interface {
	Enroll(ctx context.Context,
		req client.EnrollRequest) (*client.EnrollResponse, error)
}

type configurator interface {
	GetConfig(ctx context.Context, identity string) (*client.ConfigResponse, error)
}

type Daemon struct {
	fs afero.Fs

	enroller     func(*url.URL, *tls.Config) enroller
	configurator func(*url.URL, *tls.Config) configurator

	cert tls.Certificate

	cfg    *Config
	dynCfg *DynamicConfig

	tracerProvider trace.TracerProvider
	meterProvider  metric.MeterProvider

	mux    *http.ServeMux
	server *http.Server
}

func New() *Daemon {
	d := &Daemon{
		fs: afero.NewOsFs(),
		enroller: func(u *url.URL, tlsConfig *tls.Config) enroller {
			return client.New(u, tlsConfig)
		},
		configurator: func(u *url.URL, tlsConfig *tls.Config) configurator {
			return client.New(u, tlsConfig)
		},

		tracerProvider: tracenoop.NewTracerProvider(),
		meterProvider:  metricnoop.NewMeterProvider(),
		mux:            http.NewServeMux(),
	}

	return d
}

func (d *Daemon) id() (string, error) {
	if d.cert.Leaf == nil {
		return "", errors.New("missing id")
	}

	return d.cert.Leaf.Subject.CommonName, nil
}

type BootstrapOptions struct {
	Token      string
	ConfigFile string
	CacheDir   string
	CertDir    string
}

// Bootstrap configures the MAAS agent using the provided bootstrap token.
// It parses the token, generates identity (if needed), generates configuration
// and performs enrollment via provided controller.
// On success private key, certificates and configuration are saved to disk.
func (d *Daemon) Bootstrap(ctx context.Context, opts BootstrapOptions) (err error) {
	tok, err := token.ParseBootstrapToken(opts.Token)
	if err != nil {
		return fmt.Errorf("invalid bootstrap token: %w", err)
	}

	t := newTracker(d.fs)

	// Determine config path before writing it.
	t.trackNew(opts.ConfigFile)

	cfg, err := generateConfig(d.fs, opts.ConfigFile, configOptions{
		ControllerURL: tok.URL.String(),
		CacheDir:      opts.CacheDir,
		CertDir:       opts.CertDir,
	})
	if err != nil {
		return fmt.Errorf("config generation: %w", err)
	}

	// Determine cert paths from the config before we potentially create them.
	t.trackNew(cfg.TLS.KeyFile)
	t.trackNew(cfg.TLS.CertFile)
	t.trackNew(cfg.TLS.CAFile)

	defer func() { err = t.cleanup(err) }()

	id, err := generateIdentity(d.fs, cfg.TLS.CertFile, cfg.TLS.KeyFile)
	if err != nil {
		return fmt.Errorf("identity generation: %w", err)
	}

	enrollReq := client.EnrollRequest{
		Secret:    tok.Secret,
		AgentUUID: id.ID,
		CSR:       string(id.CSR),
	}

	enroller := d.enroller(tok.URL,
		client.NewTLSConfigWithFingerprintPinning(tok.Fingerprint))

	provisioned, err := enroller.Enroll(ctx, enrollReq)
	if err != nil {
		return fmt.Errorf("enrollment failed: %w", err)
	}

	if provisioned.Certificate != "" {
		if err := certutil.WriteCertificatePEM(d.fs, cfg.TLS.CertFile,
			[]byte(provisioned.Certificate)); err != nil {
			return fmt.Errorf("write certificate: %w", err)
		}
	}

	if err := certutil.WriteCertificatePEM(d.fs, cfg.TLS.CAFile,
		[]byte(provisioned.CA)); err != nil {
		return fmt.Errorf("write CA certificate: %w", err)
	}

	return nil
}

type DaemonArgs struct {
	ConfigFile string
	// TODO: Remove once Python based rackd is obsolete.
	// Right now it is used to determine if daemon was started by rackd.
	Supervised bool
}

// Start starts MAAS agent daemon with provided options.
// It will initialize all the services and communicate with MAAS controller to
// obtain other required parameters. Communication happens using mTLS.
func (d *Daemon) Start(ctx context.Context, args DaemonArgs) error {
	var err error

	g, ctx := errgroup.WithContext(ctx)

	d.cfg, err = loadConfig(d.fs, args.ConfigFile)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	d.setupLogger()

	if err := d.setupObservability(ctx); err != nil {
		return fmt.Errorf("configure observability: %w", err)
	}

	d.cert, err = certutil.LoadX509KeyPair(d.fs,
		d.cfg.TLS.CertFile, d.cfg.TLS.KeyFile)
	if err != nil {
		return fmt.Errorf("loading certificate: %w", err)
	}

	id, err := d.id()
	if err != nil {
		return err
	}

	caPool, err := certutil.LoadCAPool(d.fs, d.cfg.TLS.CAFile)
	if err != nil {
		return fmt.Errorf("loading ca: %w", err)
	}

	// TODO: We should validate FQDN/IP, not just CA validation.
	configurator := d.configurator(d.cfg.ControllerURL,
		client.NewTLSConfigWithCAValidationOnly(d.cert, caPool))

	dynCfg, err := configurator.GetConfig(ctx, id)
	if err != nil {
		return fmt.Errorf("fetching config: %w", err)
	}

	d.dynCfg = &DynamicConfig{
		Temporal: TemporalConfig{
			EncryptionKey: dynCfg.RPCSecret,
		},
		SystemID:  dynCfg.SystemID,
		RPCSecret: dynCfg.RPCSecret,
		MAASURL:   dynCfg.MAASURL,
	}

	// This is a temporary solution for backward compatibility.
	// This supports only "rackd" mode ("region" and "region+rack" are not covered).
	//  1. agent fetches dynamic configuration
	//  2. if configuration contains system_id -> start as normal
	//     system_id is generated by the rackd via RPC
	//  3. if system_id is empty -> init & start rackd
	//     write files necessary for rackd to start (secret, rackd.conf and etc.)
	//     it will start rackd, which would then start the agent
	// TODO: Remove once Python based rackd is obsolete.
	if !args.Supervised && dynCfg.SystemID == "" {
		if err := startRackd(d.fs, rackdConfig{
			AgentUUID: id,
			RPCSecret: dynCfg.RPCSecret,
			MAASURL:   dynCfg.MAASURL,
		}); err != nil {
			return fmt.Errorf("starting rackd: %w", err)
		}

		return nil
	}

	// Initialization of services is extracted, so it will be easier to apply
	// refactoring and changes to certain things which appeared to be not the
	// best design decision.
	if err := d.startServices(ctx, g); err != nil {
		return fmt.Errorf("starting services: %w", err)
	}

	g.Go(d.startHTTPServer)

	// TODO: Implement graceful shutdown in case of an error
	return g.Wait()
}

// startHTTPServer initializes and starts the daemon's HTTP server
// on a Unix domain socket. It unlinks any existing socket at the path
// and sets file permissions to 0660 to restrict access to the owner
// and the group. It will register all the handlers from daemon's mux.
// This call is blocking.
func (d *Daemon) startHTTPServer() error {
	socketPath := filepath.Join(pathutil.RunDir(), "agent-http.sock")

	if err := d.fs.Remove(socketPath); err != nil {
		if !errors.Is(err, os.ErrNotExist) {
			return fmt.Errorf("remove existing socket: %w", err)
		}
	}

	// TODO: consider listening on a ip:port once Python rackd is gone,
	// as it will be unlikely that nginx will be shipped as a dependency.
	listener, err := net.Listen("unix", socketPath)
	if err != nil {
		return fmt.Errorf("listen on unix socket: %w", err)
	}

	defer func() {
		if err != nil {
			//nolint:errcheck // TODO: log once logger is injected
			_ = listener.Close()
			//nolint:errcheck // TODO: log once logger is injected
			_ = d.fs.Remove(socketPath)
		}
	}()

	if err := d.fs.Chmod(socketPath, 0660); err != nil {
		return fmt.Errorf("chmod socket: %w", err)
	}

	d.server = &http.Server{
		Handler:           d.mux,
		ReadHeaderTimeout: 60 * time.Second,
	}

	return d.server.Serve(listener)
}

// setupLogger sets the global logger with the provided logLevel.
// If logLevel provided is unknown, then INFO will be used.
func (d *Daemon) setupLogger() {
	// Use custom ConsoleWriter without TimestampFieldName, because stdout
	// is captured with systemd-cat
	consoleWriter := zerolog.ConsoleWriter{Out: os.Stdout, NoColor: true}
	consoleWriter.PartsOrder = []string{
		zerolog.LevelFieldName,
		zerolog.CallerFieldName,
		zerolog.MessageFieldName,
	}

	log.Logger = zerolog.New(consoleWriter).With().Logger()

	ll, err := zerolog.ParseLevel(string(d.cfg.Observability.Logging.Level))
	if err != nil || ll == zerolog.NoLevel {
		ll = zerolog.InfoLevel
	}

	zerolog.SetGlobalLevel(ll)

	// TODO: switch to slog and return logger to inject as a dependency.

	log.Info().Msg(fmt.Sprintf("Logger is configured with log level %q", ll.String()))
}

// setupObservability initializes metrics, tracing, and profiling based on cfg.
func (d *Daemon) setupObservability(_ context.Context) error {
	if err := d.setupMetrics(); err != nil {
		return err
	}

	if err := d.setupProfiler(); err != nil {
		return err
	}

	return nil
}

// observabilityResource builds the OpenTelemetry resource for this agent.
func (d *Daemon) observabilityResource() (*resource.Resource, error) {
	return resource.Merge(resource.Default(),
		resource.NewWithAttributes(
			semconv.SchemaURL,
			semconv.ServiceName("maas.agent"),
			// semconv.ServiceVersion(version.Version()),
		),
	)
}

// setupMetrics configures the Prometheus exporter and registers /metrics.
func (d *Daemon) setupMetrics() error {
	if !d.cfg.Observability.Metrics.Enabled {
		return nil
	}

	exporter, err := prometheus.New()
	if err != nil {
		return fmt.Errorf("init metrics exporter: %w", err)
	}

	res, err := d.observabilityResource()
	if err != nil {
		return fmt.Errorf("init metrics resource: %w", err)
	}

	d.meterProvider = sdkmetric.NewMeterProvider(
		sdkmetric.WithResource(res),
		sdkmetric.WithReader(exporter),
	)

	d.mux.Handle("/metrics", promhttp.Handler())

	return nil
}

// setupProfiler registers pprof handlers when profiling is enabled.
func (d *Daemon) setupProfiler() error {
	if !d.cfg.Observability.Profiling.Enabled {
		return nil
	}

	d.mux.HandleFunc("/debug/pprof/", pprof.Index)
	d.mux.HandleFunc("/debug/pprof/cmdline", pprof.Cmdline)
	d.mux.HandleFunc("/debug/pprof/profile", pprof.Profile)
	d.mux.HandleFunc("/debug/pprof/symbol", pprof.Symbol)
	d.mux.HandleFunc("/debug/pprof/trace", pprof.Trace)

	return nil
}

// Stop gracefully shuts down the daemon.
func (d *Daemon) Stop(ctx context.Context) error {
	// TODO: All the services should be considered here.
	if d.server == nil {
		return nil
	}

	return d.server.Shutdown(ctx)
}

// newTracker creates a tracker that records which files are newly created
// during bootstrap. On failure, only those files will be cleaned up,
// preserving any user-provided files that already existed.
func newTracker(fs afero.Fs) *tracker {
	return &tracker{
		fs:      fs,
		written: make(map[string]struct{}),
	}
}

type tracker struct {
	fs      afero.Fs
	written map[string]struct{}
}

// trackNew records path as a candidate for cleanup if it does not already
// exist. Blank paths and paths that cannot be stat'd are silently ignored.
func (t *tracker) trackNew(path string) {
	if path == "" {
		return
	}

	ok, err := afero.Exists(t.fs, path)
	if err != nil {
		// If we can't determine existence, be conservative and don't delete it.
		return
	}

	if !ok {
		t.written[path] = struct{}{}
	}
}

// cleanup removes all tracked files and returns a combined error. It is a
// no-op when err is nil, so it is safe to call unconditionally in a defer.
func (t *tracker) cleanup(err error) error {
	if err == nil {
		return nil
	}

	var cleanupErr error
	for path := range t.written {
		cleanupErr = errors.Join(cleanupErr, t.fs.Remove(path))
	}

	if cleanupErr != nil {
		return errors.Join(err, fmt.Errorf("bootstrap cleanup: %w", cleanupErr))
	}

	return err
}

type rackdConfig struct {
	AgentUUID string
	RPCSecret string
	MAASURL   string
}

// startRackd implements functionality similar to `maas init rackd` command.
// This function would be no longer required once twisted RPC is gone,
// and rackd is no longer the supervisor of the agent.
// TODO: Remove once Python based rackd is obsolete.
func startRackd(fs afero.Fs, cfg rackdConfig) error {
	if err := writeRackdConfig(fs, cfg); err != nil {
		return err
	}

	if err := restartRackd(); err != nil {
		return err
	}

	return nil
}

// writeRackdConfig persists legacy configuration files (secret, agent_uuid
// and rackd.conf with specified maas_url parameter) required by rackd.
// If running as a snap, it sets the snap_mode to "rack".
// TODO: Remove once Python based rackd is obsolete.
func writeRackdConfig(fs afero.Fs, cfg rackdConfig) error {
	if common := filepath.Clean(os.Getenv("SNAP_COMMON")); common != "" {
		if err := atomicfile.WriteFileWithFs(fs, filepath.Join(common, "snap_mode"),
			[]byte("rack"), 0o640); err != nil {
			return fmt.Errorf("writing snap_mode: %w", err)
		}
	}

	commonDir := "/var/lib/maas"
	if dir := os.Getenv("SNAP_COMMON"); dir != "" {
		commonDir = filepath.Join(filepath.Clean(dir), "maas")
	}

	dataDir := "/etc/maas"
	if dir := os.Getenv("SNAP_DATA"); dir != "" {
		dataDir = filepath.Clean(dir)
	}

	configFiles := []struct {
		path string
		data []byte
		perm os.FileMode
	}{
		{
			path: filepath.Join(commonDir, "secret"),
			data: []byte(cfg.RPCSecret + "\n"),
			perm: 0o640,
		},
		{
			path: filepath.Join(commonDir, "agent_uuid"),
			data: []byte(cfg.AgentUUID + "\n"),
			perm: 0o640,
		},
		{
			path: filepath.Join(dataDir, "rackd.conf"),
			data: fmt.Appendf(nil, "maas_url: %s\n", cfg.MAASURL),
			perm: 0o644,
		},
	}

	for _, cf := range configFiles {
		if err := atomicfile.WriteFileWithFs(fs, cf.path, cf.data,
			cf.perm); err != nil {
			return fmt.Errorf("failed writing %s: %w", cf.path, err)
		}
	}

	return nil
}

// restartRackd transitions the system from the agent to the legacy rackd service.
//
// This method is intended for backward compatibility during the transition
// from rackd-supervised agents to standalone operation.
// TODO: Remove once Python based rackd is obsolete.
func restartRackd() error {
	if snap := os.Getenv("SNAP"); snap != "" {
		snap = filepath.Clean(snap)

		return runAll(
			exec.Command("snapctl", "stop", "maas.pebble"),
			//nolint:gosec // G204 previous .Clean and .Join should be enough
			exec.Command(filepath.Join(snap, "bin/reconfigure-pebble")),
			exec.Command("snapctl", "start", "maas.pebble"),
		)
	}

	return runAll(
		exec.Command("systemctl", "stop", "maas-rackd"),
		exec.Command("systemctl", "enable", "maas-rackd"),
		exec.Command("systemctl", "start", "maas-rackd"),
	)
}

// runAll executes a sequence of commands and stops at the first failure.
func runAll(cmds ...*exec.Cmd) error {
	for _, cmd := range cmds {
		if out, err := cmd.CombinedOutput(); err != nil {
			return fmt.Errorf("command %q failed: %s: %w", cmd.String(),
				string(bytes.TrimSpace(out)), err)
		}
	}

	return nil
}
