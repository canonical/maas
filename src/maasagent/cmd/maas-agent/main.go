package main

/*
	Copyright 2023 Canonical Ltd.  This software is licensed under the
	GNU Affero General Public License version 3 (see the file LICENSE).
*/

import (
	"os"
	"os/signal"
	"syscall"

	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"go.temporal.io/sdk/client"
	"launchpad.net/maas/maas/src/maasagent/internal/workflow"
	wflog "launchpad.net/maas/maas/src/maasagent/internal/workflow/log"
)

func Run() int {
	zerolog.SetGlobalLevel(zerolog.InfoLevel)

	log.Logger = log.Output(zerolog.ConsoleWriter{Out: os.Stderr})

	if envLogLevel, ok := os.LookupEnv("LOG_LEVEL"); ok {
		if logLevel, err := zerolog.ParseLevel(envLogLevel); err != nil {
			log.Warn().Str("LOG_LEVEL", envLogLevel).Msg("Unknown log level, defaulting to INFO")
		} else {
			zerolog.SetGlobalLevel(logLevel)
		}
	}

	// TODO: add contextual fields to the global logger?
	log.Info().Msg("Starting MAAS Agent service")

	client, err := client.Dial(client.Options{
		// TODO: fetch from rack config?
		HostPort: "localhost:5271",
		Logger:   wflog.New(log.Logger),
	})

	if err != nil {
		log.Error().Err(err).Send()
		return 1
	}

	// TODO: init Data Encoder
	// TODO: read real systemID
	_, err = workflow.NewWorkerPool("systemID", client)

	if err != nil {
		log.Error().Err(err).Send()
		return 1
	}

	log.Info().Msg("Service MAAS Agent started")

	sigC := make(chan os.Signal, 2)

	signal.Notify(sigC, syscall.SIGTERM, syscall.SIGINT)

	<-sigC

	return 0
}

func main() {
	os.Exit(Run())
}
