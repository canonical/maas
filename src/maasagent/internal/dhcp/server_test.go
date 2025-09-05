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
	"fmt"
	"net"
	"syscall"
	"testing"
	"time"

	"github.com/cilium/ebpf/link"
	"github.com/cilium/ebpf/ringbuf"
	"github.com/google/gopacket"
	"github.com/google/gopacket/layers"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"golang.org/x/sys/unix"
	"maas.io/core/src/maasagent/internal/dhcp/xdp"
)

// wrapConn adapts a stream-oriented net.Conn (from net.Pipe)
// to look like a packet-oriented net.PacketConn for testing purpose
type wrapConn struct {
	c net.Conn
}

func (w wrapConn) ReadFrom(p []byte) (int, net.Addr, error) {
	n, err := w.c.Read(p)
	return n, nil, err
}

func (w wrapConn) WriteTo(p []byte, _ net.Addr) (int, error) {
	return w.c.Write(p)
}

func (w wrapConn) Close() error {
	return w.c.Close()
}

func (w wrapConn) LocalAddr() net.Addr {
	return w.c.LocalAddr()
}

func (w wrapConn) RemoteAddr() net.Addr {
	return w.c.RemoteAddr()
}

func (w wrapConn) SetDeadline(t time.Time) error {
	return w.c.SetDeadline(t)
}

func (w wrapConn) SetReadDeadline(t time.Time) error {
	return w.c.SetReadDeadline(t)
}

func (w wrapConn) SetWriteDeadline(t time.Time) error {
	return w.c.SetWriteDeadline(t)
}

var _ net.PacketConn = wrapConn{}

// pipe returns a pair of connected PacketConns backed by net.Pipe
func pipe() (net.PacketConn, net.PacketConn) {
	a, b := net.Pipe()
	return wrapConn{a}, wrapConn{b}
}

// fakeSocket is returned by fakeSocketFactory and stored by the Server because
// using real sockets in unit-tests is problematic.
type fakeSocket struct {
	family    AddressFamily
	iface     *net.Interface
	writeOnly bool
	conn      net.PacketConn
}

func (fs fakeSocket) AddressFamily() AddressFamily {
	return fs.family
}

func (fs fakeSocket) Iface() *net.Interface {
	return fs.iface
}

func (fs fakeSocket) IsWriteOnly() bool {
	return fs.writeOnly
}

func (fs fakeSocket) Conn() net.PacketConn {
	return fs.conn
}

func (fs fakeSocket) Close() error {
	return fs.conn.Close()
}

// fakeSocketFactory used to override how Server creates required sockets
// Using real sockets would require real interfaces and privileged access to
// set unix.SO_BROADCAST and read real broadcast datagrams, so we have to fake
type fakeSocketFactory struct {
	ifaceIdx       int
	connV4, connV6 net.PacketConn
	errV4, errV6   error
}

func (f fakeSocketFactory) NewIPv4Socket(iface *net.Interface,
	writeOnly bool) (Socket, error) {
	return fakeSocket{
		iface:     &net.Interface{Index: f.ifaceIdx},
		family:    AddressFamily(unix.AF_INET),
		conn:      f.connV4,
		writeOnly: writeOnly}, f.errV4
}
func (f fakeSocketFactory) NewIPv6Socket(iface *net.Interface,
	writeOnly bool) (Socket, error) {
	return fakeSocket{
		iface:     &net.Interface{Index: f.ifaceIdx},
		family:    AddressFamily(unix.AF_INET6),
		conn:      f.connV6,
		writeOnly: writeOnly}, f.errV6
}

// fakeRecordReader pretends to be a ringbuf.Reader that returns a configured
// ringbuf.Record (normally Reader would read the XDP BPF map)
type fakeRecordReader struct {
	readRecord chan ringbuf.Record
	readErr    chan error
	closeErr   error
	closed     bool
}

func (f *fakeRecordReader) Read() (ringbuf.Record, error) {
	return <-f.readRecord, <-f.readErr
}

func (f *fakeRecordReader) Close() error {
	f.readRecord <- ringbuf.Record{}

	f.readErr <- ringbuf.ErrClosed
	f.closed = true

	return f.closeErr
}

type fakeXDPFactory struct {
	xdpProgram   *xdp.Program
	recordReader RecordReader
	attacher     XDPAttacher
	newErr       error
}

func (f fakeXDPFactory) New(s *Server) (XDPAttacher, error) {
	s.recordReader = f.recordReader
	s.xdpProgram = f.xdpProgram

	return f.attacher, f.newErr
}

// fakeHandler is a fake implementation of DHCPvX handler
type fakeHandler struct {
	fn func(context.Context, Message) (Response, error)
}

