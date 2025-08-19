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
	"context"
	"encoding/binary"
	"errors"
	"net"
	"runtime"
	"sync"

	"github.com/cilium/ebpf/link"
	"github.com/cilium/ebpf/ringbuf"
	"github.com/insomniacslk/dhcp/dhcpv4"
	"github.com/insomniacslk/dhcp/dhcpv6"
	"github.com/rs/zerolog/log"
	"golang.org/x/net/ipv4"
	"golang.org/x/net/ipv6"
	"golang.org/x/sync/semaphore"

	"maas.io/core/src/maasagent/internal/dhcp/xdp"
)

const (
	maxDHCPPktSize = 1500
)

var bufPool = &sync.Pool{
	New: func() any {
		return make([]byte, maxDHCPPktSize)
	},
}

var (
	ErrInvalidBuffer = errors.New("invalid buffer received from pool")
	ErrNoSocketFound = errors.New("no dhcp socket found for IP version and interface")
)

type Handler4 interface {
	ServeDHCP4(context.Context, Message) error
}

type Handler6 interface {
	ServeDHCP6(context.Context, Message) error
}

type socket interface {
	IfaceIdx() int
	Conn() net.PacketConn
	Close() error
}

type socket4 struct {
	conn       net.PacketConn
	pktConn    *ipv4.PacketConn
	ifaceName  string
	ifaceIndex int
}

func (s *socket4) IfaceIdx() int {
	return s.ifaceIndex
}

func (s *socket4) Conn() net.PacketConn {
	return s.conn
}

func (s *socket4) Close() error {
	return s.pktConn.Close()
}

type socket6 struct {
	conn       net.PacketConn
	pktConn    *ipv6.PacketConn
	ifaceName  string
	ifaceIndex int
}

func (s *socket6) IfaceIdx() int {
	return s.ifaceIndex
}

func (s *socket6) Conn() net.PacketConn {
	return s.conn
}

func (s *socket6) Close() error {
	return s.pktConn.Close()
}

type Message struct {
	Pkt6     dhcpv6.DHCPv6
	Pkt4     *dhcpv4.DHCPv4
	SrcMAC   net.HardwareAddr
	SrcIP    net.IP
	IfaceIdx uint32
	SrcPort  uint16
}

type Server struct {
	handler4 Handler4
	handler6 Handler6
	xdpProg  *xdp.Program
	inflight *semaphore.Weighted
	links    []link.Link
	sockets  []socket
	ifaces   []*net.Interface
}

func NewServer(ifaces []string, xdpProg *xdp.Program, h4 Handler4, h6 Handler6) (*Server, error) {
	var err error

	netIfaces := make([]*net.Interface, len(ifaces))

	for i, iface := range ifaces {
		netIfaces[i], err = net.InterfaceByName(iface)
		if err != nil {
			return nil, err
		}
	}

	s := &Server{
		xdpProg:  xdpProg,
		ifaces:   netIfaces,
		inflight: semaphore.NewWeighted(1024), // TODO make this configurable
		handler4: h4,
		handler6: h6,
	}

	err = s.Listen()
	if err != nil {
		return nil, err
	}

	if s.xdpProg != nil {
		err = s.attachDHCPXDP(xdpProg)
		if err != nil {
			// TODO check if eBPF is disabled, if so, ignore and rely directly on the connections
			return nil, err
		}
	}

	return s, nil
}

func (s *Server) GetSocketFor(ipVersion int, ifaceIdx int) (socket, error) {
	for _, sock := range s.sockets {
		if sock.IfaceIdx() == ifaceIdx {
			if _, ok := sock.(*socket4); ok && ipVersion == 4 {
				return sock, nil
			} else if _, ok := sock.(*socket6); ok && ipVersion == 6 {
				return sock, nil
			}
		}
	}

	return nil, ErrNoSocketFound
}

func (s *Server) listen4(iface *net.Interface) error {
	conn, err := newDHCP4Conn(iface)
	if err != nil {
		return err
	}

	s.sockets = append(s.sockets, &socket4{
		ifaceIndex: iface.Index,
		ifaceName:  iface.Name,
		conn:       conn,
		pktConn:    ipv4.NewPacketConn(conn), // TODO determine whether we need to join multicast groups
	})

	return nil
}

func (s *Server) listen6(iface *net.Interface) error {
	conn, err := newDHCP6Conn(iface)
	if err != nil {
		return err
	}

	s.sockets = append(s.sockets, &socket6{
		ifaceIndex: iface.Index,
		ifaceName:  iface.Name,
		conn:       conn,
		pktConn:    ipv6.NewPacketConn(conn),
	})

	return nil
}

func (s *Server) Listen() error {
	for _, iface := range s.ifaces {
		addrs, err := iface.Addrs()
		if err != nil {
			return err
		}

		var listen4, listen6 bool

		for _, addr := range addrs {
			// TODO handle more addr types
			switch a := addr.(type) {
			case *net.IPNet:
				if a.IP.To4() != nil {
					listen4 = true
				} else {
					listen6 = true
				}
			case *net.IPAddr:
				if a.IP.To4() != nil {
					listen4 = true
				} else {
					listen6 = true
				}
			}
		}

		if listen4 {
			err = s.listen4(iface)
			if err != nil {
				return err
			}
		}

		if listen6 {
			err = s.listen6(iface)
			if err != nil {
				return err
			}
		}
	}

	return nil
}

