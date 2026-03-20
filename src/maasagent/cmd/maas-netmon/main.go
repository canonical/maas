// Copyright (c) 2023-2026 Canonical Ltd
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
	"encoding/json"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"golang.org/x/sync/errgroup"

	"maas.io/core/src/maasagent/internal/logger"
	"maas.io/core/src/maasagent/internal/netmon"
)

func Run() int {
	l := initLogger()

	if len(os.Args) < 2 {
		l.Error("Please provide an interface to monitor")
		return 2
	}

	iface := os.Args[1]

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigC := make(chan os.Signal, 2)
	signal.Notify(sigC, syscall.SIGTERM, syscall.SIGINT)

	resultC := make(chan netmon.Result)

	g, ctx := errgroup.WithContext(ctx)
	g.SetLimit(2)

	svc := netmon.NewService(iface, netmon.WithLogger(l))

	g.Go(func() error {
		return svc.Start(ctx, resultC)
	})

	g.Go(func() error {
		encoder := json.NewEncoder(os.Stdout)

		for {
			select {
			case <-sigC:
				cancel()
				return nil
			case res, ok := <-resultC:
				if !ok {
					l.Debug("Result channel has been closed")
					return nil
				}

				err := encoder.Encode(res)
				if err != nil {
					return err
				}
			}
		}
	})

	l.Info("Service netmon started")

	if err := g.Wait(); err != nil {
		l.Error("Network minutor failure", slog.Any("error", err))
		return 1
	}

	return 0
}

func main() {
	os.Exit(Run())
}

func initLogger() *slog.Logger {
	level := os.Getenv("LOG_LEVEL")

	slevel := logger.ParseLevel(level)

	opts := &slog.HandlerOptions{
		Level: slevel,
	}

	handler := slog.NewTextHandler(os.Stderr, opts)

	logger := slog.New(handler)

	return logger
}
