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

			handler := NewRecursiveHandler()

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

			handler := NewRecursiveHandler()

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

	handler := NewRecursiveHandler()

	responseWriter := &mockResponseWriter{}

	handler.srvFailResponse(responseWriter, in)

	assert.Equal(t, expectedOut, responseWriter.sent[0])
}

func TestServeDNS(t *testing.T) {
	testcases := map[string]struct {
		in struct {
			msg    *dns.Msg
			client ResolverClient
			config *systemConfig
		}
		out struct {
			sent     []*dns.Msg
			received []*dns.Msg
		}
	}{
		"basic non-authoritative": {
			in: struct {
				msg    *dns.Msg
				client ResolverClient
				config *systemConfig
			}{
				msg: &dns.Msg{
					MsgHdr: dns.MsgHdr{
						Id:               1,
						Opcode:           dns.OpcodeQuery,
						RecursionDesired: true,
					},
					Question: []dns.Question{
						{
							Name:   "example.com",
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
									Name:   "example.com",
									Qtype:  dns.TypeA,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.A{
									Hdr: dns.RR_Header{
										Name:     "example.com",
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
								Name:   "example.com",
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
							Rcode:            dns.RcodeSuccess,
						},
						Question: []dns.Question{
							{
								Name:   "example.com",
								Qtype:  dns.TypeA,
								Qclass: dns.ClassINET,
							},
						},
						Answer: []dns.RR{
							&dns.A{
								Hdr: dns.RR_Header{
									Name:     "example.com",
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
				msg    *dns.Msg
				client ResolverClient
				config *systemConfig
			}{
				msg: &dns.Msg{
					MsgHdr: dns.MsgHdr{
						Id:               1,
						Opcode:           dns.OpcodeQuery,
						RecursionDesired: true,
					},
					Question: []dns.Question{
						{
							Name:   "example",
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
									Name:   "example",
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
									Name:   "example.test",
									Qtype:  dns.TypeA,
									Qclass: dns.ClassINET,
								},
							},
							Answer: []dns.RR{
								&dns.A{
									Hdr: dns.RR_Header{
										Name:     "example.test",
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
								Name:   "example",
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
							Id:               1,
							Opcode:           dns.OpcodeQuery,
							RecursionDesired: true,
							Response:         true,
							Rcode:            dns.RcodeSuccess,
						},
						Question: []dns.Question{
							{
								Name:   "example",
								Qtype:  dns.TypeA,
								Qclass: dns.ClassINET,
							},
						},
						Answer: []dns.RR{
							&dns.A{
								Hdr: dns.RR_Header{
									Name:     "example.test",
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
		"nxdomain": {
			in: struct {
				msg    *dns.Msg
				client ResolverClient
				config *systemConfig
			}{
				msg: &dns.Msg{
					MsgHdr: dns.MsgHdr{
						Id:               1,
						Opcode:           dns.OpcodeQuery,
						RecursionDesired: true,
					},
					Question: []dns.Question{
						{
							Name:   "example.com",
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
									Name:   "example.com",
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
								Name:   "example.com",
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
							Rcode:            dns.RcodeNameError,
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
					},
				},
			},
		},
		"client error": {
			in: struct {
				msg    *dns.Msg
				client ResolverClient
				config *systemConfig
			}{
				msg: &dns.Msg{
					MsgHdr: dns.MsgHdr{
						Id:               1,
						Opcode:           dns.OpcodeQuery,
						RecursionDesired: true,
					},
					Question: []dns.Question{
						{
							Name:   "example.com",
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
								Name:   "example.com",
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
								Name:   "example.com",
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
			handler := NewRecursiveHandler()
			handler.systemResolvers = tc.in.config
			handler.client = tc.in.client

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

func FuzzServeDNSQuestion(f *testing.F) {
	f.Add("example", uint16(5), uint16(1))

	handler := NewRecursiveHandler()
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
