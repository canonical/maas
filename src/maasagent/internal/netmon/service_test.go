package netmon

/*
	Copyright 2023 Canonical Ltd.  This software is licensed under the
	GNU Affero General Public License version 3 (see the file LICENSE).
*/

import (
	"net"
	"net/netip"
	"testing"
	"time"

	"github.com/google/gopacket"
	pcap "github.com/packetcap/go-pcap"
	"github.com/stretchr/testify/assert"

	"maas.io/core/src/maasagent/internal/ethernet"
)

func uint16Pointer(v uint16) *uint16 {
	return &v
}

func TestIsValidARPPacket(t *testing.T) {
	t.Parallel()

	testcases := map[string]struct {
		in  *ethernet.ARPPacket
		out bool
	}{
		"valid ARP packet": {
			in: &ethernet.ARPPacket{
				HardwareType:    ethernet.HardwareTypeEthernet,
				ProtocolType:    ethernet.ProtocolTypeIPv4,
				HardwareAddrLen: 6,
				ProtocolAddrLen: 4,
			},
			out: true,
		},
		"invalid hardware type ARP packet": {
			in: &ethernet.ARPPacket{
				HardwareType:    ethernet.HardwareTypeChaos,
				ProtocolType:    ethernet.ProtocolTypeIPv4,
				HardwareAddrLen: 6,
				ProtocolAddrLen: 4,
			},
			out: false,
		},
		"invalid protocol type ARP packet": {
			in: &ethernet.ARPPacket{
				HardwareType:    ethernet.HardwareTypeEthernet,
				ProtocolType:    ethernet.ProtocolTypeIPv6,
				HardwareAddrLen: 6,
				ProtocolAddrLen: 4,
			},
			out: false,
		},
		"invalid hardware address length ARP packet": {
			in: &ethernet.ARPPacket{
				HardwareType:    ethernet.HardwareTypeEthernet,
				ProtocolType:    ethernet.ProtocolTypeIPv4,
				HardwareAddrLen: 8,
				ProtocolAddrLen: 4,
			},
			out: false,
		},
		"invalid protocol address lenth ARP packet": {
			in: &ethernet.ARPPacket{
				HardwareType:    ethernet.HardwareTypeEthernet,
				ProtocolType:    ethernet.ProtocolTypeIPv4,
				HardwareAddrLen: 6,
				ProtocolAddrLen: 16,
			},
			out: false,
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()
			assert.Equal(t, tc.out, isValidARPPacket(tc.in))
		})
	}
}

func TestUpdateBindings(t *testing.T) {
	t.Parallel()

	timestamp := time.Now()

	type in struct {
		p               func(p *ethernet.ARPPacket)
		vid             *uint16
		time            time.Time
		bindingsFixture map[string]Binding
	}

	testcases := map[string]struct {
		in  in
		out []Result
	}{
		"new request packet": {
			in: in{
				p: func(p *ethernet.ARPPacket) {
					p.SendHwAddr = net.HardwareAddr{0xc0, 0xff, 0xee, 0x15, 0xc0, 0x01}
				},
				time: timestamp,
			},
			out: []Result{
				{
					IP:    "10.0.0.1",
					MAC:   "c0:ff:ee:15:c0:01",
					Time:  timestamp.Unix(),
					Event: EventNew,
				},
			},
		},
		"new reply packet": {
			in: in{
				p: func(p *ethernet.ARPPacket) {
					p.OpCode = ethernet.OpReply
					p.SendHwAddr = net.HardwareAddr{0xc0, 0xff, 0xee, 0x15, 0xc0, 0x01}
					p.TgtHwAddr = net.HardwareAddr{0xc0, 0xff, 0xee, 0x15, 0xc0, 0x1d}
				},
				time: timestamp,
			},
			out: []Result{
				{
					IP:    "10.0.0.1",
					MAC:   "c0:ff:ee:15:c0:01",
					Time:  timestamp.Unix(),
					Event: EventNew,
				},
				{
					IP:    "10.0.0.2",
					MAC:   "c0:ff:ee:15:c0:1d",
					Time:  timestamp.Unix(),
					Event: EventNew,
				},
			},
		},
		"new VLAN packet": {
			in: in{
				p: func(p *ethernet.ARPPacket) {
					p.SendHwAddr = net.HardwareAddr{0xc0, 0xff, 0xee, 0x15, 0xc0, 0x01}
				},
				vid:  uint16Pointer(2),
				time: timestamp,
			},
			out: []Result{
				{
					IP:    "10.0.0.1",
					MAC:   "c0:ff:ee:15:c0:01",
					Time:  timestamp.Unix(),
					VID:   uint16Pointer(2),
					Event: EventNew,
				},
			},
		},
		"refresh": {
			in: in{
				p: func(p *ethernet.ARPPacket) {
					p.SendHwAddr = net.HardwareAddr{0xc0, 0xff, 0xee, 0x15, 0xc0, 0x01}
				},
				time: timestamp.Add(seenAgainThreshold + time.Second),
				bindingsFixture: map[string]Binding{
					"0_10.0.0.1": {
						IP:   netip.MustParseAddr("10.0.0.1"),
						MAC:  net.HardwareAddr{0xc0, 0xff, 0xee, 0x15, 0xc0, 0x01},
						Time: timestamp,
					},
				},
			},
			out: []Result{
				{
					IP:    "10.0.0.1",
					MAC:   "c0:ff:ee:15:c0:01",
					Time:  timestamp.Add(seenAgainThreshold + time.Second).Unix(),
					Event: EventRefreshed,
				},
			},
		},
		"move": {
			in: in{
				p: func(p *ethernet.ARPPacket) {
					p.SendHwAddr = net.HardwareAddr{0xc0, 0xff, 0xee, 0x15, 0xc0, 0x1d}
				},
				time: timestamp,
				bindingsFixture: map[string]Binding{
					"0_10.0.0.1": {
						IP:   netip.MustParseAddr("10.0.0.1"),
						MAC:  net.HardwareAddr{0xc0, 0xff, 0xee, 0x15, 0xc0, 0x01},
						Time: timestamp,
					},
				},
			},
			out: []Result{
				{
					IP:          "10.0.0.1",
					MAC:         "c0:ff:ee:15:c0:1d",
					PreviousMAC: "c0:ff:ee:15:c0:01",
					Time:        timestamp.Unix(),
					Event:       EventMoved,
				},
			},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			packet := testARPPacket()
			if tc.in.p != nil {
				tc.in.p(packet)
			}

			svc := NewService("lo")
			if tc.in.bindingsFixture != nil {
				svc.bindings = tc.in.bindingsFixture
			}

			res := svc.updateBindings(packet, tc.in.vid, tc.in.time)
			for i, expected := range tc.out {
				assert.Equal(t, expected, res[i])
			}
		})
	}
}

