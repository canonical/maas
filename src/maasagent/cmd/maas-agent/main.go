package main

/*
	Copyright 2023 Canonical Ltd.  This software is licensed under the
	GNU Affero General Public License version 3 (see the file LICENSE).
*/

import (
	"context"
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
	"golang.org/x/sync/errgroup"
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

	powerService := power.NewPowerService(cfg.SystemID, &workerPool)
	httpProxyService := httpproxy.NewHTTPProxyService(getSocketDir(), cache)

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

	// TODO: consider using returned context
	errGroup, _ := errgroup.WithContext(ctx)

	errGroup.Go(func() error {
		return <-workerPool.Error()
	})

	errGroup.Go(func() error {
		return <-httpProxyService.Error()
	})

	log.Info().Msg("Service MAAS Agent started")

	sigC := make(chan os.Signal, 2)

	signal.Notify(sigC, syscall.SIGTERM, syscall.SIGINT)

	groupErrors := make(chan error)

	go func() {
		groupErrors <- errGroup.Wait()
	}()

	select {
	case err := <-groupErrors:
		log.Err(err).Msg("a service failed to execute")
		return 1
	case <-sigC:
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

func getSocketDir() string {
	name := os.Getenv("SNAP_INSTANCE_NAME")

	if name != "" {
		return fmt.Sprintf("/run/snap.%s", name)
	}

	return "/run/maas"
}

func main() {
	os.Exit(Run())
}
