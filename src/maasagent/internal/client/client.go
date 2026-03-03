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

package client

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
)

const apiURL = "/MAAS/a/v3internal"

type Client struct {
	apiURL     *url.URL
	httpClient *http.Client
}

func New(baseURL *url.URL, tlsConfig *tls.Config) *Client {
	return &Client{
		apiURL: baseURL.JoinPath(apiURL),
		httpClient: &http.Client{
			Transport: &http.Transport{
				TLSClientConfig: tlsConfig,
			},
		},
	}
}

func (c *Client) request(ctx context.Context, method, path string,
	body []byte) (*http.Response, error) {
	u := c.apiURL.JoinPath(path)

	var bodyReader io.Reader
	if len(body) > 0 {
		bodyReader = bytes.NewReader(body)
	}

	req, err := http.NewRequestWithContext(ctx, method, u.String(), bodyReader)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	if len(body) > 0 {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}

	return resp, nil
}

// Enroll sends an enrollment request to the controller.
// It uses TLS fingerprint pinning for secure communication.
func (c *Client) Enroll(ctx context.Context,
	req EnrollRequest) (*EnrollResponse, error) {
	data, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal enrollment request: %w", err)
	}

	resp, err := c.request(ctx, http.MethodPost, "/agents:enroll", data)
	if err != nil {
		return nil, err
	}

	//nolint:errcheck // we do not care about possible error here
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		return nil, fmt.Errorf("enrollment failed with status %d", resp.StatusCode)
	}

	enrollResp := &EnrollResponse{}
	if err := json.NewDecoder(resp.Body).Decode(enrollResp); err != nil {
		return nil, fmt.Errorf("failed to parse enrollment response: %w", err)
	}

	return enrollResp, nil
}

// GetConfig fetches agent configuration from the controller.
func (c *Client) GetConfig(ctx context.Context,
	agentUUID string) (*ConfigResponse, error) {
	resp, err := c.request(ctx, http.MethodGet,
		fmt.Sprintf("/agents/%s/config", url.PathEscape(agentUUID)), nil)
	if err != nil {
		return nil, err
	}

	//nolint:errcheck // we do not care about possible error here
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("get config failed with status %d", resp.StatusCode)
	}

	configResp := &ConfigResponse{}
	if err := json.NewDecoder(resp.Body).Decode(configResp); err != nil {
		return nil, fmt.Errorf("failed to parse config response: %w", err)
	}

	return configResp, nil
}
