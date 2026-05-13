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
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"sync"
	"syscall"
)

// SignalHandler manages SIGHUP handling to trigger power driver re-discovery.
// On SIGHUP, it re-scans the socket directory, computes the diff against the
// previous scan, updates the registry, and notifies the region controller.
type SignalHandler struct {
	logger       *slog.Logger
	discovery    *Discovery
	registry     *Registry
	regionClient *RegionClient
	agentUUID    string
	mu           sync.Mutex
	prevDrivers  []SocketDriver
	stopCh       chan struct{}
}

// SetupSignalHandler creates and starts a SIGHUP signal handler.
// It registers the handler and returns the SignalHandler for lifecycle management.
func SetupSignalHandler(
	logger *slog.Logger,
	socketDir string,
	registry *Registry,
	discovery *Discovery,
	regionClient *RegionClient,
	agentUUID string,
) *SignalHandler {
	h := &SignalHandler{
		logger:       logger,
		discovery:    discovery,
		registry:     registry,
		regionClient: regionClient,
		agentUUID:    agentUUID,
		stopCh:       make(chan struct{}),
	}

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGHUP)

	go h.listen(sigCh)

	return h
}

// Stop stops the signal handler and releases resources.
func (h *SignalHandler) Stop() {
	close(h.stopCh)
}

// listen blocks waiting for SIGHUP signals and triggers re-discovery.
func (h *SignalHandler) listen(sigCh <-chan os.Signal) {
	for {
		select {
		case <-sigCh:
			h.logger.Info("received SIGHUP, re-scanning power driver sockets")
			if err := h.rescan(); err != nil {
				h.logger.Error("power driver re-scan failed", "error", err)
			}
		case <-h.stopCh:
			return
		}
	}
}

// rescan performs a full re-scan of the socket directory, computes the diff,
// updates the registry, and notifies the region of changes.
func (h *SignalHandler) rescan() error {
	ctx := context.Background()

	current, err := h.discovery.Scan(ctx)
	if err != nil {
		return fmt.Errorf("scan socket directory: %w", err)
	}

	h.mu.Lock()
	prev := h.prevDrivers
	h.prevDrivers = current
	h.mu.Unlock()

	added, removed := Diff(prev, current)

	if len(added) == 0 && len(removed) == 0 {
		h.logger.Info("power driver re-scan: no changes detected")
		return nil
	}

	if len(added) > 0 {
		h.logger.Info("registering new power drivers", "count", len(added))
		for _, d := range added {
			h.registry.Register(d)
		}
		if err := h.regionClient.RegisterDrivers(ctx, h.agentUUID, added); err != nil {
			h.logger.Error("failed to register drivers with region", "error", err)
			return fmt.Errorf("register drivers with region: %w", err)
		}
	}

	if len(removed) > 0 {
		h.logger.Info("unregistering removed power drivers", "count", len(removed))
		for _, d := range removed {
			h.registry.Unregister(d.Name)
			version := ""
			if v, ok := d.Metadata["version"].(string); ok {
				version = v
			}
			if err := h.regionClient.UnregisterDriver(ctx, h.agentUUID, d.Name, version); err != nil {
				h.logger.Error("failed to unregister driver from region", "driver", d.Name, "error", err)
			}
		}
	}

	return nil
}
