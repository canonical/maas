// Copyright (c) 2025-2026 Canonical Ltd
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
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"golang.org/x/sync/errgroup"

	"maas.io/core/src/maasagent/internal/cli"
)

func main() {
	ctx := context.Background()

	ctx, stop := signal.NotifyContext(ctx, os.Interrupt, syscall.SIGTERM)
	defer stop()

	cmd := cli.RootCmd(ctx)
	g, ctx := errgroup.WithContext(ctx)
	g.Go(func() error { return cmd.ExecuteContext(ctx) })

	err := g.Wait()
	if err != nil && err == context.Canceled {
		return
	}

	if err != nil {
		// TODO: replace global logger with the custom one
		slog.Error("command failed", "error", err)
		stop()
		os.Exit(1) //nolint:gocritic // exitAfterDefer: stop() is called here
	}
}
