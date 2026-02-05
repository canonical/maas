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
	"fmt"
	"net/netip"
)

// IPv4ToInt converts an IPv4 to an int.
//
// If ip does not correspond to IPv4, returns an error.
func IPv4ToInt(ip netip.Addr) (uint32, error) {
	if !ip.Is4() {
		return 0, fmt.Errorf("%v is not an IPv4", ip)
	}

	slice := ip.As4()

	return binary.BigEndian.Uint32(slice[:]), nil
}

// IntToIPv4 converts an int to an IPv4.
func IntToIPv4(ip uint32) netip.Addr {
	var bytes [4]byte

	binary.BigEndian.PutUint32(bytes[:], ip)

	return netip.AddrFrom4(bytes)
}

// Uint128 encapsulates a 128-bit unsigned integer.
//
// Useful since Go does not have a built-in type for this.
type Uint128 struct {
	bytes [16]byte
}

// Uint64sToUint128 concatenates two uint64s in big endian format.
func Uint64sToUint128(a, b uint64) Uint128 {
	var bytes [16]byte

	binary.BigEndian.PutUint64(bytes[0:8], a)
	binary.BigEndian.PutUint64(bytes[8:16], b)

	return Uint128{bytes}
}

// Uint128ToUint64s splits an Uint128 in 2 uint64s according to big endian.
func Uint128ToUint64s(x Uint128) (uint64, uint64) {
	return binary.BigEndian.Uint64(x.bytes[0:8]), binary.BigEndian.Uint64(x.bytes[8:16])
}

// IPv6ToInt converts an IPv6 to an Uint128
//
// Returns an error in case the ip is not an IPv6, e.g. if
// it is an IPv4.
func IPv6ToInt(ip netip.Addr) (Uint128, error) {
	if !ip.Is6() {
		return Uint128{}, fmt.Errorf("%v is not an IPv6", ip)
	}

	return Uint128{ip.As16()}, nil
}

// IntToIPv6 converts an Uint128 to an IPv6
func IntToIPv6(ip Uint128) netip.Addr {
	return netip.AddrFrom16(ip.bytes)
}
