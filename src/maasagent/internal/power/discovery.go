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
	"log/slog"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"maas.io/core/src/maasagent/internal/pathutil"
)

// SocketDriver represents a power driver accessible via a UNIX domain socket.
type SocketDriver struct {
	// Name is the driver name (e.g. "ipmi", "redfish").
	Name string
	// SocketPath is the full path to the UNIX domain socket.
	SocketPath string
	// Metadata contains the driver metadata returned by GET /metadata.
	Metadata map[string]any
}

// Discovery scans a directory for power driver UNIX sockets and queries their metadata.
type Discovery struct {
	logger    *slog.Logger
	socketDir string
	timeout   time.Duration
}

// NewDiscovery creates a new Discovery for the given socket directory.
func NewDiscovery(logger *slog.Logger, socketDir string) *Discovery {
	return &Discovery{
		logger:    logger,
		socketDir: socketDir,
		timeout:   5 * time.Second,
	}
}

// DefaultSocketDir returns the default power drivers socket directory
// based on the installation type (snap or deb).
func DefaultSocketDir() string {
	return filepath.Join(pathutil.RunDir(), "power-drivers")
}

// Scan scans the socket directory for .sock files and queries each for metadata.
// It returns a slice of SocketDriver for all responsive drivers.
// Stale sockets that fail to respond are logged and skipped.
func (d *Discovery) Scan(ctx context.Context) ([]SocketDriver, error) {
	entries, err := os.ReadDir(d.socketDir)
	if err != nil {
		if os.IsNotExist(err) {
			d.logger.Warn("socket directory does not exist", "dir", d.socketDir)
			return nil, nil
		}
		return nil, fmt.Errorf("read socket directory %s: %w", d.socketDir, err)
	}

	var drivers []SocketDriver

	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".sock") {
			continue
		}

		socketPath := filepath.Join(d.socketDir, entry.Name())
		driver, err := d.querySocket(ctx, socketPath, entry.Name())
		if err != nil {
			d.logger.Warn("skipping unresponsive socket", "socket", socketPath, "error", err)
			continue
		}

		drivers = append(drivers, *driver)
	}

	return drivers, nil
}

// querySocket connects to a single UNIX socket and queries its /metadata endpoint.
func (d *Discovery) querySocket(ctx context.Context, socketPath, sockName string) (*SocketDriver, error) {
	client := newHTTPClientForSocket(socketPath, d.timeout)

	reqCtx, cancel := context.WithTimeout(ctx, d.timeout)
	defer cancel()

	req, err := http.NewRequestWithContext(reqCtx, http.MethodGet, "http://localhost/metadata", nil)
	if err != nil {
		return nil, fmt.Errorf("create metadata request: %w", err)
	}

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("query metadata from %s: %w", socketPath, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("metadata query returned status %d", resp.StatusCode)
	}

	var metadata map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&metadata); err != nil {
		return nil, fmt.Errorf("decode metadata from %s: %w", socketPath, err)
	}

	name, ok := metadata["name"].(string)
	if !ok || name == "" {
		// Fallback: derive name from socket filename
		name = strings.TrimSuffix(sockName, ".sock")
	}

	return &SocketDriver{
		Name:       name,
		SocketPath: socketPath,
		Metadata:   metadata,
	}, nil
}

// ScanSocketDirectory is a convenience function that creates a Discovery
// and scans the given directory. It is provided for backward compatibility
// and simple use cases.
func ScanSocketDirectory(path string) ([]SocketDriver, error) {
	logger := slog.Default()
	discovery := NewDiscovery(logger, path)
	return discovery.Scan(context.Background())
}

// newHTTPClientForSocket creates an http.Client configured to dial the given UNIX socket.
func newHTTPClientForSocket(socketPath string, timeout time.Duration) *http.Client {
	return &http.Client{
		Timeout: timeout,
		Transport: &http.Transport{
			DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
				return net.DialTimeout("unix", socketPath, timeout)
			},
		},
	}
}
