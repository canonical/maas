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
	"errors"
	"fmt"
	"net"
	"runtime"
	"syscall"

	"github.com/cilium/ebpf/link"
	"github.com/cilium/ebpf/ringbuf"
	"github.com/google/gopacket"
	"github.com/google/gopacket/layers"
	"github.com/rs/zerolog/log"
	"golang.org/x/sync/errgroup"
	"golang.org/x/sys/unix"
	"maas.io/core/src/maasagent/internal/dhcp/xdp"
	"maas.io/core/src/maasagent/internal/netutil"
	"maas.io/core/src/maasagent/internal/syncpool"
)

const (
	// DHCP packet will not exceed 1500 bytes, because of MTU size (1500)
	maxDHCPPktSize = 1500
)

// RecordReader defines a generic interface for reading BPF ring buffer.
type RecordReader interface {
	Read() (ringbuf.Record, error)
	Close() error
}

// SocketFactory abstracts how IPv4 and IPv6 sockets are created for a given
// interface. Flag writeOnly must be set if XDP program is loaded for this
// interface (all traffic is already filtered), to prevent sockets from reading
// incoming data. In this situation data is fetched from the BPF map (ring buffer)
type SocketFactory interface {
	NewIPv4Socket(iface *net.Interface, writeOnly bool) (Socket, error)
	NewIPv6Socket(iface *net.Interface, writeOnly bool) (Socket, error)
}

// defaultSocketFactory just makes real IPv4/IPv6 sockets
type defaultSocketFactory struct{}

func (defaultSocketFactory) NewIPv4Socket(iface *net.Interface,
	writeOnly bool) (Socket, error) {
	return NewIPv4Socket(iface, writeOnly)
}

func (defaultSocketFactory) NewIPv6Socket(iface *net.Interface,
	writeOnly bool) (Socket, error) {
	return NewIPv6Socket(iface, writeOnly)
}

// XDPAttacher defines a function type that attaches an XDP program
// to a network interface
type XDPAttacher func(ifaceIdx int) (link.Link, error)

// XDPFactory defines an interface for creating an XDP program and its reader.
// Mostly here so we can mock stuff in tests
type XDPFactory interface {
	New(s *Server) (XDPAttacher, error)
}

// defaultXDPFactory will load XDP program, set the reader and return attacher
// function that would attach the program to an interface.
type defaultXDPFactory struct{}

func (defaultXDPFactory) New(s *Server) (XDPAttacher, error) {
	program := xdp.New()

	if err := program.Load(); err != nil {
		return nil, err
	}

	reader, err := ringbuf.NewReader(program.Queue())
	if err != nil {
		return nil, err
	}

	s.recordReader = reader
	attacher := func(ifaceIdx int) (link.Link, error) {
		return link.AttachXDP(
			link.XDPOptions{
				Program:   program.Func(),
				Interface: ifaceIdx,
			})
	}

	s.xdpProgram = program

	return attacher, nil
}

// Handler handles DHCP requests
type Handler interface {
	// ServeDHCP processes a DHCP message and returns a response.
	ServeDHCP(context.Context, Message) (resp Response, err error)
}

// socketTable used for socket lookup. [familyIdx]map[ifaceIdx]
type socketTable [2]map[int]Socket

type Server struct {
	h4            Handler
	h6            Handler
	sockets       socketTable
	syscaller     netutil.Syscaller
	recordReader  RecordReader
	socketFactory SocketFactory
	xdpFactory    XDPFactory
	interfaces    map[int]*net.Interface
	buf           *syncpool.Pool[[]byte]
	xdpProgram    *xdp.Program
	links         []link.Link
}

type ServerOption func(*Server)

