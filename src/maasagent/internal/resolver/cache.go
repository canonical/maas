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
	maxRecordSize         = 512
	defaultCacheRecordCap = 1000
)

type Cache interface {
	Get(string, uint16) (dns.RR, bool)
	Set(dns.RR)
}

type cacheEntry struct {
	RR        dns.RR
	CreatedAt time.Time
}

func (c *cacheEntry) Expired(ts time.Time) bool {
	ttl := c.RR.Header().Ttl

	return ts.Sub(c.CreatedAt) >= time.Duration(ttl)*time.Second
}

type CacheOption func(*cache)

type cache struct {
	cache    *lru.Cache[string, *cacheEntry]
	stats    *cacheStats
	maxCount int64
}

func NewCache(size int64, options ...CacheOption) (Cache, error) {
	maxNumRecords := defaultCacheRecordCap

	if size != 0 {
		maxNumRecords = int(size / maxRecordSize)
		if maxNumRecords < 1 {
			maxNumRecords = 1
		}
	}

	lruCache, err := lru.New[string, *cacheEntry](maxNumRecords)
	if err != nil {
		return nil, err
	}

	c := &cache{
		cache:    lruCache,
		stats:    &cacheStats{},
		maxCount: int64(maxNumRecords),
	}

	for _, option := range options {
		option(c)
	}

	return c, nil
}

func (c *cache) Get(name string, rrtype uint16) (dns.RR, bool) {
	key := c.key(name, rrtype)

	entry, ok := c.cache.Get(key)
	if !ok {
		c.stats.misses.Add(1)

		return nil, ok
	}

	if entry.Expired(time.Now()) {
		_ = c.cache.Remove(key)

		c.stats.expirations.Add(1)

		return nil, false
	}

	c.stats.hits.Add(1)

	return entry.RR, ok
}

func (c *cache) Set(rr dns.RR) {
	hdr := rr.Header()
	key := c.key(hdr.Name, hdr.Rrtype)

	_ = c.cache.Add(key, &cacheEntry{
		RR:        rr,
		CreatedAt: time.Now(),
	})

	c.stats.size.Add(1)
}

func (c *cache) key(name string, rrtype uint16) string {
	return name + "_" + dns.TypeToString[rrtype]
}
