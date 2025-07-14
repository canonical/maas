// Copyright (c) \d{4}(-\d{4})? Canonical Ltd
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

package ippkt

import (
	"net"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestIPv4HeaderUnmarshalBinary(t *testing.T) {
	testcases := map[string]struct {
		in  []byte
		out IPv4Header
		err error
	}{
		"basic": {
			in: []byte{
				0x45, 0x00, 0x01, 0x77,
				0x34, 0x29, 0x00, 0x00,
				0x40, 0x11, 0x45, 0x4e,
				0x00, 0x00, 0x00, 0x00,
				0xff, 0xff, 0xff, 0xff,
			},
			out: IPv4Header{
				Version:  4,
				IHL:      5,
				Length:   375,
				Id:       13353,
				TTL:      64,
				Checksum: 0x454e,
				Protocol: IPProtocolUDP,
				SrcIP:    net.ParseIP("0.0.0.0").To4(),
				DstIP:    net.ParseIP("255.255.255.255").To4(),
			},
		},
		"too short": {
			in:  []byte{},
			err: ErrMalformedIPv4Pkt,
		},
	}

	for tname, tc := range testcases {
		t.Run(tname, func(t *testing.T) {
			hdr := &IPv4Header{}

			err := hdr.UnmarshalBinary(tc.in)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, *hdr, tc.out)
		})
	}
}

func TestIPv4HeaderMarshalBinary(t *testing.T) {
	testcases := map[string]struct {
		in  *IPv4Header
		out []byte
	}{
		"basic": {
			in: &IPv4Header{
				Version:  4,
				IHL:      5,
				Length:   375,
				Id:       13353,
				TTL:      64,
				Checksum: 0x454e,
				Protocol: IPProtocolUDP,
				SrcIP:    net.ParseIP("0.0.0.0").To4(),
				DstIP:    net.ParseIP("255.255.255.255").To4(),
			},
			out: []byte{
				0x45, 0x00, 0x01, 0x77,
				0x34, 0x29, 0x00, 0x00,
				0x40, 0x11, 0x45, 0x4e,
				0x00, 0x00, 0x00, 0x00,
				0xff, 0xff, 0xff, 0xff,
			},
		},
		"sets defaults": {
			in: &IPv4Header{
				Id:       13353,
				TTL:      64,
				Protocol: IPProtocolUDP,
				SrcIP:    net.ParseIP("0.0.0.0").To4(),
				DstIP:    net.ParseIP("255.255.255.255").To4(),
			},
			out: []byte{
				0x45, 0x00, 0x00, 0x14,
				0x34, 0x29, 0x00, 0x00,
				0x40, 0x11, 0x46, 0xb1,
				0x00, 0x00, 0x00, 0x00,
				0xff, 0xff, 0xff, 0xff,
			},
		},
	}

	for tname, tc := range testcases {
		t.Run(tname, func(t *testing.T) {
			out, err := tc.in.MarshalBinary()
			if err != nil {
				t.Fatal(err)
			}

			assert.Equal(t, out, tc.out)
		})
	}
}
