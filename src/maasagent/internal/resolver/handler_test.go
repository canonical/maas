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
	"context"
	"flag"
	"io"
	"net"
	"net/netip"
	"os"
	"path"
	"testing"
	"time"

	"github.com/miekg/dns"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

type parsedResolvConf struct {
	expectedCfg *systemConfig
	err         error
}

type mockResponseWriter struct {
	dns.ResponseWriter
	sent     []*dns.Msg
	writeErr error
}

func (m *mockResponseWriter) WriteMsg(msg *dns.Msg) error {
	m.sent = append(m.sent, msg)

	return m.writeErr
}

func (m *mockResponseWriter) RemoteAddr() net.Addr {
	addr, _ := net.ResolveIPAddr("ip4", "127.0.0.1")

	return addr
}

type mockConn struct {
	net.Conn
}

type mockClient struct {
	sent     []*dns.Msg // we send to the nameserver
	received []*dns.Msg // nameserver returns
	errs     []error
}

func (m *mockClient) Dial(_ string) (*dns.Conn, error) {
	return &dns.Conn{Conn: mockConn{}}, nil
}

func (m *mockClient) ExchangeWithConnContext(ctx context.Context, msg *dns.Msg, _ *dns.Conn) (*dns.Msg, time.Duration, error) {
	return m.ExchangeContext(ctx, msg, "")
}

func (m *mockClient) ExchangeContext(_ context.Context, msg *dns.Msg, _ string) (*dns.Msg, time.Duration, error) {
	m.sent = append(m.sent, msg)

	var (
		resp *dns.Msg
		err  error
	)

	if len(m.received) > 0 {
		resp = m.received[0]

		if len(m.received) > 1 {
			m.received = m.received[1:]
		} else {
			m.received = nil
		}
	}

	if len(m.errs) > 0 {
		err = m.errs[0]

		if len(m.errs) > 1 {
			m.errs = m.errs[1:]
		} else {
			m.errs = nil
		}
	}

	return resp, 0, err
}

type noopCache struct {
	Cache
}

func (n noopCache) Get(_ string, _ uint16) (dns.RR, bool) {
	return nil, false
}

func (n noopCache) Set(_ dns.RR) {}

func TestMain(m *testing.M) {
	flag.Parse()

	if !testing.Verbose() {
		zerolog.SetGlobalLevel(zerolog.Disabled)
		log.Logger = zerolog.New(io.Discard)
	}

	os.Exit(m.Run())
}

