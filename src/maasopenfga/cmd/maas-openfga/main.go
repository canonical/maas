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

package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/grpc-ecosystem/grpc-gateway/v2/runtime"
	openfgav1 "github.com/openfga/api/proto/openfga/v1"
	"github.com/openfga/openfga/pkg/logger"
	openfgaServer "github.com/openfga/openfga/pkg/server"
	"github.com/openfga/openfga/pkg/storage/postgres"
	"github.com/openfga/openfga/pkg/storage/sqlcommon"

	"maas.io/core/src/maasopenfga/internal/config"
	"maas.io/core/src/maasopenfga/internal/dbcredentials"
)

func getPostgresDSN(dbHost, user, pass, name string) string {
	socketPath := url.QueryEscape(dbHost)

	return fmt.Sprintf(
		"postgres://%s:%s@/%s?host=%s&search_path=openfga",
		user,
		pass,
		name,
		socketPath,
	)
}

func main() {
	socketPath := os.Getenv("MAAS_OPENFGA_HTTP_SOCKET_PATH")

	if socketPath == "" {
		// Deb installation
		socketPath = "/var/lib/maas/openfga-http.sock"
	}

	//nolint:gosec // G703: we allow custom socket path being specified
	err := os.Remove(socketPath)
	if err != nil && !os.IsNotExist(err) {
		log.Fatalf("failed to remove existing socket file: %v", err)
	}

	// TODO: implement proper graceful shutdown
	ctx := context.Background()

	lc := net.ListenConfig{}

	lis, err := lc.Listen(ctx, "unix", socketPath)
	if err != nil {
		log.Fatal(err)
	}

	regionCfg, err := config.ReadRegionConfig()
	if err != nil {
		log.Fatalf("failed to read region configuration: %v", err)
	}

	dbCreds := dbcredentials.Resolve(ctx, regionCfg)

	psqlDataStore, err := postgres.New(
		getPostgresDSN(regionCfg.DatabaseHost, dbCreds.User, dbCreds.Pass, dbCreds.Name),
		sqlcommon.NewConfig(
			sqlcommon.WithMaxOpenConns(regionCfg.OpenFGAMaxOpenConns),
			sqlcommon.WithMaxIdleConns(regionCfg.OpenFGAMaxIdleConns),
		),
	)
	if err != nil {
		log.Fatalf("failed to create postgres datastore: %v", err)
	}

	openfgaLogger, err := logger.NewLogger(logger.WithFormat("json"))
	if err != nil {
		panic(err)
	}

	opts := []openfgaServer.OpenFGAServiceV1Option{
		// TODO: investigate if we need to set some specific options
		openfgaServer.WithDatastore(psqlDataStore),
		openfgaServer.WithLogger(openfgaLogger),
	}

	fgaSvc, err := openfgaServer.NewServerWithOpts(opts...)
	if err != nil {
		log.Fatal(err)
	}

	mux := runtime.NewServeMux()

	if err = openfgav1.RegisterOpenFGAServiceHandlerServer(
		ctx,
		mux,
		fgaSvc,
	); err != nil {
		log.Fatal(err)
	}

	httpServer := &http.Server{
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, os.Interrupt, syscall.SIGTERM)

	go func() {
		<-sig
		log.Println("shutting down")

		err = httpServer.Close()
		if err != nil {
			log.Printf("failed to shutdown HTTP server: %v", err)
		}

		//nolint:gosec // G703: we allow custom socket path being specified
		err = os.Remove(socketPath)
		if err != nil && !os.IsNotExist(err) {
			log.Printf("failed to remove socket file: %v", err)
		}
	}()

	//nolint:gosec // G706 if socketPath was okay to init the listener, it's fine
	log.Printf("OpenFGA HTTP listening on socket %q", socketPath)

	if err := httpServer.Serve(lis); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}
