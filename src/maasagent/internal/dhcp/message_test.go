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

package dhcp

import (
	"net"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"golang.org/x/sys/unix"
)

func TestMarshalUnmarshalBinary(t *testing.T) {
	orig := Message{
		IfaceIdx: 42,
		Family:   AddressFamily(unix.AF_INET),
		SrcMAC:   net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
		SrcIP:    net.IPv4(192, 168, 1, 11),
		SrcPort:  1337,
		Payload:  []byte("hello world"),
	}

	data, err := orig.MarshalBinary()
	require.NoError(t, err)

	t.Log(data)

	var decoded Message

	err = decoded.UnmarshalBinary(data)
	require.NoError(t, err)

	assert.Equal(t, orig, decoded)
}
