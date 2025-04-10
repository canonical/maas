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
	"net"
	"testing"
	"time"

	lru "github.com/hashicorp/golang-lru/v2"
	"github.com/miekg/dns"
	"github.com/stretchr/testify/assert"
)

type key struct {
	name   string
	rrtype uint16
}

func createKey(name string, rrtype uint16) key {
	return key{
		name:   name,
		rrtype: rrtype,
	}
}

func createARecord(name string, ttl uint32, ip string) dns.RR {
	return &dns.A{
		Hdr: dns.RR_Header{
			Name:   name,
			Rrtype: dns.TypeA,
			Ttl:    ttl,
		},
		A: net.ParseIP(ip),
	}
}

func createCache(size int) *lru.Cache[string, *cacheEntry] {
	cache, err := lru.New[string, *cacheEntry](size)
	if err != nil {
		panic(err)
	}

	return cache
}

func createCacheEntry(rr dns.RR) *cacheEntry {
	return &cacheEntry{
		RR:        rr,
		CreatedAt: time.Now(),
	}
}

func TestCacheEntry_Expired(t *testing.T) {
	now := time.Now()

	expiredEquals := func(ttl uint32, createdAt, timeSince time.Time, want bool) func(t *testing.T) {
		return func(t *testing.T) {
			ce := &cacheEntry{
				RR:        createARecord("example.com", ttl, "127.0.0.1"),
				CreatedAt: createdAt,
			}

			assert.Equal(t, want, ce.expired(timeSince))
		}
	}

	t.Run("valid", expiredEquals(60, now, now.Add(time.Second), false))
	t.Run("expired", expiredEquals(1, now, now.Add(time.Second), true))
}

func TestCache_Get(t *testing.T) {
	type in struct {
		createCache func() *lru.Cache[string, *cacheEntry]
		key         key
	}

	type out struct {
		rr dns.RR
		ok bool
	}

	testcases := map[string]struct {
		in  in
		out out
	}{
		"empty": {
			in: in{
				createCache: func() *lru.Cache[string, *cacheEntry] {
					return createCache(1)
				},
				key: createKey("example.com", dns.TypeA),
			},
			out: out{
				rr: nil,
				ok: false,
			},
		},
		"basic": {
			in: in{
				createCache: func() *lru.Cache[string, *cacheEntry] {
					cache := createCache(1)

					_ = cache.Add("example.com_A", createCacheEntry(
						createARecord("example.com", 3600, "127.0.0.1"),
					))

					return cache
				},
				key: createKey("example.com", dns.TypeA),
			},
			out: out{
				rr: createARecord("example.com", 3600, "127.0.0.1"),
				ok: true,
			},
		},
		"multiple entries": {
			in: in{
				createCache: func() *lru.Cache[string, *cacheEntry] {
					cache := createCache(2)

					_ = cache.Add("example.com_A", createCacheEntry(
						createARecord("example.com", 3600, "127.0.0.1"),
					))

					_ = cache.Add("www.example.com_A", createCacheEntry(
						createARecord("www.example.com", 3600, "127.0.0.1"),
					))

					return cache
				},
				key: createKey("example.com", dns.TypeA),
			},
			out: out{
				rr: createARecord("example.com", 3600, "127.0.0.1"),
				ok: true,
			},
		},
		"expired": {
			in: in{
				createCache: func() *lru.Cache[string, *cacheEntry] {
					cache := createCache(1)

					_ = cache.Add("example.com_A", createCacheEntry(
						createARecord("example.com", 0, "127.0.0.1"),
					))

					return cache
				},
				key: createKey("example.com", dns.TypeA),
			},
			out: out{
				rr: nil,
				ok: false,
			},
		},
		"not exist": {
			in: in{
				createCache: func() *lru.Cache[string, *cacheEntry] {
					cache := createCache(1)

					_ = cache.Add("www.example.com_A", createCacheEntry(
						createARecord("www.example.com", 3600, "127.0.0.1"),
					))

					return cache
				},
				key: createKey("example.com", dns.TypeA),
			},
			out: out{
				rr: nil,
				ok: false,
			},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			var lcache *lru.Cache[string, *cacheEntry]

			assert.NotPanics(t, func() {
				lcache = tc.in.createCache()
			})

			c := &cache{
				cache: lcache,
				stats: &cacheStats{},
			}

			rr, ok := c.Get(tc.in.key.name, tc.in.key.rrtype)

			assert.Equal(t, tc.out.ok, ok)
			assert.Equal(t, tc.out.rr, rr)
		})
	}
}

func TestCache_Set(t *testing.T) {
	type in struct {
		cacheSize int
		records   []dns.RR
	}

	testcases := map[string]struct {
		in  in
		out []dns.RR
	}{
		"one record": {
			in: in{
				cacheSize: 1,
				records: []dns.RR{
					createARecord("example.com", 3600, "127.0.0.1"),
				},
			},
			out: []dns.RR{
				createARecord("example.com", 3600, "127.0.0.1"),
			},
		},
		"two records": {
			in: in{
				cacheSize: 2,
				records: []dns.RR{
					createARecord("example.com", 3600, "127.0.0.1"),
					createARecord("www.example.com", 3600, "127.0.0.1"),
				},
			},
			out: []dns.RR{
				createARecord("example.com", 3600, "127.0.0.1"),
				createARecord("www.example.com", 3600, "127.0.0.1"),
			},
		},
		"evict": {
			in: in{
				cacheSize: 1,
				records: []dns.RR{
					createARecord("example.com", 3600, "127.0.0.1"),
					createARecord("www.example.com", 3600, "127.0.0.1"),
				},
			},
			out: []dns.RR{
				createARecord("www.example.com", 3600, "127.0.0.1"),
			},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			cache, err := NewCache(int64(tc.in.cacheSize * maxRecordSize))
			if err != nil {
				t.Fatal(err)
			}

			for _, rr := range tc.in.records {
				cache.Set(rr)
			}

			for _, expected := range tc.out {
				name := expected.Header().Name
				rrtype := expected.Header().Rrtype

				rr, ok := cache.Get(name, rrtype)

				assert.True(t, ok)
				assert.Equal(t, expected, rr)
			}
		})
	}
}