func TestParseResolvConf(t *testing.T) {
	testcases := map[string]struct {
		in  string
		out parsedResolvConf
	}{
		"empty": {
			out: parsedResolvConf{
				expectedCfg: &systemConfig{},
			},
		},
		"only one nameserver": {
			in: "nameserver 127.0.0.53",
			out: parsedResolvConf{
				expectedCfg: &systemConfig{
					Nameservers: []netip.Addr{netip.MustParseAddr("127.0.0.53")},
				},
			},
		},
		"only nameservers": {
			in: `nameserver 127.0.0.53
nameserver 1.1.1.1
nameserver 8.8.8.8
nameserver 8.8.4.4`,
			out: parsedResolvConf{
				expectedCfg: &systemConfig{
					Nameservers: []netip.Addr{
						netip.MustParseAddr("127.0.0.53"),
						netip.MustParseAddr("1.1.1.1"),
						netip.MustParseAddr("8.8.8.8"),
						netip.MustParseAddr("8.8.4.4"),
					},
				},
			},
		},
		"only one search domain": {
			in: "search example.com",
			out: parsedResolvConf{
				expectedCfg: &systemConfig{
					SearchDomains: []string{
						"example.com.",
					},
				},
			},
		},
		"only search domains": {
			in: "search example1.com example2.com example3.com",
			out: parsedResolvConf{
				expectedCfg: &systemConfig{
					SearchDomains: []string{
						"example1.com.",
						"example2.com.",
						"example3.com.",
					},
				},
			},
		},
		"nameservers and search domains": {
			in: `nameserver 127.0.0.53
search example.com`,
			out: parsedResolvConf{
				expectedCfg: &systemConfig{
					Nameservers: []netip.Addr{
						netip.MustParseAddr("127.0.0.53"),
					},
					SearchDomains: []string{"example.com."},
				},
			},
		},
		"nameservers missing space": {
			in: "nameserver127.0.0.53",
			out: parsedResolvConf{
				err: ErrInvalidResolvConf,
			},
		},
		"search domains missing space": {
			in: "searchexample.com",
			out: parsedResolvConf{
				err: ErrInvalidResolvConf,
			},
		},
		"with comments": {
			in: `# a comment
nameserver 127.0.0.53
search example.com`,
			out: parsedResolvConf{
				expectedCfg: &systemConfig{
					Nameservers: []netip.Addr{
						netip.MustParseAddr("127.0.0.53"),
					},
					SearchDomains: []string{"example.com."},
				},
			},
		},
		"options": {
			in: "options edns0 trust-ad",
			out: parsedResolvConf{
				expectedCfg: &systemConfig{
					EDNS0Enabled: true,
					TrustAD:      true,
				},
			},
		},
		"all valid values": {
			in: `nameserver 127.0.0.53
options edns0 trust-ad
search example.com`,
			out: parsedResolvConf{
				expectedCfg: &systemConfig{
					Nameservers: []netip.Addr{
						netip.MustParseAddr("127.0.0.53"),
					},
					SearchDomains: []string{"example.com."},
					EDNS0Enabled:  true,
					TrustAD:       true,
				},
			},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			tmpFile, err := os.CreateTemp("", "resolvconftest")
			if err != nil {
				t.Fatal(err)
			}

			defer func() {
				_ = os.Remove(tmpFile.Name())
			}()

			_, err = tmpFile.Write([]byte(tc.in))
			if err != nil {
				t.Fatal(err)
			}

			err = tmpFile.Close()
			if err != nil {
				t.Fatal(err)
			}

			cfg, err := parseResolvConf(tmpFile.Name())
			if err != nil {
				if tc.out.err != nil {
					assert.ErrorIs(t, err, tc.out.err)
					return
				}

				t.Error(err)

				return
			}

			assert.Equal(t, tc.out.expectedCfg, cfg)
		})
	}
}

