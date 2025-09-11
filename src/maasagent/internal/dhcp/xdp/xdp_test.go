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

package xdp

import (
	"bytes"
	"encoding/binary"
	"net"
	"os"
	"testing"

	"github.com/cilium/ebpf/ringbuf"
	"github.com/google/gopacket"
	"github.com/google/gopacket/layers"
	"github.com/insomniacslk/dhcp/dhcpv4"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

type xdpAction uint32

const (
	xdpDrop xdpAction = 1
	xdpPass xdpAction = 2
)

// packetOption is a functional option for building packets overriding defaults
type packetOption func(*packetConfig)

type packetConfig struct {
	srcMAC  net.HardwareAddr
	dstMAC  net.HardwareAddr
	srcIP   net.IP
	dstIP   net.IP
	srcPort layers.UDPPort
	dstPort layers.UDPPort
	payload []byte
}

func defaultIPv4PacketConfig() *packetConfig {
	return &packetConfig{
		srcMAC:  net.HardwareAddr{0xde, 0xad, 0xbe, 0xef, 0x00, 0x01},
		dstMAC:  net.HardwareAddr{0xff, 0xff, 0xff, 0xff, 0xff, 0xff},
		srcIP:   net.IPv4zero,
		dstIP:   net.IPv4bcast,
		srcPort: 68,
		dstPort: 67,
		payload: []byte{},
	}
}

func withPayload(p []byte) packetOption {
	return func(c *packetConfig) { c.payload = p }
}

func withDstPort(port layers.UDPPort) packetOption {
	return func(c *packetConfig) { c.dstPort = port }
}

func buildIPv4Packet(t *testing.T, opts ...packetOption) []byte {
	cfg := defaultIPv4PacketConfig()
	for _, opt := range opts {
		opt(cfg)
	}

	eth := &layers.Ethernet{
		SrcMAC:       cfg.srcMAC,
		DstMAC:       cfg.dstMAC,
		EthernetType: layers.EthernetTypeIPv4,
	}

	ip := &layers.IPv4{
		Version:  4,
		IHL:      5,
		TTL:      64,
		Protocol: layers.IPProtocolUDP,
		SrcIP:    cfg.srcIP,
		DstIP:    cfg.dstIP,
	}
	udp := &layers.UDP{SrcPort: cfg.srcPort, DstPort: cfg.dstPort}
	require.NoError(t, udp.SetNetworkLayerForChecksum(ip))

	buf := gopacket.NewSerializeBuffer()
	optsSerialize := gopacket.SerializeOptions{
		FixLengths:       true,
		ComputeChecksums: true,
	}

	require.NoError(t, gopacket.SerializeLayers(buf, optsSerialize,
		eth, ip, udp, gopacket.Payload(cfg.payload),
	))

	return buf.Bytes()
}

func TestDHCP_XDP_IPv4(t *testing.T) {
	if os.Geteuid() != 0 {
		t.Skip("sudo is required to load XDP program and run the test")
	}

	defaultSrcMAC := net.HardwareAddr{0xde, 0xad, 0xbe, 0xef, 0x00, 0x01}

	p := New()

	require.NoError(t, p.Load())
	defer p.Close()

	rd, err := ringbuf.NewReader(p.Queue())
	require.NoError(t, err)

	defer rd.Close()

	testcases := map[string]struct {
		dhcp      func() ([]byte, error)
		opts      []packetOption
		xdpAction xdpAction
		verify    bool
	}{
		"valid DHCPDISCOVER": {
			dhcp: func() ([]byte, error) {
				d, err := dhcpv4.NewDiscovery(defaultSrcMAC)
				if err != nil {
					return nil, err
				}
				return d.ToBytes(), nil
			},
			xdpAction: xdpDrop,
			verify:    true,
		},
		"wrong dst port": {
			dhcp: func() ([]byte, error) {
				return []byte{}, nil
			},
			opts:      []packetOption{withDstPort(42)},
			xdpAction: xdpPass,
		},
	}

	for tname, tc := range testcases {
		t.Run(tname, func(t *testing.T) {
			dhcpBytes, err := tc.dhcp()
			require.NoError(t, err)

			tc.opts = append(tc.opts, withPayload(dhcpBytes))
			packet := buildIPv4Packet(t, tc.opts...)
			ret, _, err := p.Func().Test(packet)
			require.NoError(t, err)
			require.Equal(t, tc.xdpAction, xdpAction(ret))

			if !tc.verify {
				return
			}

			done := make(chan bpfDhcpData, 1)
			errs := make(chan error, 1)

			go func() {
				record, err := rd.Read()
				if err != nil {
					errs <- err
				}

				var e bpfDhcpData
				assert.NoError(t, binary.Read(bytes.NewReader(record.RawSample),
					binary.LittleEndian, &e))

				done <- e
			}()

			select {
			case err := <-errs:
				require.NoError(t, err)
			case e := <-done:
				assert.Len(t, e.SrcMac, 6)
				assert.Equal(t, []byte(defaultSrcMAC), e.SrcMac[:])
				assert.Equal(t, uint16(68), e.SrcPort)
				assert.Equal(t, net.IPv4zero.To4(), ipV4FromUint32(e.SrcIp4))

				want := make([]byte, 1984)
				copy(want, dhcpBytes)
				assert.Equal(t, want, e.DhcpPkt[:])
			}
		})
	}
}

func ipV4FromUint32(n uint32) net.IP {
	b := make([]byte, 4)
	binary.BigEndian.PutUint32(b, n)

	return net.IP(b)
}
