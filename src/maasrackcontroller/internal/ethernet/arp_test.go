// Copyright (c) 2023-2024 Canonical Ltd
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

package ethernet

import (
	"io"
	"net/netip"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestUnmarshal(t *testing.T) {
	t.Parallel()

	testcases := map[string]struct {
		in  []byte
		out *ARPPacket
		err error
	}{
		"valid request packet": {
			in: []byte{
				0x00, 0x01, 0x08, 0x00, 0x06, 0x04, 0x00, 0x01, 0x84, 0x39, 0xc0, 0x0b, 0x22, 0x25,
				0xc0, 0xa8, 0x0a, 0x1a, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xc0, 0xa8, 0x0a, 0x19,
			},
			out: &ARPPacket{
				HardwareType:    HardwareTypeEthernet,
				ProtocolType:    ProtocolTypeIPv4,
				HardwareAddrLen: 6,
				ProtocolAddrLen: 4,
				OpCode:          OpRequest,
				SendHwAddr:      []byte{0x84, 0x39, 0xc0, 0x0b, 0x22, 0x25},
				SendIPAddr:      netip.MustParseAddr("192.168.10.26"),
				TgtHwAddr:       []byte{0x00, 0x00, 0x00, 0x00, 0x00, 0x0},
				TgtIPAddr:       netip.MustParseAddr("192.168.10.25"),
			},
		},
		"valid reply packet": {
			in: []byte{
				0x00, 0x01, 0x08, 0x00, 0x06, 0x04, 0x00, 0x02, 0x80, 0x61, 0x5f, 0x08, 0xfc, 0x16,
				0xc0, 0xa8, 0x01, 0x6c, 0x24, 0x4b, 0xfe, 0xe1, 0xea, 0x26, 0xc0, 0xa8, 0x01, 0x50,
			},
			out: &ARPPacket{
				HardwareType:    HardwareTypeEthernet,
				ProtocolType:    ProtocolTypeIPv4,
				HardwareAddrLen: 6,
				ProtocolAddrLen: 4,
				OpCode:          OpReply,
				SendHwAddr:      []byte{0x80, 0x61, 0x5f, 0x08, 0xfc, 0x16},
				SendIPAddr:      netip.MustParseAddr("192.168.1.108"),
				TgtHwAddr:       []byte{0x24, 0x4b, 0xfe, 0xe1, 0xea, 0x26},
				TgtIPAddr:       netip.MustParseAddr("192.168.1.80"),
			},
		},
		"empty packet": {
			err: io.ErrUnexpectedEOF,
		},
		"too stort packet": {
			in: []byte{
				0x00, 0x01, 0x08, 0x00, 0x06, 0x04, 0x00, 0x01, 0x84, 0x39, 0xc0, 0x0b, 0x22, 0x25,
				0xc0, 0xa8,
			},
			err: ErrMalformedARPPacket,
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			res := &ARPPacket{}

			err := res.UnmarshalBinary(tc.in)
			assert.ErrorIs(t, err, tc.err)

			if err == nil {
				assert.Equal(t, tc.out, res)
			}
		})
	}
}
