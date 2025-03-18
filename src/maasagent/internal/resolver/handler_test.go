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
	"encoding/binary"
	"net"
	"net/netip"
	"os"
	"testing"
	"time"

	"github.com/miekg/dns"
	"github.com/stretchr/testify/assert"
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

type mockClient struct {
	sent     []*dns.Msg
	received []*dns.Msg
	errs     []error
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

			handler := NewRecursiveHandler(noopCache{})

			cfg, err := handler.parseResolvConf(tmpFile.Name())
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

func TestValidateQuery(t *testing.T) {
	testcases := map[string]struct {
		in  *dns.Msg
		out struct {
			expectedMsg   *dns.Msg
			expectedValid bool
		}
	}{
		"valid": {
			in: &dns.Msg{
				MsgHdr: dns.MsgHdr{
					Id:     1,
					Opcode: dns.OpcodeQuery,
				},
				Question: []dns.Question{
					{
						Name:   "example.com",
						Qtype:  dns.TypeA,
						Qclass: dns.ClassINET,
					},
				},
			},
			out: struct {
				expectedMsg   *dns.Msg
				expectedValid bool
			}{
				expectedValid: true,
			},
		},
		"AXFR": {
			in: &dns.Msg{
				MsgHdr: dns.MsgHdr{
					Id:     1,
					Opcode: dns.OpcodeQuery,
				},
				Question: []dns.Question{
					{
						Name:   "example.com",
						Qtype:  dns.TypeAXFR,
						Qclass: dns.ClassINET,
					},
				},
			},
			out: struct {
				expectedMsg   *dns.Msg
				expectedValid bool
			}{
				expectedMsg: &dns.Msg{
					MsgHdr: dns.MsgHdr{
						Id:       1,
						Opcode:   dns.OpcodeQuery,
						Response: true,
						Rcode:    dns.RcodeRefused,
					},
					Question: []dns.Question{
						{
							Name:   "example.com",
							Qtype:  dns.TypeAXFR,
							Qclass: dns.ClassINET,
						},
					},
					Answer: []dns.RR{},
					Ns:     []dns.RR{},
					Extra:  []dns.RR{},
				},
				expectedValid: false,
			},
		},
		"IXFR": {
			in: &dns.Msg{
				MsgHdr: dns.MsgHdr{
					Id:     1,
					Opcode: dns.OpcodeQuery,
				},
				Question: []dns.Question{
					{
						Name:   "example.com",
						Qtype:  dns.TypeIXFR,
						Qclass: dns.ClassINET,
					},
				},
			},
			out: struct {
				expectedMsg   *dns.Msg
				expectedValid bool
			}{
				expectedMsg: &dns.Msg{
					MsgHdr: dns.MsgHdr{
						Id:       1,
						Opcode:   dns.OpcodeQuery,
						Response: true,
						Rcode:    dns.RcodeRefused,
					},
					Question: []dns.Question{
						{
							Name:   "example.com",
							Qtype:  dns.TypeIXFR,
							Qclass: dns.ClassINET,
						},
					},
					Answer: []dns.RR{},
					Ns:     []dns.RR{},
					Extra:  []dns.RR{},
				},
				expectedValid: false,
			},
		},
		"ANY": {
			in: &dns.Msg{
				MsgHdr: dns.MsgHdr{
					Id:     1,
					Opcode: dns.OpcodeQuery,
				},
				Question: []dns.Question{
					{
						Name:   "example.com",
						Qtype:  dns.TypeANY,
						Qclass: dns.ClassINET,
					},
				},
			},
			out: struct {
				expectedMsg   *dns.Msg
				expectedValid bool
			}{
				expectedMsg: &dns.Msg{
					MsgHdr: dns.MsgHdr{
						Id:       1,
						Opcode:   dns.OpcodeQuery,
						Response: true,
						Rcode:    dns.RcodeNotImplemented,
					},
					Question: []dns.Question{
						{
							Name:   "example.com",
							Qtype:  dns.TypeANY,
							Qclass: dns.ClassINET,
						},
					},
					Answer: []dns.RR{},
					Ns:     []dns.RR{},
					Extra:  []dns.RR{},
				},
				expectedValid: false,
			},
		},
		"class CHAOS": {
			in: &dns.Msg{
				MsgHdr: dns.MsgHdr{
					Id:     1,
					Opcode: dns.OpcodeQuery,
				},
				Question: []dns.Question{
					{
						Name:   "example.com",
						Qtype:  dns.TypeTXT,
						Qclass: dns.ClassCHAOS,
					},
				},
			},
			out: struct {
				expectedMsg   *dns.Msg
				expectedValid bool
			}{
				expectedMsg: &dns.Msg{
					MsgHdr: dns.MsgHdr{
						Id:       1,
						Opcode:   dns.OpcodeQuery,
						Response: true,
						Rcode:    dns.RcodeRefused,
					},
					Question: []dns.Question{
						{
							Name:   "example.com",
							Qtype:  dns.TypeTXT,
							Qclass: dns.ClassCHAOS,
						},
					},
					Answer: []dns.RR{},
					Ns:     []dns.RR{},
					Extra:  []dns.RR{},
				},
				expectedValid: false,
			},
		},
		"class ANY": {
			in: &dns.Msg{
				MsgHdr: dns.MsgHdr{
					Id:     1,
					Opcode: dns.OpcodeQuery,
				},
				Question: []dns.Question{
					{
						Name:   "example.com",
						Qtype:  dns.TypeTXT,
						Qclass: dns.ClassANY,
					},
				},
			},
			out: struct {
				expectedMsg   *dns.Msg
				expectedValid bool
			}{
				expectedMsg: &dns.Msg{
					MsgHdr: dns.MsgHdr{
						Id:       1,
						Opcode:   dns.OpcodeQuery,
						Response: true,
						Rcode:    dns.RcodeRefused,
					},
					Question: []dns.Question{
						{
							Name:   "example.com",
							Qtype:  dns.TypeTXT,
							Qclass: dns.ClassANY,
						},
					},
					Answer: []dns.RR{},
					Ns:     []dns.RR{},
					Extra:  []dns.RR{},
				},
				expectedValid: false,
			},
		},
		"class NONE": {
			in: &dns.Msg{
				MsgHdr: dns.MsgHdr{
					Id:     1,
					Opcode: dns.OpcodeQuery,
				},
				Question: []dns.Question{
					{
						Name:   "example.com",
						Qtype:  dns.TypeTXT,
						Qclass: dns.ClassNONE,
					},
				},
			},
			out: struct {
				expectedMsg   *dns.Msg
				expectedValid bool
			}{
				expectedMsg: &dns.Msg{
					MsgHdr: dns.MsgHdr{
						Id:       1,
						Opcode:   dns.OpcodeQuery,
						Response: true,
						Rcode:    dns.RcodeRefused,
					},
					Question: []dns.Question{
						{
							Name:   "example.com",
							Qtype:  dns.TypeTXT,
							Qclass: dns.ClassNONE,
						},
					},
					Answer: []dns.RR{},
					Ns:     []dns.RR{},
					Extra:  []dns.RR{},
				},
				expectedValid: false,
			},
		},
		"non-query": {
			in: &dns.Msg{
				MsgHdr: dns.MsgHdr{
					Id:     1,
					Opcode: dns.OpcodeNotify,
				},
			},
			out: struct {
				expectedMsg   *dns.Msg
				expectedValid bool
			}{
				expectedMsg: &dns.Msg{
					MsgHdr: dns.MsgHdr{
						Id:       1,
						Opcode:   dns.OpcodeNotify,
						Response: true,
						Rcode:    dns.RcodeRefused,
					},
					Answer: []dns.RR{},
					Ns:     []dns.RR{},
					Extra:  []dns.RR{},
				},
				expectedValid: false,
			},
		},
		// unlikely to really happen, but could be done with manually crafted packets
		"mixed invalid": {
			in: &dns.Msg{
				MsgHdr: dns.MsgHdr{
					Id:     1,
					Opcode: dns.OpcodeQuery,
				},
				Question: []dns.Question{
					{
						Name:   "example.com",
						Qtype:  dns.TypeAXFR,
						Qclass: dns.ClassANY,
					},
				},
			},
			out: struct {
				expectedMsg   *dns.Msg
				expectedValid bool
			}{
				expectedMsg: &dns.Msg{
					MsgHdr: dns.MsgHdr{
						Id:       1,
						Opcode:   dns.OpcodeQuery,
						Response: true,
						Rcode:    dns.RcodeRefused,
					},
					Question: []dns.Question{
						{
							Name:   "example.com",
							Qtype:  dns.TypeAXFR,
							Qclass: dns.ClassANY,
						},
					},
					Answer: []dns.RR{},
					Ns:     []dns.RR{},
					Extra:  []dns.RR{},
				},
				expectedValid: false,
			},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			handler := NewRecursiveHandler(noopCache{})

			responseWriter := &mockResponseWriter{}

			ok := handler.validateQuery(responseWriter, tc.in)

			assert.Equal(t, tc.out.expectedValid, ok)

			if len(responseWriter.sent) > 0 {
				assert.Equal(t, tc.out.expectedMsg, responseWriter.sent[0])
			}
		})
	}
}

