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

	"golang.org/x/net/ipv4"
	"golang.org/x/net/ipv6"
	"golang.org/x/sys/unix"
)

type IPVersion int

const (
	IPv4 IPVersion = unix.AF_INET
	IPv6 IPVersion = unix.AF_INET6
)

type Socket interface {
	IfaceIdx() int
	IPVersion() IPVersion
	Conn() net.PacketConn
	Close() error
}

func NewIPv4Socket(conn net.PacketConn, ifaceName string, ifaceIdx int) Socket {
	return &socketImpl[*ipv4.PacketConn]{
		conn:      conn,
		protoConn: ipv4.NewPacketConn(conn),
		ifaceName: ifaceName,
		ifaceIdx:  ifaceIdx,
		ipVer:     IPv4,
	}
}

func NewIPv6Socket(conn net.PacketConn, ifaceName string, ifaceIdx int) Socket {
	return &socketImpl[*ipv6.PacketConn]{
		conn:      conn,
		protoConn: ipv6.NewPacketConn(conn),
		ifaceName: ifaceName,
		ifaceIdx:  ifaceIdx,
		ipVer:     IPv6,
	}
}

type socketImpl[T interface{ Close() error }] struct {
	conn      net.PacketConn
	protoConn T
	ifaceName string
	ifaceIdx  int
	ipVer     IPVersion
}

func (s *socketImpl[T]) IfaceIdx() int        { return s.ifaceIdx }
func (s *socketImpl[T]) IPVersion() IPVersion { return s.ipVer }
func (s *socketImpl[T]) Conn() net.PacketConn { return s.conn }
func (s *socketImpl[T]) Close() error         { return s.protoConn.Close() }