func (s *Server) Close() error {
	var errs []error

	for _, sock := range s.sockets {
		err := sock.Close()
		if err != nil {
			errs = append(errs, err)
		}
	}

	for _, l := range s.links {
		err := l.Close()
		if err != nil {
			errs = append(errs, err)
		}
	}

	if len(errs) > 0 {
		return errors.Join(errs...)
	}

	if s.xdpProg != nil {
		return s.xdpProg.Close()
	}

	return nil
}

func (s *Server) Serve(ctx context.Context) error {
	if s.xdpProg != nil && len(s.links) > 0 {
		return s.serveXDP(ctx)
	} else {
		return s.serveSockets(ctx)
	}
}

func (s *Server) serveXDP(ctx context.Context) error {
	readErrs := make(chan error)

	reader, err := ringbuf.NewReader(s.xdpProg.Queue())
	if err != nil {
		return err
	}

	defer reader.Close() //nolint:errcheck // ignoring deferred close error

	go func() {
		runtime.LockOSThread()
		defer runtime.UnlockOSThread()

		for {
			pkt, err := reader.Read() //nolint:govet // flagged as shadow declaraion, but is a separate goroutine
			if err != nil {
				if errors.Is(err, ringbuf.ErrClosed) {
					return
				}

				readErrs <- err

				return
			}

			err = s.inflight.Acquire(ctx, 1)
			if err != nil {
				readErrs <- err
				return
			}

			go func() {
				defer s.inflight.Release(1)

				var (
					msg Message
					idx int
				)

				n, err := binary.Decode(pkt.RawSample[idx:idx+4], binary.LittleEndian, &msg.IfaceIdx)
				if err != nil {
					readErrs <- err
					return
				}

				idx += n

				copy(msg.SrcMAC, pkt.RawSample[idx:idx+6])
				idx += 6

				n, err = binary.Decode(pkt.RawSample[idx:idx+2], binary.LittleEndian, &msg.SrcPort)
				if err != nil {
					readErrs <- err
					return
				}

				idx += n

				ip4 := make(net.IP, 4)
				copy(ip4, pkt.RawSample[idx:idx+4])

				idx += 4

				ip6 := make(net.IP, 16)
				copy(ip6, pkt.RawSample[idx:idx+16])

				idx += 16

				if !ip4.IsUnspecified() {
					msg.SrcIP = ip4

					msg.Pkt4, err = dhcpv4.FromBytes(pkt.RawSample[idx:])
					if err != nil {
						readErrs <- err
						return
					}
				} else {
					msg.SrcIP = ip6

					msg.Pkt6, err = dhcpv6.FromBytes(pkt.RawSample[idx:])
					if err != nil {
						readErrs <- err
						return
					}
				}

				if msg.Pkt4 != nil {
					err = s.handler4.ServeDHCP4(ctx, msg)
				} else {
					err = s.handler6.ServeDHCP6(ctx, msg)
				}

				if err != nil {
					log.Err(err).Send()
				}
			}()
		}
	}()

	select {
	case <-ctx.Done():
		return ctx.Err()
	case err = <-readErrs:
		return err
	}
}

func (s *Server) serveSockets(ctx context.Context) error {
	msgs := make(chan Message, len(s.sockets))
	errChan := make(chan error)

	for _, sock := range s.sockets {
		go func(s socket) {
			for {
				select {
				case <-ctx.Done():
					return
				default:
					conn := s.Conn()

					buf, ok := bufPool.Get().([]byte)
					if !ok {
						errChan <- ErrInvalidBuffer
						return
					}

					n, addr, err := conn.ReadFrom(buf)
					if err != nil {
						errChan <- err
						return
					}

					msg := Message{
						IfaceIdx: uint32(s.IfaceIdx()), //nolint:gosec // this interface indexes never overflow uint32
					}

					switch a := addr.(type) {
					case *net.IPAddr:
						msg.SrcIP = a.IP
					case *net.UDPAddr:
						msg.SrcIP = a.IP
						msg.SrcPort = uint16(a.Port) //nolint:gosec // port number will not overflow uint16
					}

					if _, ok := s.(*socket4); ok {
						msg.Pkt4, err = dhcpv4.FromBytes(buf[:n])
					} else {
						msg.Pkt6, err = dhcpv6.FromBytes(buf[:n])
					}

					if err != nil {
						errChan <- err
						return
					}

					msgs <- msg
				}
			}
		}(sock)
	}

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case msg := <-msgs:
			err := s.inflight.Acquire(ctx, 1)
			if err != nil {
				return err
			}

			if msg.Pkt4 != nil {
				go func() {
					defer s.inflight.Release(1)

					err := s.handler4.ServeDHCP4(ctx, msg)
					if err != nil {
						log.Err(err).Send()
					}
				}()
			} else {
				go func() {
					defer s.inflight.Release(1)

					err := s.handler6.ServeDHCP6(ctx, msg)
					if err != nil {
						log.Err(err).Send()
					}
				}()
			}
		case err := <-errChan:
			return err
		}
	}
}

func (s *Server) attachDHCPXDP(prog *xdp.Program) error {
	var err error

	s.links = make([]link.Link, len(s.ifaces))

	for i, iface := range s.ifaces {
		s.links[i], err = link.AttachXDP(link.XDPOptions{
			Program:   prog.Func(),
			Interface: iface.Index,
		})
		if err != nil {
			return err
		}
	}

	return nil
}