func TestSrvFailResponse(t *testing.T) {
	in := &dns.Msg{
		MsgHdr: dns.MsgHdr{
			Id:     1,
			Opcode: dns.OpcodeQuery,
		},
		Question: []dns.Question{
			{
				Name:   "example.com",
				Qtype:  dns.TypeA,
				Qclass: dns.ClassINET,
			},
		},
	}

	expectedOut := &dns.Msg{
		MsgHdr: dns.MsgHdr{
			Id:       1,
			Opcode:   dns.OpcodeQuery,
			Response: true,
			Rcode:    dns.RcodeServerFailure,
		},
		Question: []dns.Question{
			{
				Name:   "example.com",
				Qtype:  dns.TypeA,
				Qclass: dns.ClassINET,
			},
		},
		Answer: []dns.RR{},
		Ns:     []dns.RR{},
		Extra:  []dns.RR{},
	}

	handler := NewRecursiveHandler(noopCache{})

	responseWriter := &mockResponseWriter{}

	handler.srvFailResponse(responseWriter, in)

	assert.Equal(t, expectedOut, responseWriter.sent[0])
}

func TestServeDNS(t *testing.T) {
	testcases := map[string]struct {
		in struct {
			msg                  *dns.Msg
			client               ResolverClient
			config               *systemConfig
			authoritativeServers []netip.Addr
		}
		out struct {
			sent     []*dns.Msg
			received []*dns.Msg
		}
	}{
		"basic non-authoritative": {
			in: struct {
				msg                  *dns.Msg
				client               ResolverClient
				config               *systemConfig
				authoritativeServers []netip.Addr
			}{
				msg: &dns.Msg{
					MsgHdr: dns.MsgHdr{
						Id:               1,
						Opcode:           dns.OpcodeQuery,
						RecursionDesired: true,
					},
					Question: []dns.Question{
						{
							Name:   "example.com.",
							Qtype:  dns.TypeA,
							Qclass: dns.ClassINET,
						},
					},
				},
				client: &mockClient{
					received: []*dns.Msg{
						{
							MsgHdr: dns.MsgHdr{
								Id:               1,
								Opcode:           dns.OpcodeQuery,
								RecursionDesired: true,
							},
							Question: []dns.Question{
								{
									Name:   "example.com.",
									Qtype:  dns.TypeA,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.A{
									Hdr: dns.RR_Header{
										Name:     "example.com.",
										Rrtype:   dns.TypeA,
										Class:    dns.ClassINET,
										Ttl:      30,
										Rdlength: uint16(binary.Size(net.ParseIP("10.0.0.1"))),
									},
									A: net.ParseIP("10.0.0.1"),
								},
							},
							Ns:    []dns.RR{},
							Extra: []dns.RR{},
						},
					},
				},
				config: &systemConfig{
					Nameservers: []netip.Addr{netip.MustParseAddr("127.0.0.1")},
				},
			},
			out: struct {
				sent     []*dns.Msg
				received []*dns.Msg
			}{
				sent: []*dns.Msg{
					{
						MsgHdr: dns.MsgHdr{
							Id:               1,
							Opcode:           dns.OpcodeQuery,
							RecursionDesired: true,
						},
						Question: []dns.Question{
							{
								Name:   "example.com.",
								Qtype:  dns.TypeA,
								Qclass: dns.ClassINET,
							},
						},
					},
				},
				received: []*dns.Msg{
					{

						MsgHdr: dns.MsgHdr{
							Id:                 1,
							Opcode:             dns.OpcodeQuery,
							RecursionDesired:   true,
							RecursionAvailable: true,
							Response:           true,
							Rcode:              dns.RcodeSuccess,
						},
						Question: []dns.Question{
							{
								Name:   "example.com.",
								Qtype:  dns.TypeA,
								Qclass: dns.ClassINET,
							},
						},
						Answer: []dns.RR{
							&dns.A{
								Hdr: dns.RR_Header{
									Name:     "example.com.",
									Rrtype:   dns.TypeA,
									Class:    dns.ClassINET,
									Ttl:      30,
									Rdlength: uint16(binary.Size(net.ParseIP("10.0.0.1"))),
								},
								A: net.ParseIP("10.0.0.1"),
							},
						},
						Ns:    []dns.RR{},
						Extra: []dns.RR{},
					},
				},
			},
		},
		"search": {
			in: struct {
				msg                  *dns.Msg
				client               ResolverClient
				config               *systemConfig
				authoritativeServers []netip.Addr
			}{
				msg: &dns.Msg{
					MsgHdr: dns.MsgHdr{
						Id:               1,
						Opcode:           dns.OpcodeQuery,
						RecursionDesired: true,
					},
					Question: []dns.Question{
						{
							Name:   "example.",
							Qtype:  dns.TypeA,
							Qclass: dns.ClassINET,
						},
					},
				},
				client: &mockClient{
					received: []*dns.Msg{
						{
							MsgHdr: dns.MsgHdr{
								Id:               1,
								Opcode:           dns.OpcodeQuery,
								RecursionDesired: true,
								Response:         true,
								Rcode:            dns.RcodeNameError,
							},
							Question: []dns.Question{
								{
									Name:   "example.",
									Qtype:  dns.TypeA,
									Qclass: dns.ClassINET,
								},
							},
						},
						{
							MsgHdr: dns.MsgHdr{
								Id:               1,
								Opcode:           dns.OpcodeQuery,
								RecursionDesired: true,
								Response:         true,
								Rcode:            dns.RcodeSuccess,
							},
							Question: []dns.Question{
								{
									Name:   "example.test.",
									Qtype:  dns.TypeA,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.A{
									Hdr: dns.RR_Header{
										Name:     "example.test.",
										Rrtype:   dns.TypeA,
										Class:    dns.ClassINET,
										Ttl:      30,
										Rdlength: uint16(binary.Size(net.ParseIP("10.0.0.1"))),
									},
									A: net.ParseIP("10.0.0.1"),
								},
							},
						},
					},
				},
				config: &systemConfig{
					Nameservers: []netip.Addr{
						netip.MustParseAddr("10.0.0.1"),
					},
					SearchDomains: []string{
						"test",
					},
				},
			},
			out: struct {
				sent     []*dns.Msg
				received []*dns.Msg
			}{
				sent: []*dns.Msg{
					{
						MsgHdr: dns.MsgHdr{
							Id:               1,
							Opcode:           dns.OpcodeQuery,
							RecursionDesired: true,
						},
						Question: []dns.Question{
							{
								Name:   "example.",
								Qtype:  dns.TypeA,
								Qclass: dns.ClassINET,
							},
						},
					},
					{
						MsgHdr: dns.MsgHdr{
							Id:               1,
							Opcode:           dns.OpcodeQuery,
							RecursionDesired: true,
						},
						Question: []dns.Question{
							{
								Name:   "example.test.",
								Qtype:  dns.TypeA,
								Qclass: dns.ClassINET,
							},
						},
					},
				},
				received: []*dns.Msg{
					{
						MsgHdr: dns.MsgHdr{
							Id:                 1,
							Opcode:             dns.OpcodeQuery,
							RecursionDesired:   true,
							RecursionAvailable: true,
							Response:           true,
							Rcode:              dns.RcodeSuccess,
						},
						Question: []dns.Question{
							{
								Name:   "example.",
								Qtype:  dns.TypeA,
								Qclass: dns.ClassINET,
							},
						},
						Answer: []dns.RR{
							&dns.A{
								Hdr: dns.RR_Header{
									Name:     "example.test.",
									Rrtype:   dns.TypeA,
									Class:    dns.ClassINET,
									Ttl:      30,
									Rdlength: uint16(binary.Size(net.ParseIP("10.0.0.1"))),
								},
								A: net.ParseIP("10.0.0.1"),
							},
						},
						Ns:    []dns.RR{},
						Extra: []dns.RR{},
					},
				},
			},
		},
		"basic authoritative": {
			in: struct {
				msg                  *dns.Msg
				client               ResolverClient
				config               *systemConfig
				authoritativeServers []netip.Addr
			}{
				msg: &dns.Msg{
					MsgHdr: dns.MsgHdr{
						Id:     1,
						Opcode: dns.OpcodeQuery,
					},
					Question: []dns.Question{
						{
							Name:   "example.maas.",
							Qtype:  dns.TypeA,
							Qclass: dns.ClassINET,
						},
					},
					Answer: []dns.RR{},
					Ns:     []dns.RR{},
					Extra:  []dns.RR{},
				},
				client: &mockClient{
					received: []*dns.Msg{
						{
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeSuccess,
							},
							Question: []dns.Question{
								{
									Name:   ".",
									Qtype:  dns.TypeNS,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.NS{
									Hdr: dns.RR_Header{
										Name:   ".",
										Rrtype: dns.TypeNS,
									},
									Ns: "maas.",
								},
							},
							Ns: []dns.RR{},
							Extra: []dns.RR{ // some / most servers will return the A record for the nameserver
								&dns.A{
									Hdr: dns.RR_Header{
										Name:   "maas.",
										Rrtype: dns.TypeA,
										Ttl:    30,
									},
									A: net.ParseIP("127.0.0.1"),
								},
							},
						}, {
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeNameError,
							},
							Question: []dns.Question{
								{
									Name:   "maas.",
									Qtype:  dns.TypeCNAME,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{},
							Ns:     []dns.RR{},
							Extra:  []dns.RR{},
						}, {
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeSuccess,
							},
							Question: []dns.Question{
								{
									Name:   "maas.",
									Qtype:  dns.TypeA,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.A{
									Hdr: dns.RR_Header{
										Name:   "maas.",
										Rrtype: dns.TypeA,
										Ttl:    30,
									},
									A: net.ParseIP("127.0.0.1"),
								},
							},
							Ns:    []dns.RR{},
							Extra: []dns.RR{},
						}, {
							MsgHdr: dns.MsgHdr{
								Id:       2,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								// querying the root server for an internal zone should
								// NXDOMAIN, and in turn, the resolver will go back to querying region servers
								Rcode: dns.RcodeNameError,
							},
							Question: []dns.Question{
								{
									Name:   "maas.",
									Qtype:  dns.TypeNS,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{},
							Ns:     []dns.RR{},
							Extra:  []dns.RR{},
						}, {
							MsgHdr: dns.MsgHdr{
								Id:       2,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeSuccess,
							},
							Question: []dns.Question{
								{
									Name:   "maas.",
									Qtype:  dns.TypeNS,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.NS{
									Hdr: dns.RR_Header{
										Name:   "maas.",
										Rrtype: dns.TypeNS,
										Ttl:    30,
									},
									Ns: "maas.",
								},
							},
							Ns:    []dns.RR{},
							Extra: []dns.RR{},
						}, {
							MsgHdr: dns.MsgHdr{
								Id:       2,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeNameError,
							},
							Question: []dns.Question{
								{
									Name:   "maas.",
									Qtype:  dns.TypeCNAME,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{},
							Ns:     []dns.RR{},
							Extra:  []dns.RR{},
						}, {
							MsgHdr: dns.MsgHdr{
								Id:       2,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeSuccess,
							},
							Question: []dns.Question{
								{
									Name:   "maas.",
									Qtype:  dns.TypeA,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.A{
									Hdr: dns.RR_Header{
										Name:   "maas.",
										Rrtype: dns.TypeA,
										Class:  dns.ClassINET,
										Ttl:    30,
									},
									A: net.ParseIP("127.0.0.1"),
								},
							},
							Ns:    []dns.RR{},
							Extra: []dns.RR{},
						}, {
							MsgHdr: dns.MsgHdr{
								Id:       3,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeNameError,
							},
							Question: []dns.Question{
								{
									Name:   "example.maas.",
									Qtype:  dns.TypeNS,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{},
							Ns:     []dns.RR{},
							Extra:  []dns.RR{},
						}, {
							MsgHdr: dns.MsgHdr{
								Id:       3,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeNameError,
							},
							Question: []dns.Question{
								{
									Name:   "example.maas.",
									Qtype:  dns.TypeNS,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{},
							Ns:     []dns.RR{},
							Extra:  []dns.RR{},
						}, {
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeNameError,
							},
							Question: []dns.Question{
								{
									Name:   "maas.",
									Qtype:  dns.TypeCNAME,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{},
							Ns:     []dns.RR{},
							Extra:  []dns.RR{},
						}, {
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeSuccess,
							},
							Question: []dns.Question{
								{
									Name:   "maas.",
									Qtype:  dns.TypeA,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.A{
									Hdr: dns.RR_Header{
										Name:   "maas.",
										Rrtype: dns.TypeA,
										Ttl:    30,
									},
									A: net.ParseIP("127.0.0.1"),
								},
							},
							Ns:    []dns.RR{},
							Extra: []dns.RR{},
						}, {
							MsgHdr: dns.MsgHdr{
								Id:       4,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeSuccess,
							},
							Question: []dns.Question{
								{
									Name:   "example.maas.",
									Qtype:  dns.TypeA,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.A{
									Hdr: dns.RR_Header{
										Name:   "example.maas.",
										Rrtype: dns.TypeA,
										Class:  dns.ClassINET,
										Ttl:    30,
									},
									A: net.ParseIP("10.0.0.1"),
								},
							},
						},
					},
				},
				config:               &systemConfig{},
				authoritativeServers: []netip.Addr{netip.MustParseAddr("127.0.0.1")},
			},
			out: struct {
				sent     []*dns.Msg
				received []*dns.Msg
			}{
				sent: []*dns.Msg{
					{
						MsgHdr: dns.MsgHdr{
							Id:     1,
							Opcode: dns.OpcodeQuery,
						},
						Question: []dns.Question{
							{
								Name:   ".",
								Qtype:  dns.TypeNS,
								Qclass: dns.ClassINET,
							},
						},
					}, {
						MsgHdr: dns.MsgHdr{
							Id:     1,
							Opcode: dns.OpcodeQuery,
						},
						Question: []dns.Question{
							{
								Name:   "maas.",
								Qtype:  dns.TypeCNAME,
								Qclass: dns.ClassINET,
							},
						},
					}, {
						MsgHdr: dns.MsgHdr{
							Id:     1,
							Opcode: dns.OpcodeQuery,
						},
						Question: []dns.Question{
							{
								Name:   "maas.",
								Qtype:  dns.TypeA,
								Qclass: dns.ClassINET,
							},
						},
					}, {
						MsgHdr: dns.MsgHdr{
							Id:     1,
							Opcode: dns.OpcodeQuery,
						},
						Question: []dns.Question{
							{
								Name:   "maas.",
								Qtype:  dns.TypeNS,
								Qclass: dns.ClassINET,
							},
						},
					}, {
						MsgHdr: dns.MsgHdr{
							Id:     1,
							Opcode: dns.OpcodeQuery,
						},
						Question: []dns.Question{
							{
								Name:   "maas.",
								Qtype:  dns.TypeNS,
								Qclass: dns.ClassINET,
							},
						},
					}, {
						MsgHdr: dns.MsgHdr{
							Id:     1,
							Opcode: dns.OpcodeQuery,
						},
						Question: []dns.Question{
							{
								Name:   "maas.",
								Qtype:  dns.TypeCNAME,
								Qclass: dns.ClassINET,
							},
						},
					}, {
						MsgHdr: dns.MsgHdr{
							Id:     1,
							Opcode: dns.OpcodeQuery,
						},
						Question: []dns.Question{
							{
								Name:   "maas.",
								Qtype:  dns.TypeA,
								Qclass: dns.ClassINET,
							},
						},
					}, {
						MsgHdr: dns.MsgHdr{
							Id:     1,
							Opcode: dns.OpcodeQuery,
						},
						Question: []dns.Question{
							{
								Name:   "example.maas.",
								Qtype:  dns.TypeNS,
								Qclass: dns.ClassINET,
							},
						},
					}, {
						MsgHdr: dns.MsgHdr{
							Id:     1,
							Opcode: dns.OpcodeQuery,
						},
						Question: []dns.Question{
							{
								Name:   "example.maas.",
								Qtype:  dns.TypeNS,
								Qclass: dns.ClassINET,
							},
						},
					}, {
						MsgHdr: dns.MsgHdr{
							Id:     1,
							Opcode: dns.OpcodeQuery,
						},
						Question: []dns.Question{
							{
								Name:   "maas.",
								Qtype:  dns.TypeCNAME,
								Qclass: dns.ClassINET,
							},
						},
					}, {
						MsgHdr: dns.MsgHdr{
							Id:     1,
							Opcode: dns.OpcodeQuery,
						},
						Question: []dns.Question{
							{
								Name:   "maas.",
								Qtype:  dns.TypeA,
								Qclass: dns.ClassINET,
							},
						},
					}, {
						MsgHdr: dns.MsgHdr{
							Id:     1,
							Opcode: dns.OpcodeQuery,
						},
						Question: []dns.Question{
							{
								Name:   "example.maas.",
								Qtype:  dns.TypeA,
								Qclass: dns.ClassINET,
							},
						},
					},
				},
				received: []*dns.Msg{
					{
						MsgHdr: dns.MsgHdr{
							Id:                 1,
							Opcode:             dns.OpcodeQuery,
							Response:           true,
							Rcode:              dns.RcodeSuccess,
							RecursionAvailable: true,
						},
						Question: []dns.Question{
							{
								Name:   "example.maas.",
								Qtype:  dns.TypeA,
								Qclass: dns.ClassINET,
							},
						},
						Answer: []dns.RR{
							&dns.A{
								Hdr: dns.RR_Header{
									Name:   "example.maas.",
									Rrtype: dns.TypeA,
									Class:  dns.ClassINET,
									Ttl:    30,
								},
								A: net.ParseIP("10.0.0.1"),
							},
						},
						Ns:    []dns.RR{},
						Extra: []dns.RR{},
					},
				},
			},
		},
		"nxdomain": {
			in: struct {
				msg                  *dns.Msg
				client               ResolverClient
				config               *systemConfig
				authoritativeServers []netip.Addr
			}{
				msg: &dns.Msg{
					MsgHdr: dns.MsgHdr{
						Id:               1,
						Opcode:           dns.OpcodeQuery,
						RecursionDesired: true,
					},
					Question: []dns.Question{
						{
							Name:   "example.com.",
							Qtype:  dns.TypeA,
							Qclass: dns.ClassINET,
						},
					},
				},
				client: &mockClient{
					received: []*dns.Msg{
						{
							MsgHdr: dns.MsgHdr{
								Id:               1,
								Opcode:           dns.OpcodeQuery,
								RecursionDesired: true,
								Response:         true,
								Rcode:            dns.RcodeNameError,
							},
							Question: []dns.Question{
								{
									Name:   "example.com.",
									Qtype:  dns.TypeA,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{},
							Ns:     []dns.RR{},
							Extra:  []dns.RR{},
						},
					},
				},
				config: &systemConfig{
					Nameservers: []netip.Addr{
						netip.MustParseAddr("10.0.0.1"),
					},
				},
			},
			out: struct {
				sent     []*dns.Msg
				received []*dns.Msg
			}{
				sent: []*dns.Msg{
					{
						MsgHdr: dns.MsgHdr{
							Id:               1,
							Opcode:           dns.OpcodeQuery,
							RecursionDesired: true,
						},
						Question: []dns.Question{
							{
								Name:   "example.com.",
								Qtype:  dns.TypeA,
								Qclass: dns.ClassINET,
							},
						},
					},
				},
				received: []*dns.Msg{
					{
						MsgHdr: dns.MsgHdr{
							Id:                 1,
							Opcode:             dns.OpcodeQuery,
							RecursionDesired:   true,
							RecursionAvailable: true,
							Response:           true,
							Rcode:              dns.RcodeNameError,
						},
						Question: []dns.Question{
							{
								Name:   "example.com.",
								Qtype:  dns.TypeA,
								Qclass: dns.ClassINET,
							},
						},
						Answer: []dns.RR{},
						Ns:     []dns.RR{},
						Extra:  []dns.RR{},
					},
				},
			},
		},
		"client error": {
			in: struct {
				msg                  *dns.Msg
				client               ResolverClient
				config               *systemConfig
				authoritativeServers []netip.Addr
			}{
				msg: &dns.Msg{
					MsgHdr: dns.MsgHdr{
						Id:               1,
						Opcode:           dns.OpcodeQuery,
						RecursionDesired: true,
					},
					Question: []dns.Question{
						{
							Name:   "example.com.",
							Qtype:  dns.TypeA,
							Qclass: dns.ClassINET,
						},
					},
				},
				client: &mockClient{
					errs: []error{net.ErrClosed},
				},
				config: &systemConfig{
					Nameservers: []netip.Addr{
						netip.MustParseAddr("10.0.0.1"),
					},
				},
			},
			out: struct {
				sent     []*dns.Msg
				received []*dns.Msg
			}{
				sent: []*dns.Msg{
					{
						MsgHdr: dns.MsgHdr{
							Id:               1,
							Opcode:           dns.OpcodeQuery,
							RecursionDesired: true,
						},
						Question: []dns.Question{
							{
								Name:   "example.com.",
								Qtype:  dns.TypeA,
								Qclass: dns.ClassINET,
							},
						},
					},
				},
				received: []*dns.Msg{
					{
						MsgHdr: dns.MsgHdr{
							Id:               1,
							Opcode:           dns.OpcodeQuery,
							RecursionDesired: true,
							Response:         true,
							Rcode:            dns.RcodeServerFailure,
						},
						Question: []dns.Question{
							{
								Name:   "example.com.",
								Qtype:  dns.TypeA,
								Qclass: dns.ClassINET,
							},
						},
						Answer: []dns.RR{},
						Ns:     []dns.RR{},
						Extra:  []dns.RR{},
					},
				},
			},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			handler := NewRecursiveHandler(noopCache{})
			handler.systemResolvers = tc.in.config
			handler.client = tc.in.client
			handler.authoritativeServers = tc.in.authoritativeServers

			responseWriter := &mockResponseWriter{}

			handler.ServeDNS(responseWriter, tc.in.msg)

			client := handler.client.(*mockClient)

			for i, sent := range tc.out.sent {
				assert.Greater(t, client.sent[i].Id, uint16(0))

				// set id to 1 to avoid random generation
				client.sent[i].Id = 1

				assert.Equal(t, sent, client.sent[i], "mismatch sent query")
			}

			for i, received := range tc.out.received {
				assert.Greater(t, responseWriter.sent[i].Id, uint16(0))

				// set id to 1 to avoid random generation
				responseWriter.sent[i].Id = 1

				assert.Equal(t, received, responseWriter.sent[i], "mismatch response")
			}
		})
	}
}

func TestGetNS(t *testing.T) {
	testcases := map[string]struct {
		in struct {
			name                 string
			client               ResolverClient
			authoritativeServers []string
		}
		out struct {
			ns  *dns.NS
			err error
		}
	}{
		"basic": {
			in: struct {
				name                 string
				client               ResolverClient
				authoritativeServers []string
			}{
				name: "example.com",
				client: &mockClient{
					received: []*dns.Msg{
						{
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeSuccess,
							},
							Question: []dns.Question{
								{
									Name:   "example.com",
									Qtype:  dns.TypeNS,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.NS{
									Hdr: dns.RR_Header{
										Name:     "example.com",
										Rrtype:   dns.TypeNS,
										Class:    dns.ClassINET,
										Ttl:      30,
										Rdlength: uint16(len("ns1.example.com")),
									},
									Ns: "ns1.example.com",
								},
							},
							Ns:    []dns.RR{},
							Extra: []dns.RR{},
						},
					},
				},
				authoritativeServers: []string{"127.0.0.1"},
			},
			out: struct {
				ns  *dns.NS
				err error
			}{
				ns: &dns.NS{
					Hdr: dns.RR_Header{
						Name:     "example.com",
						Rrtype:   dns.TypeNS,
						Class:    dns.ClassINET,
						Ttl:      30,
						Rdlength: uint16(len("ns1.example.com")),
					},
					Ns: "ns1.example.com",
				},
			},
		},
		"NXDOMAIN": {
			in: struct {
				name                 string
				client               ResolverClient
				authoritativeServers []string
			}{
				name: "example.com",
				client: &mockClient{
					received: []*dns.Msg{
						{
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeNameError,
							},
							Question: []dns.Question{
								{
									Name:   "example.com",
									Qtype:  dns.TypeNS,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{},
							Ns:     []dns.RR{},
							Extra:  []dns.RR{},
						},
					},
				},
				authoritativeServers: []string{"127.0.0.1", "::1"},
			},
			out: struct {
				ns  *dns.NS
				err error
			}{
				err: ErrNoAnswer,
			},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			handler := NewRecursiveHandler(noopCache{})
			handler.client = tc.in.client

			ns, err := handler.getNS(tc.in.name, netip.MustParseAddr("127.0.0.1"))
			if err != nil {
				if tc.out.err != nil {
					assert.ErrorIs(t, tc.out.err, err)
				} else {
					t.Error(err)
				}
			}

			assert.Equal(t, ns, tc.out.ns)
		})
	}
}

func TestQueryAliasType(t *testing.T) {
	testcases := map[string]struct {
		in struct {
			query  *dns.Msg
			client ResolverClient
		}
		out *dns.Msg
	}{
		"valid": {
			in: struct {
				query  *dns.Msg
				client ResolverClient
			}{
				query: &dns.Msg{
					MsgHdr: dns.MsgHdr{
						Id:     1,
						Opcode: dns.OpcodeQuery,
					},
					Question: []dns.Question{
						{
							Name:   "www.example.com.",
							Qtype:  dns.TypeCNAME,
							Qclass: dns.ClassINET,
						},
					},
				},
				client: &mockClient{
					received: []*dns.Msg{
						{
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeNameError,
							},
							Question: []dns.Question{
								{
									Name:   "com.",
									Qtype:  dns.TypeCNAME,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{},
							Ns:     []dns.RR{},
							Extra:  []dns.RR{},
						},
						{
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeSuccess,
							},
							Question: []dns.Question{
								{
									Name:   "com.",
									Qtype:  dns.TypeA,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.A{
									Hdr: dns.RR_Header{
										Name:   "com.",
										Rrtype: dns.TypeA,
										Class:  dns.ClassINET,
										Ttl:    30,
									},
									A: net.ParseIP("10.0.0.1"),
								},
							},
							Ns:    []dns.RR{},
							Extra: []dns.RR{},
						},
						{
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeSuccess,
							},
							Question: []dns.Question{
								{
									Name:   "www.example.com.",
									Qtype:  dns.TypeCNAME,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.CNAME{
									Hdr: dns.RR_Header{
										Name:   "www.example.com.",
										Rrtype: dns.TypeCNAME,
										Class:  dns.ClassINET,
									},
									Target: "example.com.",
								},
							},
							Ns:    []dns.RR{},
							Extra: []dns.RR{},
						},
						{
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeNameError,
							},
							Question: []dns.Question{
								{
									Name:   "com.",
									Qtype:  dns.TypeCNAME,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{},
							Ns:     []dns.RR{},
							Extra:  []dns.RR{},
						},
						{
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeSuccess,
							},
							Question: []dns.Question{
								{
									Name:   "com.",
									Qtype:  dns.TypeA,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.A{
									Hdr: dns.RR_Header{
										Name:   "com.",
										Rrtype: dns.TypeA,
										Class:  dns.ClassINET,
										Ttl:    30,
									},
									A: net.ParseIP("10.0.0.1"),
								},
							},
							Ns:    []dns.RR{},
							Extra: []dns.RR{},
						},
						{
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeNameError,
							},
							Question: []dns.Question{
								{
									Name:   "example.com.",
									Qtype:  dns.TypeCNAME,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{},
							Ns:     []dns.RR{},
							Extra:  []dns.RR{},
						},
						{
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeNameError,
							},
							Question: []dns.Question{
								{
									Name:   "com.",
									Qtype:  dns.TypeCNAME,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{},
							Ns:     []dns.RR{},
							Extra:  []dns.RR{},
						},
						{
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeSuccess,
							},
							Question: []dns.Question{
								{
									Name:   "com.",
									Qtype:  dns.TypeA,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.A{
									Hdr: dns.RR_Header{
										Name:   "com.",
										Rrtype: dns.TypeA,
										Class:  dns.ClassINET,
										Ttl:    30,
									},
									A: net.ParseIP("10.0.0.1"),
								},
							},
							Ns:    []dns.RR{},
							Extra: []dns.RR{},
						},
						{
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeSuccess,
							},
							Question: []dns.Question{
								{
									Name:   "example.com.",
									Qtype:  dns.TypeA,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.A{
									Hdr: dns.RR_Header{
										Name:   "example.com.",
										Rrtype: dns.TypeA,
										Class:  dns.ClassINET,
									},
									A: net.ParseIP("10.0.0.1"),
								},
							},
							Ns:    []dns.RR{},
							Extra: []dns.RR{},
						},
					},
				},
			},
			out: &dns.Msg{
				MsgHdr: dns.MsgHdr{
					Id:       1,
					Opcode:   dns.OpcodeQuery,
					Response: true,
					Rcode:    dns.RcodeSuccess,
				},
				Question: []dns.Question{
					{
						Name:   "example.com.",
						Qtype:  dns.TypeA,
						Qclass: dns.ClassINET,
					},
				},
				Answer: []dns.RR{
					&dns.A{
						Hdr: dns.RR_Header{
							Name:   "example.com.",
							Rrtype: dns.TypeA,
							Class:  dns.ClassINET,
						},
						A: net.ParseIP("10.0.0.1"),
					},
				},
				Ns:    []dns.RR{},
				Extra: []dns.RR{},
			},
		},
		"loop": {
			in: struct {
				query  *dns.Msg
				client ResolverClient
			}{
				query: &dns.Msg{
					MsgHdr: dns.MsgHdr{
						Id:     1,
						Opcode: dns.OpcodeQuery,
					},
					Question: []dns.Question{
						{
							Name:   "www.example.com.",
							Qtype:  dns.TypeCNAME,
							Qclass: dns.ClassINET,
						},
					},
				},
				client: &mockClient{
					received: []*dns.Msg{
						{
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeNameError,
							},
							Question: []dns.Question{
								{
									Name:   "com.",
									Qtype:  dns.TypeCNAME,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{},
							Ns:     []dns.RR{},
							Extra:  []dns.RR{},
						}, {
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeSuccess,
							},
							Question: []dns.Question{
								{
									Name:   "com.",
									Qtype:  dns.TypeA,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.A{
									Hdr: dns.RR_Header{
										Name:   "com.",
										Rrtype: dns.TypeA,
										Class:  dns.ClassINET,
										Ttl:    30,
									},
									A: net.ParseIP("10.0.0.1"),
								},
							},
							Ns:    []dns.RR{},
							Extra: []dns.RR{},
						}, {
							MsgHdr: dns.MsgHdr{
								Id:     1,
								Opcode: dns.OpcodeQuery,
							},
							Question: []dns.Question{
								{
									Name:   "www.example.com.",
									Qtype:  dns.TypeCNAME,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.CNAME{
									Hdr: dns.RR_Header{
										Name:   "www.example.com.",
										Rrtype: dns.TypeCNAME,
										Class:  dns.ClassINET,
										Ttl:    30,
									},
									Target: "example.com",
								},
							},
							Ns:    []dns.RR{},
							Extra: []dns.RR{},
						}, {
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeNameError,
							},
							Question: []dns.Question{
								{
									Name:   "com.",
									Qtype:  dns.TypeCNAME,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{},
							Ns:     []dns.RR{},
							Extra:  []dns.RR{},
						}, {
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeSuccess,
							},
							Question: []dns.Question{
								{
									Name:   "com.",
									Qtype:  dns.TypeA,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.A{
									Hdr: dns.RR_Header{
										Name:   "com.",
										Rrtype: dns.TypeA,
										Class:  dns.ClassINET,
										Ttl:    30,
									},
									A: net.ParseIP("10.0.0.1"),
								},
							},
							Ns:    []dns.RR{},
							Extra: []dns.RR{},
						}, {
							MsgHdr: dns.MsgHdr{
								Id:       1,
								Opcode:   dns.OpcodeQuery,
								Response: true,
								Rcode:    dns.RcodeSuccess,
							},
							Question: []dns.Question{
								{
									Name:   "example.com.",
									Qtype:  dns.TypeCNAME,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.CNAME{
									Hdr: dns.RR_Header{
										Name:   "example.com.",
										Rrtype: dns.TypeCNAME,
										Class:  dns.ClassINET,
										Ttl:    30,
									},
									Target: "www.example.com.",
								},
							},
						},
					},
				},
			},
			out: &dns.Msg{
				MsgHdr: dns.MsgHdr{
					Id:       1,
					Opcode:   dns.OpcodeQuery,
					Response: true,
					Rcode:    dns.RcodeRefused,
				},
				Question: []dns.Question{
					{
						Name:   "www.example.com.",
						Qtype:  dns.TypeCNAME,
						Qclass: dns.ClassINET,
					},
				},
				Answer: []dns.RR{},
				Ns:     []dns.RR{},
				Extra:  []dns.RR{},
			},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			handler := NewRecursiveHandler(noopCache{})
			handler.client = tc.in.client
			handler.authoritativeServers = []netip.Addr{netip.MustParseAddr("127.0.0.1")}

			session := newSession(&net.UDPAddr{IP: net.ParseIP("10.0.0.2"), Port: 53})
			ns := &dns.NS{
				Hdr: dns.RR_Header{
					Name:   "com.",
					Rrtype: dns.TypeNS,
					Class:  dns.ClassINET,
					Ttl:    30,
				},
				Ns: "com.",
			}

			query := tc.in.query

			for {
				out, err := handler.queryAliasType(query, ns, session)
				if err != nil {
					t.Fatal(err)
				}

				switch out.Rcode {
				case dns.RcodeRefused:
					assert.Equal(t, tc.out, out)
					return
				case dns.RcodeNameError:
					if query.Question[0].Qtype == dns.TypeCNAME {
						query.Question[0].Qtype = dns.TypeA
						continue
					}

					t.Fatalf("unexpected NXDOMAIN %+v", out)
				case dns.RcodeSuccess:
					if query.Question[0].Qtype == dns.TypeCNAME {
						cname, ok := out.Answer[0].(*dns.CNAME)
						if !ok {
							t.Fatalf("expected to receive a cname, found %+v", out.Answer[0])
						}

						query.Question[0].Name = cname.Target
					} else {
						assert.Equal(t, tc.out, out)
						return
					}
				}
			}
		})
	}
}

func FuzzServeDNSQuestion(f *testing.F) {
	f.Add("example", uint16(5), uint16(1))

	handler := NewRecursiveHandler(noopCache{})
	handler.systemResolvers = &systemConfig{
		Nameservers: []netip.Addr{netip.MustParseAddr("127.0.0.1")},
	}
	handler.client = &mockClient{}

	f.Fuzz(func(t *testing.T, label string, qtype uint16, qclass uint16) {
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

		responseWriter := &mockResponseWriter{}

		handler.ServeDNS(responseWriter, msg)

		assert.GreaterOrEqual(t, len(responseWriter.sent), 1)
	})
}