func (h fakeHandler) ServeDHCP(ctx context.Context, m Message) (Response, error) {
	return h.fn(ctx, m)
}

// fakeLink because we need a controlled Close() method for testing
type fakeLink struct {
	link.Link
	closeErr error
}

type fakeSyscaller struct {
	recordedP  chan []byte
	recordedTo syscall.Sockaddr
}

func (f *fakeSyscaller) Close(fd int) error {
	return nil
}

func (f *fakeSyscaller) Sendto(fd int, p []byte, flags int, to syscall.Sockaddr) error {
	f.recordedP <- p

	f.recordedTo = to

	return nil
}

func (f *fakeSyscaller) SetsockoptInt(fd, level, opt int, value int) error {
	return nil
}

func (f *fakeSyscaller) Socket(domain, typ, proto int) (int, error) {
	return 0, nil
}

func (f fakeLink) Close() error { return f.closeErr }

// TestServerEcho_IPv4Socket is a simple test that is using bunch of fakes.
// It is testing the flow when DHCP is received over the IPv4 socket and
// response is returned over the same socket.
func TestServerEcho_IPv4Socket(t *testing.T) {
	data := []byte(t.Name())

	inV4, outV4 := pipe()
	// Create a Server that for any interface will create a socket (fake one)
	// with the piped net.PacketConn being used to send/receive data
	s, err := NewServer(
		// A fake interface, for which a fake socket will be created
		[]*net.Interface{{Index: 1}},
		WithV4Handler(fakeHandler{
			fn: func(ctx context.Context, m Message) (Response, error) {
				return Response{Payload: m.Payload}, nil
			},
		}),
		WithSocketFactory(fakeSocketFactory{
			ifaceIdx: 1, connV4: inV4, errV6: fmt.Errorf("no IPv6"),
		}),
		WithXDPFactory(fakeXDPFactory{
			newErr: fmt.Errorf("test without XDP"),
		}),
	)

	require.NoError(t, err)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	errs := make(chan error)

	go func() {
		errs <- s.Serve(ctx)
	}()

	_, err = outV4.WriteTo(data, &net.UDPAddr{})
	require.NoError(t, err)

	buf := make([]byte, len(data))
	_, _, err = outV4.ReadFrom(buf)

	assert.NoError(t, err)
	assert.Equal(t, data, buf)

	cancel()

	if err := <-errs; err != nil {
		require.NoError(t, err)
	}
}

// TestServerEcho_IPv4Socket_L2 is a simple test that is using bunch of fakes.
// It is testing the flow when DHCP message is received over IPv4 socket and
// response should be a raw Ethernet frame.
func TestServerEcho_IPv4Socket_L2(t *testing.T) {
	data := []byte(t.Name())

	//nolint:govet // false positive shadow
	fakeSyscaller := fakeSyscaller{recordedP: make(chan []byte)}
	inV4, outV4 := pipe()
	// Create a Server that for any interface will create a socket (fake one)
	// with the piped net.PacketConn being used to send/receive data
	s, err := NewServer(
		// A fake interface, for which a fake socket will be created
		[]*net.Interface{{Index: 1, HardwareAddr: net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22}}},
		WithV4Handler(fakeHandler{
			fn: func(ctx context.Context, m Message) (Response, error) {
				return Response{
					IfaceIdx:   1,
					Mode:       SendL2,
					DstMAC:     net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
					SrcAddress: net.IPv4zero,
					DstAddress: net.IPv4zero,
					Payload:    m.Payload,
				}, nil
			},
		}),
		WithSocketFactory(fakeSocketFactory{
			ifaceIdx: 1, connV4: inV4, errV6: fmt.Errorf("no IPv6"),
		}),
		WithXDPFactory(fakeXDPFactory{
			newErr: fmt.Errorf("test without XDP"),
		}),
		WithSyscaller(&fakeSyscaller),
	)

	require.NoError(t, err)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	errs := make(chan error)

	go func() {
		errs <- s.Serve(ctx)
	}()

	_, err = outV4.WriteTo(data, &net.UDPAddr{})
	require.NoError(t, err)

	frame := <-fakeSyscaller.recordedP

	// Decode the full Ethernet frame and compare the UDP payload
	// For testing it doesn't matter if thats a valid DHCP or not.
	packet := gopacket.NewPacket(frame, layers.LayerTypeEthernet, gopacket.Default)
	result := packet.Layer(layers.LayerTypeUDP).LayerPayload()
	assert.Equal(t, data, result)

	cancel()

	if err := <-errs; err != nil {
		require.NoError(t, err)
	}
}

