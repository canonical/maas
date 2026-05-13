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

import "sync"

// Registry is a thread-safe in-memory store for discovered power drivers.
type Registry struct {
	mu      sync.RWMutex
	drivers map[string]SocketDriver
}

// NewRegistry creates a new empty Registry.
func NewRegistry() *Registry {
	return &Registry{
		drivers: make(map[string]SocketDriver),
	}
}

// Register adds or updates a driver in the registry.
func (r *Registry) Register(driver SocketDriver) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.drivers[driver.Name] = driver
}

// Unregister removes a driver from the registry by name.
func (r *Registry) Unregister(driverName string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	delete(r.drivers, driverName)
}

// Get looks up a driver by name. Returns the driver and true if found,
// or a zero SocketDriver and false if not.
func (r *Registry) Get(driverName string) (SocketDriver, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	driver, ok := r.drivers[driverName]
	return driver, ok
}

// GetAll returns a slice of all registered drivers.
func (r *Registry) GetAll() []SocketDriver {
	r.mu.RLock()
	defer r.mu.RUnlock()
	result := make([]SocketDriver, 0, len(r.drivers))
	for _, driver := range r.drivers {
		result = append(result, driver)
	}
	return result
}

// Diff computes the added and removed drivers between two snapshots.
// "added" contains drivers present in current but not in previous.
// "removed" contains drivers present in previous but not in current.
func Diff(previous, current []SocketDriver) (added, removed []SocketDriver) {
	prevMap := make(map[string]SocketDriver, len(previous))
	for _, d := range previous {
		prevMap[d.Name] = d
	}

	currMap := make(map[string]SocketDriver, len(current))
	for _, d := range current {
		currMap[d.Name] = d
	}

	for _, d := range current {
		if _, ok := prevMap[d.Name]; !ok {
			added = append(added, d)
		}
	}

	for _, d := range previous {
		if _, ok := currMap[d.Name]; !ok {
			removed = append(removed, d)
		}
	}

	return added, removed
}
