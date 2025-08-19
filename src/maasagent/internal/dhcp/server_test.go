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
	"net"
	"sync"
	"testing"
	"time"

	"github.com/insomniacslk/dhcp/dhcpv4"
	"github.com/insomniacslk/dhcp/dhcpv6"
	"maas.io/core/src/maasagent/internal/dhcp/xdp"
)

type dhcpTestClient struct {
	ipVersion int
	conn      net.PacketConn
}

func newDHCPTestClient(network string, addr string) (*dhcpTestClient, error) {
	conn, err := net.ListenPacket(network, addr)
	if err != nil {
		return nil, err
	}

	ipVersion := 4
	if network == "udp6" {
		ipVersion = 6
	}

	return &dhcpTestClient{
		conn:      conn,
		ipVersion: ipVersion,
	}, nil
}

func (d *dhcpTestClient) Roundtrip(ctx context.Context, buf []byte) error {
	_, err := d.conn.WriteTo(buf, &net.UDPAddr{ //nolint:staticcheck // _ is being marked as unusred
		IP:   net.ParseIP("127.0.0.1"),
		Port: 67,
	})

	resp := make([]byte, len(buf))

	_, _, err = d.conn.ReadFrom(resp)
	if err != nil {
		return err
	}

	if d.ipVersion == 4 {
		_, err = dhcpv4.FromBytes(resp)
	} else {
		_, err = dhcpv6.FromBytes(resp)
	}

	return err
}

func (d *dhcpTestClient) Close() error {
	return d.conn.Close()
}

type echoDHCPHandler struct {
	s *Server
}

func (e *echoDHCPHandler) echo(ctx context.Context, msg Message, ipv IPVersion) error {
	sock, err := e.s.GetSocketFor(ipv, int(msg.IfaceIdx))
	if err != nil {
		return err
	}

	conn := sock.Conn()

	var buf []byte
	if ipv == IPv4 {
		buf = msg.Pkt4.ToBytes()
	} else {
		buf = msg.Pkt6.ToBytes()
	}

	_, err = conn.WriteTo(buf, &net.UDPAddr{IP: msg.SrcIP, Port: int(msg.SrcPort)})

	return err
}

func (e *echoDHCPHandler) ServeDHCP4(ctx context.Context, msg Message) error {
	return e.echo(ctx, msg, 4)
}

func (e *echoDHCPHandler) ServeDHCP6(ctx context.Context, msg Message) error {
	return e.echo(ctx, msg, 6)
}

func BenchmarkXdpDhcpServer(b *testing.B) {
	ctx, cancel := context.WithCancel(context.Background())

	b.Cleanup(func() {
		cancel()
	})

	xdpProg := xdp.New()

	err := xdpProg.Load()
	if err != nil {
		b.Fatal(err)
	}

	handler := &echoDHCPHandler{}

	server, err := NewServer([]string{"lo"}, xdpProg, handler, handler)
	if err != nil {
		b.Fatal(err)
	}

	handler.s = server

	go server.Serve(ctx)
	defer server.Close()

	var (
		client *dhcpTestClient
		pkt    []byte
	)

	client, err = newDHCPTestClient("udp4", "127.0.0.1:68")
	if err != nil {
		b.Fatal(err)
	}

	msg, err := dhcpv4.New(
		dhcpv4.WithClientIP(net.ParseIP("127.0.0.1")),
	)
	if err != nil {
		b.Error(err)
	}

	msg.OpCode = dhcpv4.OpcodeBootRequest
	pkt = msg.ToBytes()

	defer client.Close()

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		err = client.Roundtrip(ctx, pkt)
		if err != nil {
			b.Fatal(err)
		}
	}
}