// TestServerEcho_XDP tests data being read from a ring buffer and then send
// over using a socket bound to a proper interface.
func TestServerEcho_XDP(t *testing.T) {
	msg := Message{
		SrcMAC:   net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
		SrcIP:    net.IPv4zero,
		IfaceIdx: 1,
		Family:   AddressFamily(unix.AF_INET),
		SrcPort:  1337,
		Payload:  []byte(t.Name()),
	}

	data, err := msg.MarshalBinary()
	require.NoError(t, err)

	fakeRecordReader := &fakeRecordReader{
		readRecord: make(chan ringbuf.Record),
		readErr:    make(chan error),
	}

	inV4, outV4 := pipe()
	// Create a Server that for any interface will create a socket (fake one)
	// with the piped net.PacketConn being used to send/receive data
	s, err := NewServer(
		// A fake interface, for which a fake socket will be created
		[]*net.Interface{{Index: 1, HardwareAddr: net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22}}},
		WithV4Handler(fakeHandler{
			fn: func(ctx context.Context, m Message) (Response, error) {
				return Response{Payload: m.Payload}, nil
			},
		}),
		WithSocketFactory(fakeSocketFactory{
			ifaceIdx: 1, connV4: inV4, errV6: fmt.Errorf("no IPv6"),
		}),
		WithXDPFactory(fakeXDPFactory{
			xdpProgram: xdp.New(),
			attacher: func(ifaceIdx int) (link.Link, error) {
				return fakeLink{}, nil
			},
			recordReader: fakeRecordReader,
		}),
	)

	require.NoError(t, err)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	errs := make(chan error)

	go func() {
		errs <- s.Serve(ctx)
	}()

	fakeRecordReader.readRecord <- ringbuf.Record{
		RawSample: data,
		Remaining: 0,
	}

	fakeRecordReader.readErr <- nil

	buf := make([]byte, len(msg.Payload))
	_, _, err = outV4.ReadFrom(buf)

	assert.NoError(t, err)
	assert.Equal(t, msg.Payload, buf)

	cancel()

	if err := <-errs; err != nil {
		require.NoError(t, err)
	}
}

// TestServerEcho_XDP_L2 tests data being read from a ring buffer and then send
// over using a socket bound to a proper interface.
func TestServerEcho_XDP_L2(t *testing.T) {
	expected := []byte(t.Name())

	msg := Message{
		SrcMAC:   net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
		SrcIP:    net.IPv4zero,
		IfaceIdx: 1,
		Family:   AddressFamily(unix.AF_INET),
		SrcPort:  1337,
		Payload:  expected,
	}

	data, err := msg.MarshalBinary()
	require.NoError(t, err)

	fakeRecordReader := &fakeRecordReader{
		readRecord: make(chan ringbuf.Record),
		readErr:    make(chan error),
	}

	//nolint:govet // false positive shadow
	fakeSyscaller := fakeSyscaller{recordedP: make(chan []byte)}

	inV4, _ := pipe()
	// Create a Server that for any interface will create a socket (fake one)
	// with the piped net.PacketConn being used to send/receive data
	s, err := NewServer(
		// A fake interface, for which a fake socket will be created
		[]*net.Interface{{Index: 1, HardwareAddr: net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22}}},
		WithV4Handler(fakeHandler{
			fn: func(ctx context.Context, m Message) (Response, error) {
				return Response{
					IfaceIdx:   1,
					Mode:       SendL2,
					DstMAC:     net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
					SrcAddress: net.IPv4zero,
					DstAddress: net.IPv4zero,
					Payload:    m.Payload,
				}, nil
			},
		}),
		WithSocketFactory(fakeSocketFactory{
			ifaceIdx: 1, connV4: inV4, errV6: fmt.Errorf("no IPv6"),
		}),
		WithXDPFactory(fakeXDPFactory{
			xdpProgram: xdp.New(),
			attacher: func(ifaceIdx int) (link.Link, error) {
				return fakeLink{}, nil
			},
			recordReader: fakeRecordReader,
		}),
		WithSyscaller(&fakeSyscaller),
	)

	require.NoError(t, err)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	errs := make(chan error)

	go func() {
		errs <- s.Serve(ctx)
	}()

	fakeRecordReader.readRecord <- ringbuf.Record{
		RawSample: data,
		Remaining: 0,
	}

	fakeRecordReader.readErr <- nil

	frame := <-fakeSyscaller.recordedP

	// Decode the full Ethernet frame and compare the UDP payload
	// For testing it doesn't matter if thats a valid DHCP or not.
	packet := gopacket.NewPacket(frame, layers.LayerTypeEthernet, gopacket.Default)
	result := packet.Layer(layers.LayerTypeUDP).LayerPayload()
	assert.Equal(t, expected, result)

	cancel()

	if err := <-errs; err != nil {
		require.NoError(t, err)
	}

	assert.True(t, fakeRecordReader.closed)
}