func TestServeDNS(t *testing.T) {
	type in struct {
		file         string
		handler      func(h *RecursiveHandler)
		clientErrors []error
	}

	testcases := map[string]in{
		"type AXFR is invalid": {
			file: "invalid-axfr.dig",
		},
		"type IXFR is invalid": {
			file: "invalid-ixfr.dig",
		},
		"type ANY is invalid": {
			file: "invalid-any.dig",
		},
		"class CHAOS is invalid": {
			file: "invalid-class-chaos.dig",
		},
		"class ANY is invalid": {
			file: "invalid-class-any.dig",
		},
		"class NONE is invalid": {
			file: "invalid-class-none.dig",
		},
		"request having a non-query type is invalid": {
			file: "invalid-non-query.dig",
		},
		"request containing mixed types and classes is invalid": {
			file: "invalid-mixed.dig",
		},
		"basic non-authoritative request": {
			file: "non-authoritative.dig",
			handler: func(h *RecursiveHandler) {
				h.SetUpstreams(&systemConfig{
					Nameservers: []netip.Addr{netip.MustParseAddr("127.0.0.1")},
				}, nil)
			}},
		"handler configured with search domain": {
			file: "search.dig",
			handler: func(h *RecursiveHandler) {
				h.SetUpstreams(&systemConfig{
					Nameservers:   []netip.Addr{netip.MustParseAddr("10.0.0.1")},
					SearchDomains: []string{"test"},
				}, nil)
			}},
		"basic authoritative request": {
			file: "authoritative.dig",
			handler: func(h *RecursiveHandler) {
				h.SetUpstreams(&systemConfig{},
					[]string{"127.0.0.1"})
			}},
		"nxdomain": {
			file: "nxdomain.dig",
			handler: func(h *RecursiveHandler) {
				h.SetUpstreams(&systemConfig{
					Nameservers: []netip.Addr{netip.MustParseAddr("10.0.0.1")},
				}, nil)
			}},
		"return SERVFAIL because of the underlying client error": {
			file: "client-error.dig",
			handler: func(h *RecursiveHandler) {
				h.SetUpstreams(&systemConfig{
					Nameservers: []netip.Addr{netip.MustParseAddr("10.0.0.1")},
				}, nil)
			},
			clientErrors: []error{net.ErrClosed},
		},
		"single question": {
			file: "single-question.dig",
			handler: func(h *RecursiveHandler) {
				h.SetUpstreams(&systemConfig{
					Nameservers: []netip.Addr{netip.MustParseAddr("127.0.0.1")},
				}, nil)
			},
		},
		"multi question": {
			file: "multi-question.dig",
			handler: func(h *RecursiveHandler) {
				h.SetUpstreams(&systemConfig{
					Nameservers: []netip.Addr{netip.MustParseAddr("127.0.0.1")},
				}, nil)
				cache, _ := NewCache(int64(20 * maxRecordSize))
				h.recordCache = cache
			},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			file := path.Join("testdata", tc.file)

			// DNS request towards us (resolver)
			request := ParseDigOutputBlock(t, file, "Request")
			// One or more requests/responses from us (resolver) to the nameserver
			resolution := ParseDigOutputBlock(t, file, "Resolution")
			// Answer that is to be returned by us (resolver) to the client
			response := ParseDigOutputBlock(t, file, "Response")

			handler := NewRecursiveHandler(noopCache{})
			if tc.handler != nil {
				tc.handler(handler)
			}

			client := &mockClient{
				received: resolution,
				errs:     tc.clientErrors,
			}

			handler.client = client

			// responseWriter records response returned by resolver
			responseWriter := &mockResponseWriter{}

			require.Len(t, request, 1, "tests expecting to test a single request")

			handler.ServeDNS(responseWriter, request[0])

			for i, question := range extractQuestions(resolution) {
				// Client will generated a random number for Id, but for tests
				// we set it to a known number.
				client.sent[i].Id = question.Id
				require.Equal(t, question, client.sent[i], "mismatch sent query")
			}

			for i, answer := range response {
				require.Greater(t, responseWriter.sent[i].Id, uint16(0))
				responseWriter.sent[i].Id = answer.Id

				require.Equal(t, answer, responseWriter.sent[i], "mismatch response")
			}
		})
	}
}

func TestServeDNS_Cached(t *testing.T) {
	file := path.Join("testdata", "multi-question.dig")

	// DNS request towards us (resolver)
	request := ParseDigOutputBlock(t, file, "Request")
	// One or more requests/responses from us (resolver) to the nameserver
	resolution := ParseDigOutputBlock(t, file, "Resolution")
	// Answer that is to be returned by us (resolver) to the client
	response := ParseDigOutputBlock(t, file, "Response")

	cache, _ := NewCache(int64(20 * maxRecordSize))

	handler := NewRecursiveHandler(cache)
	handler.SetUpstreams(&systemConfig{
		Nameservers: []netip.Addr{netip.MustParseAddr("127.0.0.1")},
	}, nil)

	client := &mockClient{received: resolution}

	handler.client = client

	// responseWriter records response returned by resolver
	responseWriter := &mockResponseWriter{}

	handler.ServeDNS(responseWriter, request[0])

	for _, answer := range response[0].Answer {
		entry, ok := cache.Get(answer.Header().Name, answer.Header().Rrtype)

		assert.True(t, ok)
		assert.Equal(t, answer, entry)
	}

	for _, ns := range response[0].Ns {
		entry, ok := cache.Get(ns.Header().Name, ns.Header().Rrtype)

		assert.True(t, ok)
		assert.Equal(t, ns, entry)
	}

	for _, extra := range response[0].Extra {
		entry, ok := cache.Get(extra.Header().Name, extra.Header().Rrtype)

		assert.True(t, ok)
		assert.Equal(t, extra, entry)
	}
}