// NewServer returns a Server that listens on the given interfaces.
//
// For each interface it creates IPv4 and IPv6 sockets and, if available,
// attaches an XDP program. DHCPv4 and DHCPv6 handlers are set with
// WithV4Handler and WithV6Handler.
//
// If all of the sockets setup fails, it returns an error.
func NewServer(ifaces []*net.Interface, options ...ServerOption) (*Server, error) {
	s := &Server{
		sockets: socketTable{
			make(map[int]Socket),
			make(map[int]Socket),
		},
		interfaces:    make(map[int]*net.Interface),
		links:         []link.Link{},
		syscaller:     netutil.RealSyscaller{},
		socketFactory: defaultSocketFactory{},
		xdpFactory:    defaultXDPFactory{},
		buf: syncpool.New(func() []byte {
			return make([]byte, maxDHCPPktSize)
		}),
	}

	for _, opt := range options {
		opt(s)
	}

	xdpAttacher, err := s.xdpFactory.New(s)
	if err != nil {
		log.Warn().Err(err).Msg("Cannot load XDP program")
	}

	for _, iface := range ifaces {
		var link link.Link

		writeOnly := false

		// Make an attempt to load XDP program. If successful, then sockets bound
		// to the interface can be flagged as write-only.
		if xdpAttacher != nil {
			link, err = xdpAttacher(iface.Index)
			if err == nil {
				writeOnly = true
			} else {
				log.Warn().Str("iface", iface.Name).Err(err).Msg("Cannot attach XDP program")
			}
		}

		// Bind sockets to the interface. Close BPF link in case of an error
		if err := s.bind(iface, writeOnly); err != nil {
			if link != nil {
				//nolint:govet // false positive shadow
				if err := link.Close(); err != nil {
					log.Warn().Err(err).Msg("Closing BPF link failed")
				}
			}

			log.Warn().Str("iface", iface.Name).Err(err).Msg("Cannot bind socket")

			continue
		}

		s.interfaces[iface.Index] = iface

		// Once initialization is successful, store BPF links, as they need to
		// be closed properly
		if link != nil {
			s.links = append(s.links, link)
		}
	}

	return s, nil
}

// WithSyscaller used for testing
func WithSyscaller(syscaller netutil.Syscaller) ServerOption {
	return func(s *Server) {
		s.syscaller = syscaller
	}
}

// WithSocketFactory used for testing
func WithSocketFactory(factory SocketFactory) ServerOption {
	return func(s *Server) {
		s.socketFactory = factory
	}
}

// WithXDPFactory used for testing
func WithXDPFactory(factory XDPFactory) ServerOption {
	return func(s *Server) {
		s.xdpFactory = factory
	}
}

// WithV4Handler sets a handler used for IPv4 DHCP
func WithV4Handler(h Handler) ServerOption {
	return func(s *Server) {
		s.h4 = h
	}
}

// WithV6Handler sets a handler used for IPv6 DHCP
func WithV6Handler(h Handler) ServerOption {
	return func(s *Server) {
		s.h6 = h
	}
}

// familyIndex is needed for socket ([familyIdx]map[ifaceIdx]) lookup
func familyIndex(af AddressFamily) int {
	switch af {
	case AddressFamily(unix.AF_INET):
		return 0
	case AddressFamily(unix.AF_INET6):
		return 1
	default:
		panic("unsupported family")
	}
}

// bind tries to configure required sockets and bind to a given interface
// If at least one constructor will succeed, the error returned is nil.
func (s *Server) bind(iface *net.Interface, writeOnly bool) error {
	// socket constructors
	newFns := []func(*net.Interface, bool) (Socket, error){
		s.socketFactory.NewIPv4Socket,
		s.socketFactory.NewIPv6Socket,
	}

	var errs []error

	for _, newSocketFn := range newFns {
		sock, err := newSocketFn(iface, writeOnly)
		if err != nil {
			errs = append(errs, err)
			log.Warn().Str("iface", iface.Name).Str("type", fmt.Sprintf("%T", newSocketFn)).
				Err(err).Msg("Cannot bind socket")

			continue
		}

		famIdx := familyIndex(sock.AddressFamily())
		s.sockets[famIdx][iface.Index] = sock
	}

	if len(errs) != len(newFns) {
		return nil
	}

	return fmt.Errorf("failed to bind sockets: %v", errors.Join(errs...))
}

