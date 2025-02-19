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
	"os"
	"testing"

	"github.com/stretchr/testify/assert"
)

type parsedResolvConf struct {
	expectedCfg *systemConfig
	err         error
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
		"valid with values ignored": {
			in: `nameserver 127.0.0.53
options edns0 trust-ad
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
