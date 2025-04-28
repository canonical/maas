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
	"time"

	lru "github.com/hashicorp/golang-lru/v2"
	"github.com/miekg/dns"
)

const (
	maxRecordSize        = 512
	defaultMaxNumRecords = 1000
)

type Cache interface {
	Get(string, uint16) (dns.RR, bool)
	Set(dns.RR)
}

type cacheEntry struct {
	RR        dns.RR
	CreatedAt time.Time
}

// Expired calculates if an entry has reached its TTL
func (c *cacheEntry) expired(ts time.Time) bool {
	ttl := c.RR.Header().Ttl

	return ts.Sub(c.CreatedAt) >= time.Duration(ttl)*time.Second
}

type CacheOption func(*cache)

type cache struct {
	cache         *lru.Cache[string, *cacheEntry]
	stats         *cacheStats
	maxNumRecords int
}

// NewCache provides a constructor for an in-memory DNS cache
func NewCache(options ...CacheOption) (Cache, error) {
	c := &cache{
		stats:         &cacheStats{},
		maxNumRecords: defaultMaxNumRecords,
	}

	for _, option := range options {
		option(c)
	}

	lruCache, err := lru.New[string, *cacheEntry](c.maxNumRecords)
	if err != nil {
		return nil, err
	}

	c.cache = lruCache

	return c, nil
}

// WithMaxSize allows setting the maximum cache size in bytes. By default it is
// limited to defaultMaxNumRecords (1000), but if WithMaxSize is provided, then
// it is calculated as maxNumRecords = size / maxRecordSize (512 bytes)
func WithMaxSize(size int64) CacheOption {
	return func(c *cache) {
		if size != 0 {
			c.maxNumRecords = max(int(size/maxRecordSize), 1)
		}
	}
}

// Get fetches a record for the given name and type if one is present
// in the cache, returns false if one is absent or expired
func (c *cache) Get(name string, rrtype uint16) (dns.RR, bool) {
	key := c.key(name, rrtype)

	entry, ok := c.cache.Get(key)
	if !ok {
		c.stats.misses.Add(1)

		return nil, ok
	}

	if entry.expired(time.Now()) {
		_ = c.cache.Remove(key)

		c.stats.expirations.Add(1)

		return nil, false
	}

	c.stats.hits.Add(1)

	return entry.RR, ok
}

// Set inserts a record into the cache
func (c *cache) Set(rr dns.RR) {
	hdr := rr.Header()
	key := c.key(hdr.Name, hdr.Rrtype)

	_ = c.cache.Add(key, &cacheEntry{
		RR:        rr,
		CreatedAt: time.Now(),
	})

	c.stats.size.Add(1)
}

// key generates the key for a record in the cache
func (c *cache) key(name string, rrtype uint16) string {
	return name + "_" + dns.TypeToString[rrtype]
}