func TestConnMap_Get(t *testing.T) {
	testcases := map[string]struct {
		in struct {
			addr  netip.Addr
			conns map[netip.Addr][]*exclusiveConn
		}
		out struct {
			expectedMap map[netip.Addr][]*exclusiveConn
			conn        *exclusiveConn
			ok          bool
		}
	}{
		"one conn": {
			in: struct {
				addr  netip.Addr
				conns map[netip.Addr][]*exclusiveConn
			}{
				addr: netip.MustParseAddr("10.0.0.1"),
				conns: map[netip.Addr][]*exclusiveConn{
					netip.MustParseAddr("10.0.0.1"): {
						{
							conn: &dns.Conn{
								TsigSecret: map[string]string{"a": "a"}, // for testing identity in the list
							},
						},
					},
				},
			},
			out: struct {
				expectedMap map[netip.Addr][]*exclusiveConn
				conn        *exclusiveConn
				ok          bool
			}{
				expectedMap: map[netip.Addr][]*exclusiveConn{
					netip.MustParseAddr("10.0.0.1"): {
						{
							conn: &dns.Conn{
								TsigSecret: map[string]string{"a": "a"},
							},
						},
					},
				},
				conn: &exclusiveConn{
					conn: &dns.Conn{
						TsigSecret: map[string]string{"a": "a"},
					},
				},
				ok: true,
			},
		},
		"two conns": {
			in: struct {
				addr  netip.Addr
				conns map[netip.Addr][]*exclusiveConn
			}{
				addr: netip.MustParseAddr("10.0.0.1"),
				conns: map[netip.Addr][]*exclusiveConn{
					netip.MustParseAddr("10.0.0.1"): {
						{
							conn: &dns.Conn{
								TsigSecret: map[string]string{"a": "a"}, // for testing identity in the list
							},
						},
						{
							conn: &dns.Conn{
								TsigSecret: map[string]string{"b": "b"}, // for testing identity in the list
							},
						},
					},
				},
			},
			out: struct {
				expectedMap map[netip.Addr][]*exclusiveConn
				conn        *exclusiveConn
				ok          bool
			}{
				expectedMap: map[netip.Addr][]*exclusiveConn{
					netip.MustParseAddr("10.0.0.1"): {
						{
							conn: &dns.Conn{
								TsigSecret: map[string]string{"b": "b"},
							},
						},
						{
							conn: &dns.Conn{
								TsigSecret: map[string]string{"a": "a"},
							},
						},
					},
				},
				conn: &exclusiveConn{
					conn: &dns.Conn{
						TsigSecret: map[string]string{"a": "a"},
					},
				},
				ok: true,
			},
		},
		"no conns": {
			in: struct {
				addr  netip.Addr
				conns map[netip.Addr][]*exclusiveConn
			}{
				addr: netip.MustParseAddr("10.0.0.1"),
				conns: map[netip.Addr][]*exclusiveConn{
					netip.MustParseAddr("10.0.0.1"): {},
				},
			},
			out: struct {
				expectedMap map[netip.Addr][]*exclusiveConn
				conn        *exclusiveConn
				ok          bool
			}{
				expectedMap: map[netip.Addr][]*exclusiveConn{
					netip.MustParseAddr("10.0.0.1"): {},
				},
				ok: false,
			},
		},
		"wrong key": {
			in: struct {
				addr  netip.Addr
				conns map[netip.Addr][]*exclusiveConn
			}{
				addr: netip.MustParseAddr("10.0.0.2"),
				conns: map[netip.Addr][]*exclusiveConn{
					netip.MustParseAddr("10.0.0.1"): {
						{
							conn: &dns.Conn{
								TsigSecret: map[string]string{"a": "a"},
							},
						},
					},
				},
			},
			out: struct {
				expectedMap map[netip.Addr][]*exclusiveConn
				conn        *exclusiveConn
				ok          bool
			}{
				expectedMap: map[netip.Addr][]*exclusiveConn{
					netip.MustParseAddr("10.0.0.1"): {
						{
							conn: &dns.Conn{
								TsigSecret: map[string]string{"a": "a"},
							},
						},
					},
				},
				ok: false,
			},
		},
	}

	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			cm := &connMap{
				conns: tc.in.conns,
			}

			conn, ok := cm.Get(tc.in.addr)

			assert.Equal(t, tc.out.ok, ok)
			assert.Equal(t, tc.out.conn, conn)
			assert.Equal(t, tc.out.expectedMap, cm.conns)
		})
	}
}