// Close would close all the sockets, links and BPF program
func (s *Server) Close() error {
	var errs []error

	addErr := func(err error) {
		if err != nil {
			errs = append(errs, err)
		}
	}

	if s.xdpProgram != nil {
		addErr(s.xdpProgram.Close())
	}

	for _, l := range s.links {
		addErr(l.Close())
	}

	for i := range s.sockets {
		for j := range s.sockets[i] {
			sock := s.sockets[i][j]
			if sock == nil {
				continue
			}

			addErr(sock.Close())
		}
	}

	if len(errs) == 0 {
		return nil
	}

	return fmt.Errorf("closing DHCP server failed: %v", errors.Join(errs...))
}

// Serve runs the DHCP server until the context is canceled or an error occurs.
func (s *Server) Serve(ctx context.Context) error {
	g, ctx := errgroup.WithContext(ctx)

	g.Go(func() error {
		<-ctx.Done()
		return s.Close()
	})

	g.Go(func() error {
		return s.serveSockets(ctx)
	})

	if s.xdpProgram != nil && len(s.links) > 0 {
		g.Go(func() error {
			return s.serveXDP(ctx)
		})
	}

	return g.Wait()
}

func (s *Server) serveXDP(ctx context.Context) error {
	g, ctx := errgroup.WithContext(ctx)

	g.Go(func() error {
		<-ctx.Done()
		// to unblock reader.Read()
		return s.recordReader.Close()
	})

	g.Go(func() error {
		runtime.LockOSThread()
		defer runtime.UnlockOSThread()

		for {
			record, err := s.recordReader.Read()
			if err != nil {
				if errors.Is(err, ringbuf.ErrClosed) || ctx.Err() != nil {
					// context canceled, exit cleanly
					return nil
				}

				log.Err(err).Msg("Failed reading from ring buffer")

				return err
			}

			// TODO: introduce worker pool
			var msg Message
			//nolint:govet // false positive shadow
			if err := msg.UnmarshalBinary(record.RawSample); err != nil {
				log.Warn().Err(err).Msg("Failed unmarshaling from ring buffer")
				continue
			}

			h := s.handlerFor(msg.Family)

			resp, err := h.ServeDHCP(ctx, msg)
			if err != nil {
				log.Warn().Err(err).Msg("Failed to handle DHCP")
				continue
			}

			// TODO: write response properly: unicast/broadcast/eth
			if resp.Mode == SendL2 {
				err = s.WriteToEthernet(resp)
				if err != nil {
					log.Err(err).Msg("Failed to send DHCP response")
				}
			} else {
				sock := s.socketFor(int(msg.IfaceIdx), msg.Family)

				_, err = sock.Conn().WriteTo(resp.Payload,
					&net.UDPAddr{IP: resp.DstAddress, Port: 68})
				if err != nil {
					log.Err(err).Msg("Failed to send DHCP response")
				}
			}
		}
	})

	return g.Wait()
}

func (s *Server) serveSockets(ctx context.Context) error {
	g, ctx := errgroup.WithContext(ctx)

	started := false

	for _, famSockets := range s.sockets {
		for _, sock := range famSockets {
			if sock == nil || sock.IsWriteOnly() {
				log.Debug().Str("iface", sock.Iface().Name).Msg("Skipping write-only socket")

				continue
			}

			started = true

			g.Go(func() error {
				return s.serveSocket(ctx, sock)
			})
		}
	}

	if !started {
		return nil
	}

	if err := g.Wait(); err != nil {
		return err
	}

	return nil
}

// handlerFor returns a handler associated with a specific address family
func (s *Server) handlerFor(af AddressFamily) Handler {
	switch af {
	case AddressFamily(unix.AF_INET):
		return s.h4
	case AddressFamily(unix.AF_INET6):
		return s.h6
	default:
		panic("unsupported family")
	}
}

