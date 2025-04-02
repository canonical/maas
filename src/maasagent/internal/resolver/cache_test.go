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

func TestCacheEntry_Expired(t *testing.T) {
	now := time.Now()

	testcases := map[string]struct {
		in struct {
			ttl       uint32
			createdAt time.Time
			timeSince time.Time
		}
		out bool
	}{
		"valid": {
			in: struct {
				ttl       uint32
				createdAt time.Time
				timeSince time.Time
			}{
				ttl:       60,
				createdAt: now,
				timeSince: now.Add(time.Second),
			},
			out: false,
		},
		"expired": {
			in: struct {
				ttl       uint32
				createdAt time.Time
				timeSince time.Time
			}{
				ttl:       1,
				createdAt: now,
				timeSince: now.Add(time.Second),
			},
			out: true,
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			ce := &cacheEntry{
				RR: &dns.A{
					Hdr: dns.RR_Header{
						Name:   "example.com",
						Rrtype: dns.TypeA,
						Ttl:    tc.in.ttl,
					},
				},
				CreatedAt: tc.in.createdAt,
			}

			assert.Equal(t, tc.out, ce.Expired(tc.in.timeSince))
		})
	}
}

func TestCache_Get(t *testing.T) {
	testcases := map[string]struct {
		in struct {
			createCache func() (*lru.Cache[string, *cacheEntry], error)
			key         struct {
				name   string
				rrtype uint16
			}
		}
		out struct {
			rr dns.RR
			ok bool
		}
	}{
		"empty": {
			in: struct {
				createCache func() (*lru.Cache[string, *cacheEntry], error)
				key         struct {
					name   string
					rrtype uint16
				}
			}{
				createCache: func() (*lru.Cache[string, *cacheEntry], error) {
					return lru.New[string, *cacheEntry](1)
				},
				key: struct {
					name   string
					rrtype uint16
				}{
					name:   "example.com",
					rrtype: dns.TypeA,
				},
			},
			out: struct {
				rr dns.RR
				ok bool
			}{
				rr: nil,
				ok: false,
			},
		},
		"basic": {
			in: struct {
				createCache func() (*lru.Cache[string, *cacheEntry], error)
				key         struct {
					name   string
					rrtype uint16
				}
			}{
				createCache: func() (*lru.Cache[string, *cacheEntry], error) {
					cache, err := lru.New[string, *cacheEntry](1)
					if err != nil {
						return nil, err
					}

					_ = cache.Add("example.com_A", &cacheEntry{
						RR: &dns.A{
							Hdr: dns.RR_Header{
								Name:   "example.com",
								Rrtype: dns.TypeA,
								Ttl:    3600,
							},
							A: net.ParseIP("127.0.0.1"),
						},
						CreatedAt: time.Now(),
					})

					return cache, nil
				},
				key: struct {
					name   string
					rrtype uint16
				}{
					name:   "example.com",
					rrtype: dns.TypeA,
				},
			},
			out: struct {
				rr dns.RR
				ok bool
			}{
				rr: &dns.A{
					Hdr: dns.RR_Header{
						Name:   "example.com",
						Rrtype: dns.TypeA,
						Ttl:    3600,
					},
					A: net.ParseIP("127.0.0.1"),
				},
				ok: true,
			},
		},
		"multiple entries": {
			in: struct {
				createCache func() (*lru.Cache[string, *cacheEntry], error)
				key         struct {
					name   string
					rrtype uint16
				}
			}{
				createCache: func() (*lru.Cache[string, *cacheEntry], error) {
					cache, err := lru.New[string, *cacheEntry](2)
					if err != nil {
						return nil, err
					}

					_ = cache.Add("example.com_A", &cacheEntry{
						RR: &dns.A{
							Hdr: dns.RR_Header{
								Name:   "example.com",
								Rrtype: dns.TypeA,
								Ttl:    3600,
							},
							A: net.ParseIP("127.0.0.1"),
						},
						CreatedAt: time.Now(),
					})

					_ = cache.Add("www.example.com_A", &cacheEntry{
						RR: &dns.A{
							Hdr: dns.RR_Header{
								Name:   "www.example.com",
								Rrtype: dns.TypeA,
								Ttl:    3600,
							},
							A: net.ParseIP("127.0.0.1"),
						},
						CreatedAt: time.Now(),
					})

					return cache, nil
				},
				key: struct {
					name   string
					rrtype uint16
				}{
					name:   "example.com",
					rrtype: dns.TypeA,
				},
			},
			out: struct {
				rr dns.RR
				ok bool
			}{
				rr: &dns.A{
					Hdr: dns.RR_Header{
						Name:   "example.com",
						Rrtype: dns.TypeA,
						Ttl:    3600,
					},
					A: net.ParseIP("127.0.0.1"),
				},
				ok: true,
			},
		},
		"expired": {
			in: struct {
				createCache func() (*lru.Cache[string, *cacheEntry], error)
				key         struct {
					name   string
					rrtype uint16
				}
			}{
				createCache: func() (*lru.Cache[string, *cacheEntry], error) {
					cache, err := lru.New[string, *cacheEntry](1)
					if err != nil {
						return nil, err
					}

					_ = cache.Add("example.com_A", &cacheEntry{
						RR: &dns.A{
							Hdr: dns.RR_Header{
								Name:   "example.com",
								Rrtype: dns.TypeA,
								Ttl:    0,
							},
							A: net.ParseIP("127.0.0.1"),
						},
						CreatedAt: time.Now(),
					})

					return cache, nil
				},
				key: struct {
					name   string
					rrtype uint16
				}{
					name:   "example.com",
					rrtype: dns.TypeA,
				},
			},
			out: struct {
				rr dns.RR
				ok bool
			}{
				rr: nil,
				ok: false,
			},
		},
		"not exist": {
			in: struct {
				createCache func() (*lru.Cache[string, *cacheEntry], error)
				key         struct {
					name   string
					rrtype uint16
				}
			}{
				createCache: func() (*lru.Cache[string, *cacheEntry], error) {
					cache, err := lru.New[string, *cacheEntry](1)
					if err != nil {
						return nil, err
					}

					_ = cache.Add("www.example.com_A", &cacheEntry{
						RR: &dns.A{
							Hdr: dns.RR_Header{
								Name:   "example.com",
								Rrtype: dns.TypeA,
								Ttl:    3600,
							},
							A: net.ParseIP("127.0.0.1"),
						},
						CreatedAt: time.Now(),
					})

					return cache, nil
				},
				key: struct {
					name   string
					rrtype uint16
				}{
					name:   "example.com",
					rrtype: dns.TypeA,
				},
			},
			out: struct {
				rr dns.RR
				ok bool
			}{
				rr: nil,
				ok: false,
			},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			lcache, err := tc.in.createCache()
			if err != nil {
				t.Fatal(err)
			}

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
	testcases := map[string]struct {
		in struct {
			cacheSize int
			records   []dns.RR
		}
		out []dns.RR
	}{
		"one record": {
			in: struct {
				cacheSize int
				records   []dns.RR
			}{
				cacheSize: 1,
				records: []dns.RR{
					&dns.A{
						Hdr: dns.RR_Header{
							Name:   "example.com",
							Rrtype: dns.TypeA,
							Ttl:    3600,
						},
						A: net.ParseIP("127.0.0.1"),
					},
				},
			},
			out: []dns.RR{
				&dns.A{
					Hdr: dns.RR_Header{
						Name:   "example.com",
						Rrtype: dns.TypeA,
						Ttl:    3600,
					},
					A: net.ParseIP("127.0.0.1"),
				},
			},
		},
		"two records": {
			in: struct {
				cacheSize int
				records   []dns.RR
			}{
				cacheSize: 2,
				records: []dns.RR{
					&dns.A{
						Hdr: dns.RR_Header{
							Name:   "example.com",
							Rrtype: dns.TypeA,
							Ttl:    3600,
						},
						A: net.ParseIP("127.0.0.1"),
					},
					&dns.A{
						Hdr: dns.RR_Header{
							Name:   "www.example.com",
							Rrtype: dns.TypeA,
							Ttl:    3600,
						},
						A: net.ParseIP("127.0.0.1"),
					},
				},
			},
			out: []dns.RR{
				&dns.A{
					Hdr: dns.RR_Header{
						Name:   "example.com",
						Rrtype: dns.TypeA,
						Ttl:    3600,
					},
					A: net.ParseIP("127.0.0.1"),
				},
				&dns.A{
					Hdr: dns.RR_Header{
						Name:   "www.example.com",
						Rrtype: dns.TypeA,
						Ttl:    3600,
					},
					A: net.ParseIP("127.0.0.1"),
				},
			},
		},
		"evict": {
			in: struct {
				cacheSize int
				records   []dns.RR
			}{
				cacheSize: 1,
				records: []dns.RR{
					&dns.A{
						Hdr: dns.RR_Header{
							Name:   "example.com",
							Rrtype: dns.TypeA,
							Ttl:    3600,
						},
						A: net.ParseIP("127.0.0.1"),
					},
					&dns.A{
						Hdr: dns.RR_Header{
							Name:   "www.example.com",
							Rrtype: dns.TypeA,
							Ttl:    3600,
						},
						A: net.ParseIP("127.0.0.1"),
					},
				},
			},
			out: []dns.RR{
				&dns.A{
					Hdr: dns.RR_Header{
						Name:   "www.example.com",
						Rrtype: dns.TypeA,
						Ttl:    3600,
					},
					A: net.ParseIP("127.0.0.1"),
				},
			},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
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