func TestConnMap_Set(t *testing.T) {
	testcases := map[string]struct {
		in struct {
			addr    netip.Addr
			conn    *dns.Conn
			connMap *connMap
		}
		out map[netip.Addr][]*exclusiveConn
	}{
		"add one from empty": {
			in: struct {
				addr    netip.Addr
				conn    *dns.Conn
				connMap *connMap
			}{
				addr: netip.MustParseAddr("10.0.0.1"),
				conn: &dns.Conn{Conn: mockConn{}},
				connMap: &connMap{
					conns: make(map[netip.Addr][]*exclusiveConn),
				},
			},
			out: map[netip.Addr][]*exclusiveConn{
				netip.MustParseAddr("10.0.0.1"): {
					{
						conn: &dns.Conn{Conn: mockConn{}},
					},
				},
			},
		},
		"add one to existing": {
			in: struct {
				addr    netip.Addr
				conn    *dns.Conn
				connMap *connMap
			}{
				addr: netip.MustParseAddr("10.0.0.1"),
				conn: &dns.Conn{Conn: mockConn{}},
				connMap: &connMap{
					conns: map[netip.Addr][]*exclusiveConn{
						netip.MustParseAddr("10.0.0.1"): {
							{
								conn: &dns.Conn{
									Conn:       mockConn{},
									TsigSecret: map[string]string{"a": "a"},
								},
							},
						},
					},
				},
			},
			out: map[netip.Addr][]*exclusiveConn{
				netip.MustParseAddr("10.0.0.1"): {
					{
						conn: &dns.Conn{
							Conn:       mockConn{},
							TsigSecret: map[string]string{"a": "a"},
						},
					},
					{
						conn: &dns.Conn{Conn: mockConn{}},
					},
				},
			},
		},
		"add one to existing with different addr": {
			in: struct {
				addr    netip.Addr
				conn    *dns.Conn
				connMap *connMap
			}{
				addr: netip.MustParseAddr("10.0.0.2"),
				conn: &dns.Conn{Conn: mockConn{}},
				connMap: &connMap{
					conns: map[netip.Addr][]*exclusiveConn{
						netip.MustParseAddr("10.0.0.1"): {
							{
								conn: &dns.Conn{
									Conn: mockConn{},
								},
							},
						},
					},
				},
			},
			out: map[netip.Addr][]*exclusiveConn{
				netip.MustParseAddr("10.0.0.1"): {
					{
						conn: &dns.Conn{
							Conn: mockConn{},
						},
					},
				},
				netip.MustParseAddr("10.0.0.2"): {
					{
						conn: &dns.Conn{
							Conn: mockConn{},
						},
					},
				},
			},
		},
	}

	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			tc.in.connMap.Set(tc.in.addr, tc.in.conn)

			assert.Equal(t, tc.out, tc.in.connMap.conns)
		})
	}
}

func FuzzServeDNSQuestion(f *testing.F) {
	f.Add("example", uint16(5), uint16(1), "rdata")

	handler := NewRecursiveHandler(noopCache{})
	handler.systemResolvers = &systemConfig{
		Nameservers: []netip.Addr{netip.MustParseAddr("127.0.0.1")},
	}

	f.Fuzz(func(t *testing.T, label string, qtype uint16, qclass uint16, rdata string) {
		msg := &dns.Msg{
			MsgHdr: dns.MsgHdr{
				Id:     1,
				Opcode: dns.OpcodeQuery,
			},
			Question: []dns.Question{
				{
					Name:   label,
					Qtype:  qtype,
					Qclass: qclass,
				},
			},
		}

		resp := msg.Copy()
		resp.Answer = []dns.RR{
			&dns.RFC3597{ // allows for an "any" type
				Hdr: dns.RR_Header{
					Name:   label,
					Rrtype: qtype,
					Class:  qclass,
				},
				Rdata: rdata,
			},
		}

		handler.client = &mockClient{received: []*dns.Msg{resp}}

		responseWriter := &mockResponseWriter{}

		handler.ServeDNS(responseWriter, msg)

		assert.GreaterOrEqual(t, len(responseWriter.sent), 1)
	})
}

