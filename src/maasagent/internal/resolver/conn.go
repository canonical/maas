// Copyright (c) 2025 Canonical Ltd
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

package resolver

import (
	"net/netip"
	"sync"

	"maas.io/core/src/maasagent/internal/connpool"
)

type conns struct {
	m    map[netip.Addr]connpool.Pool
	lock sync.RWMutex
}

func (c *conns) Get(addr netip.Addr) (connpool.Pool, bool) {
	c.lock.RLock()
	defer c.lock.RUnlock()

	pool, ok := c.m[addr]

	return pool, ok
}

func (c *conns) Set(addr netip.Addr, pool connpool.Pool) {
	c.lock.Lock()
	defer c.lock.Unlock()

	c.m[addr] = pool
}

func (c *conns) Delete(addr netip.Addr) {
	c.lock.Lock()
	defer c.lock.Unlock()

	delete(c.m, addr)
}

func (c *conns) Close() {
	c.lock.Lock()
	defer c.lock.Unlock()

	for _, pool := range c.m {
		pool.Close()
	}

	c.m = make(map[netip.Addr]connpool.Pool)
}

func (c *conns) Range(fn func(addr netip.Addr, pool connpool.Pool)) {
	c.lock.RLock()
	defer c.lock.RUnlock()

	for addr, pool := range c.m {
		fn(addr, pool)
	}
}
