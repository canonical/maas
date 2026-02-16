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

type regionConfig struct {
	DatabaseHost        string `yaml:"database_host"`
	DatabaseName        string `yaml:"database_name"`
	DatabasePass        string `yaml:"database_pass"`
	DatabaseUser        string `yaml:"database_user"`
	OpenFGAMaxOpenConns int    `yaml:"openfga_max_open_conns"`
	OpenFGAMaxIdleConns int    `yaml:"openfga_max_idle_conns"`
}

func readRegionConfig() *regionConfig {
	configDir := os.Getenv("SNAP_DATA")
	if configDir == "" {
		// Deb installation
		configDir = "/etc/maas"
	}

	configPath := filepath.Join(configDir, "regiond.conf")

	cfg, err := os.ReadFile(filepath.Clean(configPath))
	if err != nil {
		log.Fatalf("failed to read region config file: %v", err)
	}

	var regionCfg regionConfig

	err = yaml.Unmarshal(cfg, &regionCfg)
	if err != nil {
		log.Fatalf("failed to parse region config file: %v", err)
	}

	if regionCfg.OpenFGAMaxOpenConns <= 0 {
		regionCfg.OpenFGAMaxOpenConns = defaultMaxOpenConns
	}

	if regionCfg.OpenFGAMaxIdleConns <= 0 {
		regionCfg.OpenFGAMaxIdleConns = defaultMaxIdleConns
	}

	return &regionCfg
}

func getPostgresDSN(cfg *regionConfig) string {
	socketPath := url.QueryEscape(cfg.DatabaseHost)

	return fmt.Sprintf(
		"postgres://%s:%s@/%s?host=%s&search_path=openfga",
		cfg.DatabaseUser,
		cfg.DatabasePass,
		cfg.DatabaseName,
		socketPath,
	)
}

// Tested in src/tests/e2e/test_openfga_integration.py
func main() {
	socketPath := os.Getenv("MAAS_OPENFGA_HTTP_SOCKET_PATH")

	if socketPath == "" {
		// Deb installation
		socketPath = "/var/lib/maas/openfga-http.sock"
	}

	err := os.Remove(socketPath)
	if err != nil && !os.IsNotExist(err) {
		log.Fatalf("failed to remove existing socket file: %v", err)
	}

	lis, err := net.Listen("unix", socketPath)
	if err != nil {
		log.Fatal(err)
	}

	regionCfg := readRegionConfig()

	psqlDataStore, err := postgres.New(
		getPostgresDSN(regionCfg),
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

	ctx := context.Background()
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

		err = os.Remove(socketPath)
		if err != nil && !os.IsNotExist(err) {
			log.Printf("failed to remove socket file: %v", err)
		}
	}()

	log.Printf("OpenFGA HTTP listening on unix://%s", socketPath)

	if err := httpServer.Serve(lis); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}