func BenchmarkRawSocketDhcpServer(b *testing.B) {
	ctx, cancel := context.WithCancel(context.Background())

	b.Cleanup(func() {
		cancel()
	})

	handler := &echoDHCPHandler{}

	server, err := NewServer([]string{"lo"}, nil, handler, handler)
	if err != nil {
		b.Fatal(err)
	}

	handler.s = server

	go server.Serve(ctx)
	defer server.Close()

	var (
		client *dhcpTestClient
		pkt    []byte
	)

	client, err = newDHCPTestClient("udp4", "127.0.0.1:68")
	if err != nil {
		b.Fatal(err)
	}

	msg, err := dhcpv4.New(
		dhcpv4.WithClientIP(net.ParseIP("127.0.0.1")),
	)
	if err != nil {
		b.Error(err)
	}

	msg.OpCode = dhcpv4.OpcodeBootRequest
	pkt = msg.ToBytes()

	defer client.Close()

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		err = client.Roundtrip(ctx, pkt)
		if err != nil {
			b.Fatal(err)
		}
	}
}

func BenchmarkXdpDhcpServerThroughput(b *testing.B) {
	ctx, cancel := context.WithCancel(context.Background())

	b.Cleanup(func() {
		cancel()
	})

	xdpProg := xdp.New()

	err := xdpProg.Load()
	if err != nil {
		b.Fatal(err)
	}

	handler := &echoDHCPHandler{}

	server, err := NewServer([]string{"lo"}, xdpProg, handler, handler)
	if err != nil {
		b.Fatal(err)
	}

	handler.s = server

	go server.Serve(ctx)
	defer server.Close()

	var pkt []byte

	numClients := 100
	clients := make([]*dhcpTestClient, numClients)

	for i := 0; i < numClients; i++ {
		clients[i], err = newDHCPTestClient("udp4", "127.0.0.1:0")
		if err != nil {
			b.Fatal(err)
		}

		defer clients[i].Close()
	}

	msg, err := dhcpv4.New(
		dhcpv4.WithClientIP(net.ParseIP("127.0.0.1")),
	)
	if err != nil {
		b.Error(err)
	}

	msg.OpCode = dhcpv4.OpcodeBootRequest
	pkt = msg.ToBytes()

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		wg := &sync.WaitGroup{}
		wg.Add(len(clients))

		for _, client := range clients {
			go func(c *dhcpTestClient) {
				defer wg.Done()

				c.conn.SetDeadline(time.Now().Add(time.Second))

				err = c.Roundtrip(ctx, pkt)
				if err != nil {
					b.Log(err)
				}
			}(client)
		}

		wg.Wait()
	}
}

func BenchmarkRawSocketDhcpServerThroughput(b *testing.B) {
	ctx, cancel := context.WithCancel(context.Background())

	b.Cleanup(func() {
		cancel()
	})

	handler := &echoDHCPHandler{}

	server, err := NewServer([]string{"lo"}, nil, handler, handler)
	if err != nil {
		b.Fatal(err)
	}

	handler.s = server

	go server.Serve(ctx)
	defer server.Close()

	var pkt []byte

	numClients := 100
	clients := make([]*dhcpTestClient, numClients)

	for i := 0; i < numClients; i++ {
		clients[i], err = newDHCPTestClient("udp4", "127.0.0.1:0")
		if err != nil {
			b.Fatal(err)
		}

		defer clients[i].Close()
	}

	msg, err := dhcpv4.New(
		dhcpv4.WithClientIP(net.ParseIP("127.0.0.1")),
	)
	if err != nil {
		b.Error(err)
	}

	msg.OpCode = dhcpv4.OpcodeBootRequest
	pkt = msg.ToBytes()

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		wg := &sync.WaitGroup{}
		wg.Add(len(clients))

		for _, client := range clients {
			go func(c *dhcpTestClient) {
				defer wg.Done()

				c.conn.SetDeadline(time.Now().Add(time.Second))

				err = c.Roundtrip(ctx, pkt)
				if err != nil {
					b.Log(err)
				}
			}(client)
		}

		wg.Wait()
	}
}
