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
	"net/url"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/grpc-ecosystem/grpc-gateway/v2/runtime"
	openfgav1 "github.com/openfga/api/proto/openfga/v1"
	"github.com/openfga/openfga/pkg/logger"
	openfgaServer "github.com/openfga/openfga/pkg/server"
	"github.com/openfga/openfga/pkg/storage/postgres"
	"github.com/openfga/openfga/pkg/storage/sqlcommon"
	"gopkg.in/yaml.v3"

	"maas.io/core/src/maasopenfga/internal/vault"
)

const (
	defaultMaxOpenConns      = 3
	defaultMaxIdleConns      = 1
	defaultVaultSecretsMount = "secret"
)

type regionConfig struct {
	DatabaseHost        string `yaml:"database_host"`
	DatabaseName        string `yaml:"database_name"`
	DatabasePass        string `yaml:"database_pass"`
	DatabaseUser        string `yaml:"database_user"`
	OpenFGAMaxOpenConns int    `yaml:"openfga_max_open_conns"`
	OpenFGAMaxIdleConns int    `yaml:"openfga_max_idle_conns"`
	VaultURL            string `yaml:"vault_url"`
	VaultSecretsMount   string `yaml:"vault_secrets_mount"`
	VaultSecretsPath    string `yaml:"vault_secrets_path"`
	VaultApproleID      string `yaml:"vault_approle_id"`
	VaultSecretID       string `yaml:"vault_secret_id"`
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

	if regionCfg.VaultSecretsMount == "" {
		regionCfg.VaultSecretsMount = defaultVaultSecretsMount
	}

	return &regionCfg
}

// maasDataPath returns the path of a file under the MAAS data directory,
// mirroring maascommon.path.get_maas_data_path.
func maasDataPath(name string) string {
	dataDir := os.Getenv("MAAS_DATA")
	if dataDir == "" {
		dataDir = "/var/lib/maas"
	}

	return filepath.Join(dataDir, name)
}

// readMaasID returns the ID of this MAAS controller, as stored on disk by
// the region/rack controller.
func readMaasID() (string, error) {
	data, err := os.ReadFile(filepath.Clean(maasDataPath("maas_id")))
	if err != nil {
		return "", fmt.Errorf("failed to read MAAS ID: %w", err)
	}

	return strings.TrimSpace(string(data)), nil
}

// vaultDatabaseCredsPath returns the Vault KV v2 secrets engine path where
// database credentials are stored for this controller, mirroring
// maasserver.config.get_db_creds_vault_path.
func vaultDatabaseCredsPath(secretsPath, maasID string) string {
	return fmt.Sprintf("%s/controller/%s/database-creds", secretsPath, maasID)
}

// resolveDatabaseCredentials returns the database user, password and name to
// use to connect to the database. If Vault is configured in the region
// configuration, credentials are fetched from there; otherwise (or if Vault
// is unreachable, misconfigured, or does not hold DB credentials), the
// credentials from the region configuration file are used as a fallback.
//
// This mirrors maasapiserver.settings._get_default_db_config, so that
// OpenFGA can connect to the database when MAAS is configured to store DB
// credentials in Vault instead of regiond.conf.
func resolveDatabaseCredentials(ctx context.Context, cfg *regionConfig) (cfgUser, cfgPass, cfgName string) {
	cfgUser, cfgPass, cfgName = cfg.DatabaseUser, cfg.DatabasePass, cfg.DatabaseName

	if cfg.VaultURL == "" || cfg.VaultApproleID == "" || cfg.VaultSecretID == "" {
		// Vault is not configured, use the local configuration.
		return cfgUser, cfgPass, cfgName
	}

	maasID, err := readMaasID()
	if err != nil {
		log.Printf("unable to determine MAAS ID, using DB credentials from region configuration: %v", err)
		return cfgUser, cfgPass, cfgName
	}

	client := vault.NewClient(cfg.VaultURL)

	token, err := client.Login(ctx, cfg.VaultApproleID, cfg.VaultSecretID)
	if err != nil {
		log.Printf("unable to authenticate with Vault, using DB credentials from region configuration: %v", err)
		return cfgUser, cfgPass, cfgName
	}

	creds, err := client.ReadSecret(ctx, token, cfg.VaultSecretsMount, vaultDatabaseCredsPath(cfg.VaultSecretsPath, maasID))
	if err != nil {
		if errors.Is(err, vault.ErrNotFound) {
			// Vault does not have DB credentials, but is available. No need
			// to report anything, use local credentials.
			return cfgUser, cfgPass, cfgName
		}

		log.Printf("unable to fetch DB credentials from Vault, using DB credentials from region configuration: %v", err)

		return cfgUser, cfgPass, cfgName
	}

	return creds["user"], creds["pass"], creds["name"]
}

func getPostgresDSN(cfg *regionConfig, user, pass, name string) string {
	socketPath := url.QueryEscape(cfg.DatabaseHost)

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

	regionCfg := readRegionConfig()

	dbUser, dbPass, dbName := resolveDatabaseCredentials(ctx, regionCfg)

	psqlDataStore, err := postgres.New(
		getPostgresDSN(regionCfg, dbUser, dbPass, dbName),
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
