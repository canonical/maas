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
	"os"

	"golang.org/x/sys/unix"
)

const (
	dhcpPort = 67
)

// newDHCP4Conn creates a net.PacketConn for DHCP use. While given MAAS' reference architecture,
// having the DHCP server only listen on unicast and then only using relays on broadcast, is unusual, this
// is a common enough practice in the general case to make broadcast optional
func newDHCP4Conn(iface *net.Interface, broadcast bool) (net.PacketConn, error) {
	fd, err := unix.Socket(unix.AF_INET, unix.SOCK_DGRAM, unix.IPPROTO_UDP)
	if err != nil {
		return nil, err
	}

	f := os.NewFile(uintptr(fd), "")

	// net.FilePacketConn duplicates the FD, so we can close this one when we're done with it
	defer f.Close() //nolint:errcheck // ignoring deferred close error

	if broadcast {
		err = unix.SetsockoptInt(fd, unix.SOL_SOCKET, unix.SO_BROADCAST, 1)
		if err != nil {
			return nil, err
		}
	}

	err = unix.BindToDevice(fd, iface.Name)
	if err != nil {
		return nil, err
	}

	saddr := unix.SockaddrInet4{
		Port: dhcpPort,
	}

	err = unix.Bind(fd, &saddr)
	if err != nil {
		return nil, err
	}

	return net.FilePacketConn(f)
}

// newDHCP6Conn creates a net.PacketConn for DHCP6 use. Like newDHCP4Conn, broadcast is optional
// in the event only relays will handle broadcast.
func newDHCP6Conn(iface *net.Interface, broadcast bool) (net.PacketConn, error) {
	fd, err := unix.Socket(unix.AF_INET6, unix.SOCK_DGRAM, unix.IPPROTO_UDP)
	if err != nil {
		return nil, err
	}

	f := os.NewFile(uintptr(fd), "")

	// net.FilePacketConn duplicates the FD, so we can close this one when we're done with it
	defer f.Close() //nolint:errcheck // ignoring deferred close error

	if broadcast {
		err = unix.SetsockoptInt(fd, unix.IPPROTO_IPV6, unix.IPV6_V6ONLY, 1)
		if err != nil {
			return nil, err
		}
	}

	err = unix.BindToDevice(fd, iface.Name)
	if err != nil {
		return nil, err
	}

	saddr := unix.SockaddrInet6{
		Port: dhcpPort,
	}

	err = unix.Bind(fd, &saddr)
	if err != nil {
		return nil, err
	}

	return net.FilePacketConn(f)
}
