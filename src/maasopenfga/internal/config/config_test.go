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

package config

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestReadRegionConfigAppliesDefaults(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("SNAP_DATA", dir)

	confPath := filepath.Join(dir, "regiond.conf")
	require.NoError(t, os.WriteFile(confPath, []byte(`
database_host: localhost
database_name: maasdb
database_user: maas
database_pass: secret
`), 0o600))

	cfg, err := ReadRegionConfig()
	require.NoError(t, err)

	assert.Equal(t, "localhost", cfg.DatabaseHost)
	assert.Equal(t, defaultMaxOpenConns, cfg.OpenFGAMaxOpenConns)
	assert.Equal(t, defaultMaxIdleConns, cfg.OpenFGAMaxIdleConns)
	assert.Equal(t, defaultVaultSecretsMount, cfg.VaultSecretsMount)
	assert.False(t, cfg.VaultEnabled())
}

func TestReadRegionConfigKeepsExplicitValues(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("SNAP_DATA", dir)

	confPath := filepath.Join(dir, "regiond.conf")
	require.NoError(t, os.WriteFile(confPath, []byte(`
openfga_max_open_conns: 7
openfga_max_idle_conns: 2
vault_url: http://vault:8200
vault_secrets_mount: custom-mount
vault_approle_id: role
vault_secret_id: secret
`), 0o600))

	cfg, err := ReadRegionConfig()
	require.NoError(t, err)

	assert.Equal(t, 7, cfg.OpenFGAMaxOpenConns)
	assert.Equal(t, 2, cfg.OpenFGAMaxIdleConns)
	assert.Equal(t, "custom-mount", cfg.VaultSecretsMount)
	assert.True(t, cfg.VaultEnabled())
}

func TestReadRegionConfigMissingFile(t *testing.T) {
	t.Setenv("SNAP_DATA", t.TempDir())

	_, err := ReadRegionConfig()
	require.Error(t, err)
}

func TestMaasID(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("MAAS_DATA", dir)

	require.NoError(t, os.WriteFile(filepath.Join(dir, "maas_id"), []byte("abc123\n"), 0o600))

	id, err := MaasID()
	require.NoError(t, err)
	assert.Equal(t, "abc123", id)
}

func TestMaasIDMissing(t *testing.T) {
	t.Setenv("MAAS_DATA", t.TempDir())

	_, err := MaasID()
	require.Error(t, err)
}
