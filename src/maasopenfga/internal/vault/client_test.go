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

package vault

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestLogin(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, "/v1/auth/approle/login", r.URL.Path)
		assert.Equal(t, http.MethodPost, r.Method)

		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"auth": {"client_token": "s.faketoken"}}`))
	}))
	defer server.Close()

	client := NewClient(server.URL)

	token, err := client.Login(context.Background(), "role-id", "secret-id")
	require.NoError(t, err)
	assert.Equal(t, "s.faketoken", token)
}

func TestLoginError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		_, _ = w.Write([]byte(`{"errors": ["invalid role or secret ID"]}`))
	}))
	defer server.Close()

	client := NewClient(server.URL)

	_, err := client.Login(context.Background(), "role-id", "secret-id")
	require.Error(t, err)
	assert.Contains(t, err.Error(), "invalid role or secret ID")
}

func TestReadSecret(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, "/v1/secret/data/controller/abc123/database-creds", r.URL.Path)
		assert.Equal(t, "sometoken", r.Header.Get("X-Vault-Token"))

		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"data": {"data": {"user": "u", "pass": "p", "name": "n"}}}`))
	}))
	defer server.Close()

	client := NewClient(server.URL)

	creds, err := client.ReadSecret(context.Background(), "sometoken", "secret", "controller/abc123/database-creds")
	require.NoError(t, err)
	assert.Equal(t, map[string]string{"user": "u", "pass": "p", "name": "n"}, creds)
}

func TestReadSecretNotFound(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	}))
	defer server.Close()

	client := NewClient(server.URL)

	_, err := client.ReadSecret(context.Background(), "sometoken", "secret", "controller/abc123/database-creds")
	require.Error(t, err)
	assert.True(t, errors.Is(err, ErrNotFound))
}
