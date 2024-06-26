// Copyright (c) 2023-2024 Canonical Ltd
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

package main

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	backoff "github.com/cenkalti/backoff/v4"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/converter"
	"gopkg.in/yaml.v3"

	"maas.io/core/src/maasagent/internal/cache"
	"maas.io/core/src/maasagent/internal/httpproxy"
	"maas.io/core/src/maasagent/internal/power"
	wflog "maas.io/core/src/maasagent/internal/workflow/log"
	"maas.io/core/src/maasagent/internal/workflow/worker"
	"maas.io/core/src/maasagent/pkg/workflow/codec"
)

const (
	TemporalPort = 5271
)

// config represents a necessary set of configuration options for MAAS Agent
type config struct {
	MAASUUID  string `yaml:"maas_uuid"`
	SystemID  string `yaml:"system_id"`
	Secret    string `yaml:"secret"`
	LogLevel  string `yaml:"log_level"`
	HTTPProxy struct {
		CacheDir  string `yaml:"cache_dir"`
		CacheSize int64  `yaml:"cache_size"`
	} `yaml:"httpproxy"`
	Controllers []string `yaml:"controllers,flow"`
}

func Run() int {
	// Use custom ConsoleWriter without TimestampFieldName, because stdout
	// is captured with systemd-cat
	// TODO: write directly to the journal
	consoleWriter := zerolog.ConsoleWriter{Out: os.Stdout, NoColor: true}
	consoleWriter.PartsOrder = []string{
		zerolog.LevelFieldName,
		zerolog.CallerFieldName,
		zerolog.MessageFieldName,
	}

	log.Logger = zerolog.New(consoleWriter).With().Logger()

	cfg, err := getConfig()
	if err != nil {
		log.Error().Err(err).Send()
		return 1
	}

	// Encryption Codec required for Temporal Workflow's payload encoding
	codec, err := codec.NewEncryptionCodec([]byte(cfg.Secret))
	if err != nil {
		log.Error().Err(err).Msg("Encryption codec setup failed")
		return 1
	}

	var logLevel zerolog.Level

	logLevel, err = zerolog.ParseLevel(cfg.LogLevel)
	if err != nil || logLevel == zerolog.NoLevel {
		logLevel = zerolog.InfoLevel
	}

	zerolog.SetGlobalLevel(logLevel)

	log.Info().Msg(fmt.Sprintf("Logger is configured with log level %q", logLevel.String()))

	clientBackoff := backoff.NewExponentialBackOff()
	clientBackoff.MaxElapsedTime = 60 * time.Second

	certsDir := getCertificatesDir()

	cert, err := tls.LoadX509KeyPair(fmt.Sprintf("%s/cluster.pem", certsDir), fmt.Sprintf("%s/cluster.key", certsDir))
	if err != nil {
		log.Error().Err(err).Msg("Failed loading client cert and key")
	}

	ca := x509.NewCertPool()

	b, err := os.ReadFile(fmt.Sprintf("%s/cacerts.pem", certsDir))
	if err != nil {
		log.Error().Err(err).Msg("Failed reading CA")
	} else if !ca.AppendCertsFromPEM(b) {
		log.Error().Err(err).Msg("CA PEM file is invalid")
	}

	temporalClient, err := backoff.RetryWithData(
		func() (client.Client, error) {
			return client.Dial(client.Options{
				// TODO: fallback retry if Controllers[0] is unavailable
				HostPort: fmt.Sprintf("%s:%d", cfg.Controllers[0], TemporalPort),
				Identity: fmt.Sprintf("%s@agent:%d", cfg.SystemID, os.Getpid()),
				Logger:   wflog.NewZerologAdapter(log.Logger),
				DataConverter: converter.NewCodecDataConverter(
					converter.GetDefaultDataConverter(),
					codec,
				),
				ConnectionOptions: client.ConnectionOptions{
					TLS: &tls.Config{
						MinVersion:   tls.VersionTLS12,
						Certificates: []tls.Certificate{cert},
						RootCAs:      ca,
						ServerName:   "maas",
					},
				},
			})
		}, clientBackoff,
	)

	if err != nil {
		log.Error().Err(err).Msg("Temporal client error")
		return 1
	}

	var workerPool worker.WorkerPool

	cache, err := cache.NewFileCache(cfg.HTTPProxy.CacheSize, cfg.HTTPProxy.CacheDir)
	if err != nil {
		log.Error().Err(err).Msg("HTTP Proxy cache initialisation error")
		return 1
	}

	runDir := getRunDir()

	_, err = os.Stat(runDir)
	if os.IsNotExist(err) {
		err = os.Mkdir(runDir, os.ModeDir|0755)
	}

	if err != nil {
		log.Error().Err(err).Send()
		return 1
	}

	powerService := power.NewPowerService(cfg.SystemID, &workerPool)
	httpProxyService := httpproxy.NewHTTPProxyService(runDir, cache)

	workerPool = *worker.NewWorkerPool(cfg.SystemID, temporalClient,
		worker.WithMainWorkerTaskQueueSuffix("agent:main"),
		worker.WithConfigurator(powerService),
		worker.WithConfigurator(httpProxyService),
	)

	workerPoolBackoff := backoff.NewExponentialBackOff()
	workerPoolBackoff.MaxElapsedTime = 60 * time.Second

	err = backoff.Retry(workerPool.Start, workerPoolBackoff)
	if err != nil {
		log.Error().Err(err).Msg("Temporal worker pool failure")
		return 1
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// NOTE: Signal Region Controller that Agent has started.
	// This should trigger configuration workflows execution.
	// Region controller will start configuration workflows based on certain
	// events, however this explicit call from the Agent is used to cover
	// situations when Agent is (re)started and has a clean state.
	// Once Region can detect that Agent was reconnected or restarted via
	// Temporal server API, we should no longer need this.
	type configureAgentParam struct {
		SystemID string `json:"system_id"`
	}

	workflowOptions := client.StartWorkflowOptions{
		TaskQueue: "region",
		// If we failed to execute this workflow in 120 seconds, then something bad
		// happened and we don't want to keep it in a task queue.
		WorkflowExecutionTimeout: 120 * time.Second,
	}

	workflowRun, err := temporalClient.ExecuteWorkflow(ctx, workflowOptions,
		"configure-agent", configureAgentParam{SystemID: cfg.SystemID},
	)

	if err != nil {
		log.Err(err).Msg("Failed to execute configure-agent workflow")
		return 1
	}

	if err := workflowRun.Get(ctx, nil); err != nil {
		log.Err(err).Msg("Workflow configure-agent failed")
		return 1
	}

	fatal := make(chan error)

	go func() {
		fatal <- workerPool.Error()
	}()

	go func() {
		fatal <- httpProxyService.Error()
	}()

	log.Info().Msg("Service MAAS Agent started")

	sigs := make(chan os.Signal, 2)

	signal.Notify(sigs, syscall.SIGTERM, syscall.SIGHUP)

	select {
	case err := <-fatal:
		log.Err(err).Msg("Service failure")
		return 1
	case <-sigs:
		return 0
	}
}

// getConfig reads MAAS Agent YAML configuration file
// NOTE: agent.yaml config is generated by rackd, however this behaviour
// should be changed when MAAS Agent will be a standalone service, not managed
// by the Rack Controller.
func getConfig() (*config, error) {
	fname := os.Getenv("MAAS_AGENT_CONFIG")
	if fname == "" {
		fname = "/etc/maas/agent.yaml"
	}

	data, err := os.ReadFile(filepath.Clean(fname))
	if err != nil {
		return nil, fmt.Errorf("configuration error: %w", err)
	}

	cfg := &config{}

	err = yaml.Unmarshal([]byte(data), cfg)
	if err != nil {
		return nil, fmt.Errorf("configuration error: %w", err)
	}

	return cfg, nil
}

func getRunDir() string {
	name := os.Getenv("SNAP_INSTANCE_NAME")

	if name != "" {
		return fmt.Sprintf("/run/snap.%s", name)
	}

	return "/run/maas"
}

func getCertificatesDir() string {
	dataDir := os.Getenv("SNAP_DATA")

	if dataDir != "" {
		return fmt.Sprintf("%s/certificates", dataDir)
	}

	return "/var/lib/maas/certificates"
}

func main() {
	os.Exit(Run())
}
