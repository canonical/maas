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
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"strings"

	"maas.io/core/src/maasagent/internal/client"
)

// RegionClient communicates with the MAAS region controller's internal API
// to register and unregister power drivers discovered by the agent.
type RegionClient struct {
	logger *slog.Logger
	client *client.Client
}

// NewRegionClient creates a new RegionClient that uses the existing
// client.Client for mTLS communication with the region controller.
func NewRegionClient(logger *slog.Logger, c *client.Client) *RegionClient {
	return &RegionClient{
		logger: logger,
		client: c,
	}
}

// RegisterDriverPayload represents a single driver to register with the region.
type RegisterDriverPayload struct {
	Name    string         `json:"name"`
	Version string         `json:"version"`
	Schema  map[string]any `json:"schema"`
}

// RegisterDrivers notifies the region about discovered power drivers for an agent.
// It POSTs to /MAAS/api/v3/internal/agents/{agent_uuid}/power-driver:register.
func (c *RegionClient) RegisterDrivers(ctx context.Context, agentUUID string, drivers []SocketDriver) error {
	path := fmt.Sprintf("/agents/%s/power-driver:register", url.PathEscape(agentUUID))

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

	data, err := json.Marshal(map[string]any{"drivers": payloads})
	if err != nil {
		return fmt.Errorf("marshal register payload: %w", err)
	}

	resp, err := c.client.Request(ctx, http.MethodPost, path, data)
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
// It DELETEs to /MAAS/api/v3/internal/agents/{agent_uuid}/power-driver/{driver_name}/{version}.
func (c *RegionClient) UnregisterDriver(ctx context.Context, agentUUID, driverName, version string) error {
	path := fmt.Sprintf(
		"/agents/%s/power-driver/%s/%s",
		url.PathEscape(agentUUID),
		url.PathEscape(driverName),
		url.PathEscape(version),
	)

	resp, err := c.client.Request(ctx, http.MethodDelete, path, nil)
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
