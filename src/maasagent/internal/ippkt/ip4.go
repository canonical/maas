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
	"encoding/binary"
	"errors"
	"net"
)

var (
	ErrMalformedIPv4Pkt = errors.New("malformed IPv4 packet")
)

type IPProtocol uint8

const (
	IPProtocolICMPv4   IPProtocol = 1
	IPProtocolIGMP     IPProtocol = 2
	IPProtocolIPv4     IPProtocol = 4
	IPProtocolTCP      IPProtocol = 6
	IPProtocolUDP      IPProtocol = 17
	IPProtocolRUDP     IPProtocol = 27
	IPProtocolGRE      IPProtocol = 47
	IPProtocolESP      IPProtocol = 50
	IPProtocolAH       IPProtocol = 51
	IPProtocolOSPF     IPProtocol = 89
	IPProtocolIPIP     IPProtocol = 94
	IPProtocolEtherIP  IPProtocol = 97
	IPProtocolVRRP     IPProtocol = 112
	IPProtocolSCTP     IPProtocol = 132
	IPProtocolUDPLite  IPProtocol = 136
	IPProtocolMPLSInIP IPProtocol = 137
)

// IPv4Flag implements rfc3514
type IPv4Flag uint8

const (
	IPv4FlagEvilBit       IPv4Flag = 1 << 2
	IPv4FlagDontFragment  IPv4Flag = 1 << 1
	IPv4FlagMoreFragments IPv4Flag = 1 << 0
)

type IPv4Option struct {
	Data []byte
	Type uint8
	Len  uint8
}

type IPv4Header struct {
	SrcIP      net.IP
	Options    []IPv4Option
	DstIP      net.IP
	FragOffset uint16
	Id         uint16
	Checksum   uint16
	Length     uint16
	Flags      IPv4Flag
	Version    uint8
	TTL        uint8
	Protocol   IPProtocol
	TOS        uint8
	IHL        uint8
}

func (i *IPv4Header) UnmarshalBinary(b []byte) error {
	if len(b) < 20 {
		return ErrMalformedIPv4Pkt
	}

	flags := binary.BigEndian.Uint16(b[6:8])

	i.Version = uint8(b[0]) >> 4
	i.IHL = uint8(b[0]) & 0x0f
	i.TOS = b[1]
	i.Length = binary.BigEndian.Uint16(b[2:4])
	i.Id = binary.BigEndian.Uint16(b[4:6])
	i.Flags = IPv4Flag(flags >> 13)
	i.FragOffset = flags & 0x1fff
	i.TTL = b[8]
	i.Protocol = IPProtocol(b[9])
	i.Checksum = binary.BigEndian.Uint16(b[10:12])
	i.SrcIP = b[12:16]
	i.DstIP = b[16:20]

	if i.Length == 0 {
		i.Length = uint16(len(b))
	}

	if i.Length < 20 || i.IHL < 5 || int(i.IHL*4) > int(i.Length) {
		return ErrMalformedIPv4Pkt
	}

	if len(b)-int(i.Length) > 0 {
		b = b[:i.Length]
	}

	b = b[20 : i.IHL*4]

	for len(b) > 0 {
		if i.Options == nil {
			i.Options = make([]IPv4Option, 0, 4)
		}

		opt := IPv4Option{Type: b[0]}

		switch opt.Type {
		case 0: // end
			opt.Len = 1
			i.Options = append(i.Options, opt)

			return nil
		case 1: // padding
			opt.Len = 1
			b = b[1:]

			i.Options = append(i.Options, opt)
		default:
			if len(b) < 1 {
				return ErrMalformedIPv4Pkt
			}

			opt.Len = b[1]

			if len(b) < int(opt.Len) || opt.Len <= 2 {
				return ErrMalformedIPv4Pkt
			}

			opt.Data = b[2:opt.Len]
			b = b[opt.Len:]
			i.Options = append(i.Options, opt)
		}
	}

	return nil
}

func checksum(b []byte) uint16 {
	b[10] = 0
	b[11] = 0

	var csum uint32
	for i := 0; i < len(b); i += 2 {
		csum += uint32(b[i]) << 8
		csum += uint32(b[i+1])
	}

	for csum > 65535 {
		// add carry
		csum = (csum >> 16) + uint32(uint16(csum))
	}

	// flip all the bits
	return ^uint16(csum)
}

func (i *IPv4Header) optLength() int {
	var length int

	for _, opt := range i.Options {
		length += int(opt.Len)
	}

	return length
}

func (i *IPv4Header) MarshalBinary() ([]byte, error) {
	if i.Version == 0 {
		i.Version = 4
	}

	hdrLen := uint16(20 + i.optLength())
	if i.Length == 0 {
		i.Length = hdrLen
	}

	buf := make([]byte, hdrLen)

	if i.IHL == 0 {
		i.IHL = uint8(i.Length / 4)
	}

	buf[0] = (i.Version << 4) | i.IHL
	buf[1] = i.TOS
	binary.BigEndian.PutUint16(buf[2:4], i.Length)
	binary.BigEndian.PutUint16(buf[4:6], i.Id)

	var flagFrags uint16

	flagFrags |= uint16(i.Flags) << 13
	flagFrags |= i.FragOffset
	binary.BigEndian.PutUint16(buf[6:8], flagFrags)

	buf[8] = i.TTL
	buf[9] = byte(i.Protocol)

	copy(buf[12:16], i.SrcIP.To4())
	copy(buf[16:20], i.DstIP.To4())

	idx := 20

	for _, opt := range i.Options {
		switch opt.Type {
		case 0: // end
			buf[idx] = 0
			idx++
		case 1:
			buf[idx] = 1
			idx++
		default:
			buf[idx] = opt.Type
			buf[idx+1] = opt.Len

			if len(opt.Data) > int(opt.Len) {
				return nil, ErrMalformedIPv4Pkt
			}

			copy(buf[idx+2:idx+int(opt.Len)], opt.Data)
			idx += int(opt.Len)
		}
	}

	i.Checksum = checksum(buf)

	binary.BigEndian.PutUint16(buf[10:12], i.Checksum)

	return buf, nil
}
