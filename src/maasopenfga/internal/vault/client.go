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

// Package vault provides a minimal HashiCorp Vault client, supporting only
// the operations needed to authenticate via AppRole and read secrets from a
// KV v2 secrets engine. It mirrors the behaviour of
// maasservicelayer.vault.api.apiclient.AsyncVaultApiClient.
package vault

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// ErrNotFound is returned when the requested secret path does not exist in
// Vault.
var ErrNotFound = errors.New("vault: secret not found")

// Client is a minimal Vault HTTP API client.
type Client struct {
	httpClient *http.Client
	baseURL    string
}

// NewClient returns a new Vault client pointing at baseURL.
func NewClient(baseURL string) *Client {
	return &Client{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

type appRoleLoginRequest struct {
	RoleID   string `json:"role_id"`
	SecretID string `json:"secret_id"`
}

type appRoleLoginResponse struct {
	Auth struct {
		ClientToken string `json:"client_token"`
	} `json:"auth"`
}

// Login authenticates against Vault using the AppRole auth method and
// returns a client token that can be used for subsequent requests.
func (c *Client) Login(ctx context.Context, roleID, secretID string) (string, error) {
	body, err := json.Marshal(appRoleLoginRequest{RoleID: roleID, SecretID: secretID})
	if err != nil {
		return "", fmt.Errorf("failed to marshal login request: %w", err)
	}

	endpoint, err := url.JoinPath(c.baseURL, "v1", "auth", "approle", "login")
	if err != nil {
		return "", fmt.Errorf("failed to build login url: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		return "", fmt.Errorf("failed to build login request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed to reach vault: %w", err)
	}

	defer func() {
		if err := resp.Body.Close(); err != nil {
			log.Printf("failed to close response body: %v", err)
		}
	}()

	if err := raiseForStatus(resp); err != nil {
		return "", err
	}

	var loginResp appRoleLoginResponse
	if err := json.NewDecoder(resp.Body).Decode(&loginResp); err != nil {
		return "", fmt.Errorf("failed to decode login response: %w", err)
	}

	if loginResp.Auth.ClientToken == "" {
		return "", errors.New("vault: login response did not contain a client token")
	}

	return loginResp.Auth.ClientToken, nil
}

// This is an awkward data model, but the nested "data" key is the actual Vault response.
type kvV2ReadResponse struct {
	Data struct {
		Data map[string]string `json:"data"`
	} `json:"data"`
}

// ReadSecret reads a secret from the given path in a KV v2 secrets engine
// mounted at mount, authenticating with token.
func (c *Client) ReadSecret(ctx context.Context, token, mount, path string) (map[string]string, error) {
	endpoint, err := url.JoinPath(c.baseURL, "v1", mount, "data", path)
	if err != nil {
		return nil, fmt.Errorf("failed to build read secret url: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to build read secret request: %w", err)
	}

	req.Header.Set("X-Vault-Token", token)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to reach vault: %w", err)
	}

	defer func() {
		if err := resp.Body.Close(); err != nil {
			log.Printf("failed to close response body: %v", err)
		}
	}()

	if err := raiseForStatus(resp); err != nil {
		return nil, err
	}

	var readResp kvV2ReadResponse
	if err := json.NewDecoder(resp.Body).Decode(&readResp); err != nil {
		return nil, fmt.Errorf("failed to decode read secret response: %w", err)
	}

	return readResp.Data.Data, nil
}

// vaultErrorResponse captures the standard error body returned by Vault,
// e.g. {"errors": ["invalid role or secret ID"]}.
type vaultErrorResponse struct {
	Errors []string `json:"errors"`
}

// vaultErrorDetail extracts a human-readable detail from a Vault error
// response body, falling back to the raw body if it isn't the expected
// JSON shape.
func vaultErrorDetail(body []byte) string {
	var errResp vaultErrorResponse
	if err := json.Unmarshal(body, &errResp); err == nil && len(errResp.Errors) > 0 {
		return strings.Join(errResp.Errors, "; ")
	}

	detail := strings.TrimSpace(string(body))
	if detail == "" {
		return "no additional details returned"
	}

	return detail
}

func raiseForStatus(resp *http.Response) error {
	if resp.StatusCode < 400 {
		return nil
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		body = nil
	}

	detail := vaultErrorDetail(body)

	switch resp.StatusCode {
	case http.StatusUnauthorized:
		return fmt.Errorf("vault: authentication error, please check the credentials: %s", detail)
	case http.StatusForbidden:
		return fmt.Errorf("vault: permission error, please ensure you have access to this resource: %s", detail)
	case http.StatusNotFound:
		return fmt.Errorf("%w: %s", ErrNotFound, detail)
	default:
		return fmt.Errorf("vault: request failed with status %d: %s", resp.StatusCode, detail)
	}
}