func testARPPacket() *ethernet.ARPPacket {
	return &ethernet.ARPPacket{
		HardwareType:    ethernet.HardwareTypeEthernet,
		ProtocolType:    ethernet.ProtocolTypeIPv4,
		HardwareAddrLen: 6,
		ProtocolAddrLen: 4,
		OpCode:          ethernet.OpRequest,
		SendIPAddr:      netip.MustParseAddr("10.0.0.1"),
		TgtIPAddr:       netip.MustParseAddr("10.0.0.2"),
	}
}

func TestServiceHandlePacket(t *testing.T) {
	t.Parallel()

	timestamp := time.Now()
	testcases := map[string]struct {
		in  pcap.Packet
		out []Result
		err error
	}{
		"valid request packet": {
			in: pcap.Packet{
				// generated from tcpdump
				B: []byte{
					0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x84, 0x39, 0xc0, 0x0b, 0x22, 0x25, 0x81, 0x00, 0x00, 0x02,
					0x08, 0x06, 0x00, 0x01, 0x08, 0x00, 0x06, 0x04, 0x00, 0x01, 0x84, 0x39, 0xc0, 0x0b, 0x22, 0x25,
					0xc0, 0xa8, 0x0a, 0x1a, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xc0, 0xa8, 0x0a, 0x19, 0x00, 0x00,
					0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
				},
				Info: gopacket.CaptureInfo{
					Timestamp: timestamp,
				},
			},
			out: []Result{
				{
					IP:    "192.168.10.26",
					MAC:   "84:39:c0:0b:22:25",
					VID:   uint16Pointer(2),
					Time:  timestamp.Unix(),
					Event: EventNew,
				},
			},
		},
		"valid reply packet": {
			in: pcap.Packet{
				B: []byte{
					0x24, 0x4b, 0xfe, 0xe1, 0xea, 0x26, 0x80, 0x61, 0x5f, 0x08, 0xfc, 0x16, 0x08, 0x06, 0x00, 0x01,
					0x08, 0x00, 0x06, 0x04, 0x00, 0x02, 0x80, 0x61, 0x5f, 0x08, 0xfc, 0x16, 0xc0, 0xa8, 0x01, 0x6c,
					0x24, 0x4b, 0xfe, 0xe1, 0xea, 0x26, 0xc0, 0xa8, 0x01, 0x50,
				},
			},
			out: []Result{
				{
					IP:    "192.168.1.108",
					MAC:   "80:61:5f:08:fc:16",
					VID:   nil,
					Time:  timestamp.Unix(),
					Event: EventNew,
				},
				{
					IP:    "192.168.1.80",
					MAC:   "24:4b:fe:e1:ea:26",
					VID:   nil,
					Time:  timestamp.Unix(),
					Event: EventNew,
				},
			},
		},
		"empty packet": {
			err: ErrEmptyPacket,
		},
		"malformed packet": {
			in: pcap.Packet{
				B: []byte{
					0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x84, 0x39, 0xc0, 0x0b, 0x22,
					0x08, 0x06, 0x00, 0x01, 0x08, 0x06, 0x04, 0x00, 0x01, 0x84,
					0xc0, 0xa8, 0x0a, 0x1a, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xc0,
					0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
				},
			},
		},
		"short packet": {
			in: pcap.Packet{
				B: []byte{
					0x24, 0x4b, 0xfe, 0xe1, 0xea, 0x26, 0x80, 0x61, 0x5f, 0x08, 0xfc, 0x16, 0x08, 0x06, 0x00, 0x01,
					0x08, 0x00, 0x06, 0x04, 0x00, 0x02, 0x80, 0xfc, 0x16, 0xc0, 0xa8, 0x01, 0x6c,
					0x24, 0x4b, 0xfe, 0xe1, 0xea, 0x26, 0xc0, 0xa8, 0x01, 0x50,
				},
			},
			err: ethernet.ErrMalformedARPPacket,
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			svc := NewService("")
			res, err := svc.handlePacket(tc.in)
			assert.ErrorIs(t, err, tc.err)

			if err == nil {
				for i, expected := range tc.out {
					assert.Equal(t, expected, res[i])
				}
			} else {
				assert.Nil(t, res)
			}
		})
	}
}
