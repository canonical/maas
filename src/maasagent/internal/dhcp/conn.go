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
	"fmt"
	"net"
	"os"

	"golang.org/x/sys/unix"
)

const (
	dhcp4Port = 67
	dhcp6Port = 547
)

func newDHCP4Conn(iface *net.Interface) (net.PacketConn, error) {
	return newDHCPConn(
		iface,
		unix.AF_INET,
		&unix.SockaddrInet4{Port: dhcp4Port},
		func(fd int) error {
			// SO_BROADCAST allows broadcast datagrams to be sent from this socket
			return unix.SetsockoptInt(fd, unix.SOL_SOCKET, unix.SO_BROADCAST, 1)
		},
	)
}

func newDHCP6Conn(iface *net.Interface) (net.PacketConn, error) {
	return newDHCPConn(
		iface,
		unix.AF_INET6,
		&unix.SockaddrInet6{Port: dhcp6Port},
		func(fd int) error {
			// Restrict socket to IPv6 traffic only
			return unix.SetsockoptInt(fd, unix.IPPROTO_IPV6, unix.IPV6_V6ONLY, 1)
		},
	)
}

// newDHCPConn creates a bound UDP socket on the given interface
func newDHCPConn(iface *net.Interface, af int, sockaddr unix.Sockaddr,
	fn func(fd int) error,
) (net.PacketConn, error) {
	fd, err := unix.Socket(af, unix.SOCK_DGRAM, unix.IPPROTO_UDP)
	if err != nil {
		return nil, fmt.Errorf("failed opening DHCP socket: %w", err)
	}

	f := os.NewFile(uintptr(fd), "")

	// newDHCPConn returns net.FilePacketConn which duplicates the file:
	// > FilePacketConn returns a copy of the packet network connection
	// > corresponding to the open file f.so
	defer f.Close() //nolint:errcheck // ignoring deferred close error

	if fn != nil {
		if err := fn(fd); err != nil {
			return nil, err
		}
	}

	if err := unix.BindToDevice(fd, iface.Name); err != nil {
		return nil, fmt.Errorf("failed to bind to interface: %w", err)
	}

	if err := unix.Bind(fd, sockaddr); err != nil {
		return nil, fmt.Errorf("failed to bind to sockaddr %s: %w", sockaddr, err)
	}

	return net.FilePacketConn(f)
}