func BenchmarkServeDNS(b *testing.B) {
	type in struct {
		file    string
		handler func(h *RecursiveHandler)
	}

	testcases := map[string]in{
		"basic non-authoritative request": {
			file: "bench-non-authoritative.dig",
			handler: func(h *RecursiveHandler) {
				h.SetUpstreams(&systemConfig{
					Nameservers: []netip.Addr{netip.MustParseAddr("127.0.0.1")},
				}, nil)
			}},
		"basic authoritative request": {
			file: "bench-authoritative.dig",
			handler: func(h *RecursiveHandler) {
				h.SetUpstreams(&systemConfig{
					Nameservers: []netip.Addr{netip.MustParseAddr("127.0.0.1")},
				}, []string{"127.0.0.1"})
			}},
		"CNAME": {
			file: "bench-cname.dig",
			handler: func(h *RecursiveHandler) {
				h.SetUpstreams(&systemConfig{
					Nameservers:   []netip.Addr{netip.MustParseAddr("127.0.0.1")},
					SearchDomains: []string{"test"},
				}, []string{"127.0.0.1"})
			}},
	}

	for name, tc := range testcases {
		tc := tc

		b.Run(name, func(b *testing.B) {
			file := path.Join("testdata", tc.file)

			// DNS request towards us (resolver)
			request := ParseDigOutputBlock(b, file, "Request")
			// One or more requests/responses from us (resolver) to the nameserver
			resolution := ParseDigOutputBlock(b, file, "Resolution")

			cache, err := NewCache(0)
			if err != nil {
				b.Fatal(err)
			}

			handler := NewRecursiveHandler(cache)
			handler.systemResolvers = &systemConfig{
				Nameservers: []netip.Addr{netip.MustParseAddr("127.0.0.1")},
			}
			handler.authoritativeServers = []netip.Addr{netip.MustParseAddr("127.0.0.1")}

			client := &mockClient{received: resolution}
			handler.client = client

			questions := extractQuestions(request)

			for i := 0; i < b.N; i++ {
				queries := questions // if created outside of loop, answer section remains populated
				for _, query := range queries {
					handler.ServeDNS(&mockResponseWriter{}, query)
				}
			}
		})
	}
}

func BenchmarkServeDNS_Search(b *testing.B) {
	file := path.Join("testdata", "bench-search.dig")

	// DNS request towards us (resolver)
	request := ParseDigOutputBlock(b, file, "Request")
	// One or more requests/responses from us (resolver) to the nameserver
	resolution := ParseDigOutputBlock(b, file, "Resolution")
	resolutionIter := ParseDigOutputBlock(b, file, "Resolution iter")

	cache, err := NewCache(0)
	if err != nil {
		b.Fatal(err)
	}

	handler := NewRecursiveHandler(cache)
	handler.systemResolvers = &systemConfig{
		Nameservers:   []netip.Addr{netip.MustParseAddr("127.0.0.1")},
		SearchDomains: []string{"test"},
	}
	handler.authoritativeServers = []netip.Addr{netip.MustParseAddr("127.0.0.1")}

	client := &mockClient{received: resolution}

	handler.client = client

	question := extractQuestion(request[0])

	for i := 0; i < b.N; i++ {
		query := question.Copy() // if created outside of loop, answer section remains populated

		handler.ServeDNS(&mockResponseWriter{}, query)

		// non-NXDOMAINs are cached, but we still go through a full search on each iteration
		handler.client = &mockClient{received: resolutionIter}
	}
}
