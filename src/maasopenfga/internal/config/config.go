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

// Package config provides access to the region controller's local
// configuration (regiond.conf) and other on-disk state under the MAAS data
// directory (e.g. the controller's MAAS ID).
package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"gopkg.in/yaml.v3"
)

const (
	defaultMaxOpenConns      = 3
	defaultMaxIdleConns      = 1
	defaultVaultSecretsMount = "secret"
)

// RegionConfig holds the subset of regiond.conf settings needed by the
// OpenFGA wrapper.
type RegionConfig struct {
	DatabaseHost        string `yaml:"database_host"`
	DatabaseName        string `yaml:"database_name"`
	DatabasePass        string `yaml:"database_pass"`
	DatabaseUser        string `yaml:"database_user"`
	VaultURL            string `yaml:"vault_url"`
	VaultSecretsMount   string `yaml:"vault_secrets_mount"`
	VaultSecretsPath    string `yaml:"vault_secrets_path"`
	VaultApproleID      string `yaml:"vault_approle_id"`
	VaultSecretID       string `yaml:"vault_secret_id"`
	OpenFGAMaxOpenConns int    `yaml:"openfga_max_open_conns"`
	OpenFGAMaxIdleConns int    `yaml:"openfga_max_idle_conns"`
}

// VaultEnabled reports whether enough Vault settings are present in the
// region configuration to attempt fetching secrets from it, mirroring the
// check in maasservicelayer.vault.manager.get_region_vault_manager.
func (c *RegionConfig) VaultEnabled() bool {
	return c.VaultURL != "" && c.VaultApproleID != "" && c.VaultSecretID != ""
}

// ReadRegionConfig reads and parses regiond.conf, applying the same
// defaults as the Python region configuration (RegionConfiguration).
func ReadRegionConfig() (*RegionConfig, error) {
	configDir := os.Getenv("SNAP_DATA")
	if configDir == "" {
		// Deb installation
		configDir = "/etc/maas"
	}

	configPath := filepath.Join(configDir, "regiond.conf")

	data, err := os.ReadFile(filepath.Clean(configPath))
	if err != nil {
		return nil, fmt.Errorf("failed to read region config file: %w", err)
	}

	var cfg RegionConfig

	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("failed to parse region config file: %w", err)
	}

	if cfg.OpenFGAMaxOpenConns <= 0 {
		cfg.OpenFGAMaxOpenConns = defaultMaxOpenConns
	}

	if cfg.OpenFGAMaxIdleConns <= 0 {
		cfg.OpenFGAMaxIdleConns = defaultMaxIdleConns
	}

	if cfg.VaultSecretsMount == "" {
		cfg.VaultSecretsMount = defaultVaultSecretsMount
	}

	return &cfg, nil
}

// DataPath returns the path of a file under the MAAS data directory,
// mirroring maascommon.path.get_maas_data_path.
func DataPath(name string) string {
	dataDir := os.Getenv("MAAS_DATA")
	if dataDir == "" {
		dataDir = "/var/lib/maas"
	}

	return filepath.Join(dataDir, name)
}

// MaasID returns the ID of this MAAS controller, as stored on disk by the
// region/rack controller, mirroring provisioningserver.utils.env.MAAS_ID.
func MaasID() (string, error) {
	data, err := os.ReadFile(filepath.Clean(DataPath("maas_id")))
	if err != nil {
		return "", fmt.Errorf("failed to read MAAS ID: %w", err)
	}

	return strings.TrimSpace(string(data)), nil
}
