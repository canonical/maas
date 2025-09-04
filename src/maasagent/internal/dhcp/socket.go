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

	"golang.org/x/net/ipv4"
	"golang.org/x/net/ipv6"
	"golang.org/x/sys/unix"
	"maas.io/core/src/maasagent/internal/netutil"
)

const (
	dhcpV4Port = 67
	dhcpV6Port = 547
)

func newDHCPV4Conn(iface *net.Interface) (net.PacketConn, error) {
	return newDHCPConn(
		iface,
		unix.AF_INET,
		&unix.SockaddrInet4{Port: dhcpV4Port},
		func(fd int) error {
			// SO_BROADCAST allows broadcast datagrams to be sent from this socket
			return unix.SetsockoptInt(fd, unix.SOL_SOCKET, unix.SO_BROADCAST, 1)
		},
	)
}

func newDHCPV6Conn(iface *net.Interface) (net.PacketConn, error) {
	return newDHCPConn(
		iface,
		unix.AF_INET6,
		&unix.SockaddrInet6{Port: dhcpV6Port},
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
		return nil, err
	}

	f := os.NewFile(uintptr(fd), "")

	// newDHCPConn returns net.FilePacketConn which duplicates the file:
	// > FilePacketConn returns a copy of the packet network connection
	// > corresponding to the open file f
	defer f.Close() //nolint:errcheck // ignoring deferred close error

	if fn != nil {
		if err := fn(fd); err != nil {
			return nil, err
		}
	}

	if err := unix.BindToDevice(fd, iface.Name); err != nil {
		return nil, err
	}

	if err := unix.Bind(fd, sockaddr); err != nil {
		return nil, err
	}

	return net.FilePacketConn(f)
}

// AddressFamily is a type-safe wrapper for AF_*
type AddressFamily uint16

func (af AddressFamily) String() string {
	switch af {
	case unix.AF_INET:
		return "IPv4"
	case unix.AF_INET6:
		return "IPv6"
	default:
		return fmt.Sprintf("AddressFamily(%d)", af)
	}
}

type Socket interface {
	AddressFamily() AddressFamily
	Iface() *net.Interface
	Conn() net.PacketConn
	Close() error
	IsWriteOnly() bool
}

func NewIPv4Socket(iface *net.Interface, xdpAttached bool) (Socket, error) {
	return newIPvXSocket(
		iface,
		AddressFamily(unix.AF_INET),
		netutil.IfaceHasIPv4,
		newDHCPV4Conn,
		ipv4.NewPacketConn,
	)
}

func NewIPv6Socket(iface *net.Interface, xdpAttached bool) (Socket, error) {
	return newIPvXSocket(
		iface,
		AddressFamily(unix.AF_INET6),
		netutil.IfaceHasIPv6,
		newDHCPV6Conn,
		ipv6.NewPacketConn,
	)
}

type socketImpl[T interface{ Close() error }] struct {
	conn          net.PacketConn
	protoConn     T
	iface         *net.Interface
	addressFamily AddressFamily
	writeOnly     bool
}

func (s *socketImpl[T]) AddressFamily() AddressFamily { return s.addressFamily }
func (s *socketImpl[T]) Iface() *net.Interface        { return s.iface }
func (s *socketImpl[T]) Conn() net.PacketConn         { return s.conn }
func (s *socketImpl[T]) IsWriteOnly() bool            { return s.writeOnly }

// Close closes the protocol-specific connection, which in turn
// closes the underlying net.PacketConn/socket FD.
func (s *socketImpl[T]) Close() error { return s.protoConn.Close() }

// newIPvXSocket is the shared constructor for both IPv4 and IPv6 sockets.
// Callers plug in the family-specific "has address" check, connection builder,
// and protocol-specific wrapper (ipv4.NewPacketConn / ipv6.NewPacketConn)
func newIPvXSocket[T interface{ Close() error }](
	iface *net.Interface,
	family AddressFamily,
	hasIPvX func(*net.Interface) (bool, error),
	newConn func(*net.Interface) (net.PacketConn, error),
	newProtoConn func(net.PacketConn) T,
) (Socket, error) {
	has, err := hasIPvX(iface)
	if err != nil {
		return nil, fmt.Errorf("checking %s on %s: %w", family, iface.Name, err)
	}

	if !has {
		return nil, fmt.Errorf("checking %s on %s: not configured", family, iface.Name)
	}

	conn, err := newConn(iface)
	if err != nil {
		return nil, fmt.Errorf("creating %s connection on %s: %w", family, iface.Name, err)
	}

	return &socketImpl[T]{
		iface:         iface,
		conn:          conn,
		protoConn:     newProtoConn(conn),
		addressFamily: family,
	}, nil
}