// serveSocket starts a read loop (net.PacketConn).ReadFrom on the given socket,
// dispatches received packet to the appropriate handler and writes back response
// until the context is canceled
func (s *Server) serveSocket(ctx context.Context, sock Socket) error {
	conn := sock.Conn()

	af := sock.AddressFamily()

	handler := s.handlerFor(af)
	if handler == nil {
		return fmt.Errorf("missing handler for address family: %v", af)
	}

	for {
		select {
		case <-ctx.Done():
			return nil
		default:
		}

		buf := s.buf.Get()

		n, addr, serr := conn.ReadFrom(buf)
		if n > 0 {
			// TODO: introduce worker pool
			go func(data []byte, addr net.Addr) {
				defer s.buf.Put(data[:0])

				resp, err := handler.ServeDHCP(ctx,
					Message{
						//nolint:gosec // this interface indexes never overflow uint32
						IfaceIdx: uint32(sock.Iface().Index),
						Payload:  data,
					})
				if err != nil {
					log.Warn().Err(err).Msg("Failed to handle DHCP")
					return
				}

				// TODO: write response properly: unicast/broadcast/eth
				if resp.Mode == SendL2 {
					err = s.WriteToEthernet(resp)
					if err != nil {
						log.Err(err).Msg("Failed to send DHCP response")
					}
				} else {
					n, err = conn.WriteTo(resp.Payload,
						&net.UDPAddr{IP: resp.DstAddress, Port: 68})
					if err != nil {
						log.Err(err).Msg("Failed to send DHCP response")
					}
				}
			}(buf[:n], addr)
		}

		if serr != nil {
			if ctx.Err() != nil {
				//nolint:nilerr // context canceled, exit cleanly
				return nil
			}

			log.Err(serr).Msg("Failed reading from socket")
		}
	}
}

// socketFor returns a socket associated with a specific interface and address family
func (s *Server) socketFor(ifaceIdx int, af AddressFamily) Socket {
	return s.sockets[familyIndex(af)][ifaceIdx]
}

// WriteToEthernet sends a raw Ethernet frame to the client's MAC address
func (s *Server) WriteToEthernet(r Response) error {
	eth := &layers.Ethernet{
		DstMAC:       r.DstMAC,
		SrcMAC:       s.interfaces[r.IfaceIdx].HardwareAddr,
		EthernetType: layers.EthernetTypeIPv4,
	}

	ip := &layers.IPv4{
		Version:  4,
		TTL:      64,
		SrcIP:    r.SrcAddress,
		DstIP:    r.DstAddress,
		Protocol: layers.IPProtocolUDP,
		Flags:    layers.IPv4DontFragment,
	}

	udp := &layers.UDP{
		SrcPort: 67,
		DstPort: 68,
	}

	if err := udp.SetNetworkLayerForChecksum(ip); err != nil {
		return err
	}

	buf := gopacket.NewSerializeBuffer()
	opts := gopacket.SerializeOptions{
		ComputeChecksums: true,
		FixLengths:       true,
	}

	if err := gopacket.SerializeLayers(buf, opts,
		eth,
		ip,
		udp,
		gopacket.Payload(r.Payload),
	); err != nil {
		return err
	}

	// TODO: check if we can create socket once and then reuse it
	fd, err := s.syscaller.Socket(syscall.AF_PACKET, syscall.SOCK_RAW, 0)
	if err != nil {
		return err
	}

	defer func() {
		//nolint:govet // false positive shadow
		if err := s.syscaller.Close(fd); err != nil {
			log.Warn().Err(err).Msg("Failed to close socket")
		}
	}()

	err = s.syscaller.SetsockoptInt(fd, syscall.SOL_SOCKET, syscall.SO_REUSEADDR, 1)
	if err != nil {
		return err
	}

	ethAddr := syscall.SockaddrLinklayer{
		Protocol: 0,
		Ifindex:  r.IfaceIdx,
		Halen:    6,
	}

	copy(ethAddr.Addr[:], r.DstMAC[:6])

	return s.syscaller.Sendto(fd, buf.Bytes(), 0, &ethAddr)
}
