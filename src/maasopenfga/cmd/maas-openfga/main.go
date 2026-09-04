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
	"errors"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/grpc-ecosystem/grpc-gateway/v2/runtime"
	openfgav1 "github.com/openfga/api/proto/openfga/v1"
	"github.com/openfga/openfga/pkg/logger"
	openfgaServer "github.com/openfga/openfga/pkg/server"
	"github.com/openfga/openfga/pkg/storage/postgres"
	"github.com/openfga/openfga/pkg/storage/sqlcommon"
	"gopkg.in/yaml.v3"
)

const (
	defaultMaxOpenConns = 3
	defaultMaxIdleConns = 1
)

type openfgaConfig struct {
	DatabaseURI         string `yaml:"database_uri"`
	OpenFGAMaxOpenConns int    `yaml:"openfga_max_open_conns"`
	OpenFGAMaxIdleConns int    `yaml:"openfga_max_idle_conns"`
}

func readOpenFGAConfig() (openfgaConfig, error) {
	configPath := os.Getenv("MAAS_OPENFGA_CONFIG")
	if configPath == "" {
		return openfgaConfig{}, errors.New("MAAS_OPENFGA_CONFIG environment variable is not set")
	}

	cfg, err := os.ReadFile(filepath.Clean(configPath))
	if err != nil {
		return openfgaConfig{}, fmt.Errorf("failed to read openfga config file: %w", err)
	}

	var openfgaCfg openfgaConfig
	if err := yaml.Unmarshal(cfg, &openfgaCfg); err != nil {
		return openfgaConfig{}, fmt.Errorf("failed to parse openfga config file: %w", err)
	}

	if openfgaCfg.DatabaseURI == "" {
		return openfgaConfig{}, errors.New("database_uri is not set in openfga config file")
	}

	if openfgaCfg.OpenFGAMaxOpenConns <= 0 {
		openfgaCfg.OpenFGAMaxOpenConns = defaultMaxOpenConns
	}

	if openfgaCfg.OpenFGAMaxIdleConns <= 0 {
		openfgaCfg.OpenFGAMaxIdleConns = defaultMaxIdleConns
	}

	return openfgaCfg, nil
}

// Tested in src/tests/e2e/test_openfga_integration.py
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

	openfgaCfg, err := readOpenFGAConfig()
	if err != nil {
		log.Fatal(err)
	}

	psqlDataStore, err := postgres.New(
		openfgaCfg.DatabaseURI,
		sqlcommon.NewConfig(
			sqlcommon.WithMaxOpenConns(openfgaCfg.OpenFGAMaxOpenConns),
			sqlcommon.WithMaxIdleConns(openfgaCfg.OpenFGAMaxIdleConns),
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
