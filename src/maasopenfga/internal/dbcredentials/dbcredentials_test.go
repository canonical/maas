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

package dbcredentials

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"maas.io/core/src/maasopenfga/internal/config"
)

func TestResolveVaultNotConfiguredUsesLocalCreds(t *testing.T) {
	cfg := &config.RegionConfig{
		DatabaseUser: "local-user",
		DatabasePass: "local-pass",
		DatabaseName: "local-name",
	}

	creds := Resolve(context.Background(), cfg)

	assert.Equal(t, Credentials{User: "local-user", Pass: "local-pass", Name: "local-name"}, creds)
}

func TestResolveVaultSuccessOverridesLocalCreds(t *testing.T) {
	dataDir := t.TempDir()
	t.Setenv("MAAS_DATA", dataDir)
	require.NoError(t, os.WriteFile(filepath.Join(dataDir, "maas_id"), []byte("abc123"), 0o600))

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		switch r.URL.Path {
		case "/v1/auth/approle/login":
			_, _ = w.Write([]byte(`{"auth": {"client_token": "s.faketoken"}}`))
		case "/v1/secret/data/prefix/controller/abc123/database-creds":
			assert.Equal(t, "s.faketoken", r.Header.Get("X-Vault-Token"))
			_, _ = w.Write([]byte(`{"data": {"data": {"user": "vault-user", "pass": "vault-pass", "name": "vault-name"}}}`))
		default:
			t.Fatalf("unexpected request to %s", r.URL.Path)
		}
	}))
	defer server.Close()

	cfg := &config.RegionConfig{
		DatabaseUser:      "local-user",
		DatabasePass:      "local-pass",
		DatabaseName:      "local-name",
		VaultURL:          server.URL,
		VaultSecretsMount: "secret",
		VaultSecretsPath:  "prefix",
		VaultApproleID:    "role-id",
		VaultSecretID:     "secret-id",
	}

	creds := Resolve(context.Background(), cfg)

	assert.Equal(t, Credentials{User: "vault-user", Pass: "vault-pass", Name: "vault-name"}, creds)
}

func TestResolveVaultLoginFailureFallsBackToLocalCreds(t *testing.T) {
	dataDir := t.TempDir()
	t.Setenv("MAAS_DATA", dataDir)
	require.NoError(t, os.WriteFile(filepath.Join(dataDir, "maas_id"), []byte("abc123"), 0o600))

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		_, _ = w.Write([]byte(`{"errors": ["invalid role or secret ID"]}`))
	}))
	defer server.Close()

	cfg := &config.RegionConfig{
		DatabaseUser:      "local-user",
		DatabasePass:      "local-pass",
		DatabaseName:      "local-name",
		VaultURL:          server.URL,
		VaultSecretsMount: "secret",
		VaultSecretsPath:  "prefix",
		VaultApproleID:    "role-id",
		VaultSecretID:     "secret-id",
	}

	creds := Resolve(context.Background(), cfg)

	assert.Equal(t, Credentials{User: "local-user", Pass: "local-pass", Name: "local-name"}, creds)
}

func TestResolveVaultSecretNotFoundFallsBackToLocalCreds(t *testing.T) {
	dataDir := t.TempDir()
	t.Setenv("MAAS_DATA", dataDir)
	require.NoError(t, os.WriteFile(filepath.Join(dataDir, "maas_id"), []byte("abc123"), 0o600))

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/v1/auth/approle/login":
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"auth": {"client_token": "s.faketoken"}}`))
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	defer server.Close()

	cfg := &config.RegionConfig{
		DatabaseUser:      "local-user",
		DatabasePass:      "local-pass",
		DatabaseName:      "local-name",
		VaultURL:          server.URL,
		VaultSecretsMount: "secret",
		VaultSecretsPath:  "prefix",
		VaultApproleID:    "role-id",
		VaultSecretID:     "secret-id",
	}

	creds := Resolve(context.Background(), cfg)

	assert.Equal(t, Credentials{User: "local-user", Pass: "local-pass", Name: "local-name"}, creds)
}

func TestResolveMissingMaasIDFallsBackToLocalCreds(t *testing.T) {
	t.Setenv("MAAS_DATA", t.TempDir())

	cfg := &config.RegionConfig{
		DatabaseUser:   "local-user",
		DatabasePass:   "local-pass",
		DatabaseName:   "local-name",
		VaultURL:       "http://unused",
		VaultApproleID: "role-id",
		VaultSecretID:  "secret-id",
	}

	creds := Resolve(context.Background(), cfg)

	assert.Equal(t, Credentials{User: "local-user", Pass: "local-pass", Name: "local-name"}, creds)
}
