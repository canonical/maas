// Copyright (c) 2023-2026 Canonical Ltd
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

package power

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"strings"
)

// RegionClient communicates with the MAAS region controller's internal API
// to register and unregister power drivers discovered by the agent.
type RegionClient struct {
	logger     *slog.Logger
	baseURL    *url.URL
	httpClient *http.Client
}

// NewRegionClient creates a new RegionClient that uses the given TLS config
// for mTLS authentication with the region controller.
func NewRegionClient(logger *slog.Logger, baseURL *url.URL, tlsConfig *tls.Config) *RegionClient {
	return &RegionClient{
		logger:  logger,
		baseURL: baseURL,
		httpClient: &http.Client{
			Transport: &http.Transport{
				TLSClientConfig: tlsConfig,
			},
		},
	}
}

// RegisterDriverPayload represents a single driver to register with the region.
type RegisterDriverPayload struct {
	Name    string         `json:"name"`
	Version string         `json:"version"`
	Schema  map[string]any `json:"schema"`
}

// RegisterDrivers notifies the region about discovered power drivers for an agent.
// It POSTs to /MAAS/api/v3/internal/agents/{agent_uuid}/power-drivers:register.
func (c *RegionClient) RegisterDrivers(ctx context.Context, agentUUID string, drivers []SocketDriver) error {
	path := fmt.Sprintf("/MAAS/api/v3/internal/agents/%s/power-drivers:register", url.PathEscape(agentUUID))

	payloads := make([]RegisterDriverPayload, 0, len(drivers))
	for _, d := range drivers {
		p := RegisterDriverPayload{
			Name:    d.Name,
			Schema:  d.Metadata,
		}
		if v, ok := d.Metadata["version"]; ok {
			if vs, ok := v.(string); ok {
				p.Version = vs
			}
		}
		payloads = append(payloads, p)
	}

	payload := map[string]any{
		"drivers": payloads,
	}

	data, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal register payload: %w", err)
	}

	resp, err := c.doRequest(ctx, http.MethodPost, path, bytes.NewReader(data))
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("register drivers failed with status %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}

	return nil
}

// UnregisterDriver notifies the region that a power driver has been removed.
// It DELETEs to /MAAS/api/v3/internal/agents/{agent_uuid}/power-drivers/{driver_name}/{version}.
func (c *RegionClient) UnregisterDriver(ctx context.Context, agentUUID, driverName, version string) error {
	path := fmt.Sprintf(
		"/MAAS/api/v3/internal/agents/%s/power-drivers/%s/%s",
		url.PathEscape(agentUUID),
		url.PathEscape(driverName),
		url.PathEscape(version),
	)

	resp, err := c.doRequest(ctx, http.MethodDelete, path, nil)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNoContent {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("unregister driver failed with status %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}

	return nil
}

// doRequest performs an HTTP request to the region controller.
func (c *RegionClient) doRequest(ctx context.Context, method, path string, body io.Reader) (*http.Response, error) {
	u := c.baseURL.ResolveReference(&url.URL{Path: path})

	req, err := http.NewRequestWithContext(ctx, method, u.String(), body)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request to region failed: %w", err)
	}

	return resp, nil
}
