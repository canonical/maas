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
	"encoding/binary"
	"net"
)

// SendMode specifies how a DHCP reply should be delivered.
type SendMode int

const (
	// SendUnicast replies via UDP unicast to the client's IP (port 68)
	// Typically used when ciaddr is set or the client can receive directed traffic
	SendUnicast SendMode = 1
	// SendBroadcast replies via UDP broadcast (255.255.255.255:68)
	// Used when ciaddr is 0.0.0.0 and the client set the broadcast flag
	SendBroadcast SendMode = 2
	// SendRelay replies via UDP unicast to the relay agent's giaddr (port 67)
	// Used when the request arrived through a relay
	SendRelay SendMode = 3
	// SendL2 replies as a raw Ethernet frame to the client's MAC address.
	// Used when ciaddr is 0.0.0.0 and the broadcast flag is not set
	SendL2 SendMode = 4
)

// Message is an envelope that is passed by the Server receivers to the Handler
// SrcMAC, SrcIP and SrcPort might be used in the Relay situation, to protect
// against forged IPs (e.g. if SrcIP != giaddr) and more...
type Message struct {
	SrcMAC   net.HardwareAddr
	SrcIP    net.IP
	Payload  []byte
	IfaceIdx uint32
	Family   AddressFamily
	SrcPort  uint16
}

// MarshalBinary encodes the Message into a binary representation
func (m *Message) MarshalBinary() ([]byte, error) {
	buf := make([]byte, 4+2+6+16+2+len(m.Payload))
	idx := 0

	n, err := binary.Encode(buf[idx:idx+4], binary.LittleEndian, m.IfaceIdx)
	if err != nil {
		return nil, err
	}

	idx += n

	n, err = binary.Encode(buf[idx:idx+2], binary.LittleEndian, m.Family)
	if err != nil {
		return nil, err
	}

	idx += n

	copy(buf[idx:idx+6], m.SrcMAC[:])
	idx += 6

	_, err = binary.Encode(buf[idx:idx+16], binary.LittleEndian, m.SrcIP)
	if err != nil {
		return nil, err
	}

	idx += 16

	n, err = binary.Encode(buf[idx:idx+2], binary.LittleEndian, m.SrcPort)
	if err != nil {
		return nil, err
	}

	idx += n

	copy(buf[idx:], m.Payload)

	return buf, nil
}

// UnmarshalBinary parses a raw binary data into the Message struct
// Binary data format comes from the XDP program
func (m *Message) UnmarshalBinary(data []byte) error {
	idx := 0

	n, err := binary.Decode(data[idx:idx+4], binary.LittleEndian, &m.IfaceIdx)
	if err != nil {
		return err
	}

	idx += n

	n, err = binary.Decode(data[idx:idx+2], binary.LittleEndian, &m.Family)
	if err != nil {
		return err
	}

	idx += n
	m.SrcMAC = net.HardwareAddr(data[idx : idx+6])
	idx += 6

	m.SrcIP = data[idx : idx+16]
	idx += 16

	n, err = binary.Decode(data[idx:idx+2], binary.LittleEndian, &m.SrcPort)
	if err != nil {
		return err
	}

	idx += n

	m.Payload = data[idx:]

	return nil
}

type Response struct {
	SrcAddress net.UDPAddr
	DstAddress net.UDPAddr
	DstMAC     net.HardwareAddr
	Payload    []byte
	Mode       SendMode
	IfaceIdx   int
}
