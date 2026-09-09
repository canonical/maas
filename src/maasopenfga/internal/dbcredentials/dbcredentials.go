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

// Package dbcredentials resolves the database credentials that the OpenFGA
// wrapper should use to connect to Postgres, preferring credentials stored
// in Vault (when configured) over those in the local region configuration
// file.
//
// This mirrors maasapiserver.settings._get_default_db_config, so that
// OpenFGA can connect to the database when MAAS is configured to store DB
// credentials in Vault instead of regiond.conf.
package dbcredentials

import (
	"context"
	"errors"
	"log"
	"path"

	"maas.io/core/src/maasopenfga/internal/config"
	"maas.io/core/src/maasopenfga/internal/vault"
)

// Credentials holds the database user, password and name to connect with.
type Credentials struct {
	User string
	Pass string
	Name string
}

// Resolve returns the database credentials to use. If Vault is configured
// in the region configuration, credentials are fetched from there;
// otherwise (or if Vault is unreachable, misconfigured, or does not hold DB
// credentials), the credentials from the region configuration file are used
// as a fallback.
func Resolve(ctx context.Context, cfg *config.RegionConfig) Credentials {
	local := Credentials{
		User: cfg.DatabaseUser,
		Pass: cfg.DatabasePass,
		Name: cfg.DatabaseName,
	}

	if !cfg.VaultEnabled() {
		return local
	}

	maasID, err := config.MaasID()
	if err != nil {
		log.Printf("unable to determine MAAS ID, using DB credentials from region configuration: %v", err)
		return local
	}

	client := vault.NewClient(cfg.VaultURL)

	token, err := client.Login(ctx, cfg.VaultApproleID, cfg.VaultSecretID)
	if err != nil {
		log.Printf("unable to authenticate with Vault, using DB credentials from region configuration: %v", err)
		return local
	}

	creds, err := client.ReadSecret(ctx, token, cfg.VaultSecretsMount, credentialsPath(cfg.VaultSecretsPath, maasID))
	if err != nil {
		if errors.Is(err, vault.ErrNotFound) {
			// Vault does not have DB credentials, but is available. No need
			// to report anything, use local credentials.
			return local
		}

		log.Printf("unable to fetch DB credentials from Vault, using DB credentials from region configuration: %v", err)

		return local
	}

	return Credentials{
		User: creds["user"],
		Pass: creds["pass"],
		Name: creds["name"],
	}
}

// credentialsPath returns the Vault KV v2 secrets engine path where
// database credentials are stored for a given controller, mirroring
// maasserver.config.get_db_creds_vault_path.
func credentialsPath(secretsBasePath, maasID string) string {
	return path.Join(secretsBasePath, "controller", maasID, "database-creds")
}
