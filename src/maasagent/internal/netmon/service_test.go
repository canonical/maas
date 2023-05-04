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

	"launchpad.net/maas/maas/src/maasagent/internal/ethernet"
)

func uint16Pointer(v uint16) *uint16 {
	return &v
}

type isValidARPPacketCase struct {
	In   *ethernet.ARPPacket
	Name string
	Out  bool
}

func TestIsValidARPPacket(t *testing.T) {
	table := []isValidARPPacketCase{
		{
			Name: "ValidARPPacket",
			In: &ethernet.ARPPacket{
				HardwareType:    ethernet.HardwareTypeEthernet,
				ProtocolType:    ethernet.ProtocolTypeIPv4,
				HardwareAddrLen: 6,
				ProtocolAddrLen: 4,
			},
			Out: true,
		},
		{
			Name: "InvalidHardwareTypeARPPacket",
			In: &ethernet.ARPPacket{
				HardwareType:    ethernet.HardwareTypeChaos,
				ProtocolType:    ethernet.ProtocolTypeIPv4,
				HardwareAddrLen: 6,
				ProtocolAddrLen: 4,
			},
			Out: false,
		},
		{
			Name: "InvalidProtocolTypeARPPacket",
			In: &ethernet.ARPPacket{
				HardwareType:    ethernet.HardwareTypeEthernet,
				ProtocolType:    ethernet.ProtocolTypeIPv6,
				HardwareAddrLen: 6,
				ProtocolAddrLen: 4,
			},
			Out: false,
		},
		{
			Name: "InvalidHardwareAddrLenARPPacket",
			In: &ethernet.ARPPacket{
				HardwareType:    ethernet.HardwareTypeEthernet,
				ProtocolType:    ethernet.ProtocolTypeIPv4,
				HardwareAddrLen: 8,
				ProtocolAddrLen: 4,
			},
			Out: false,
		},
		{
			Name: "InvalidProtocolAddrLenARPPacket",
			In: &ethernet.ARPPacket{
				HardwareType:    ethernet.HardwareTypeEthernet,
				ProtocolType:    ethernet.ProtocolTypeIPv4,
				HardwareAddrLen: 6,
				ProtocolAddrLen: 16,
			},
			Out: false,
		},
	}
	for _, tcase := range table {
		t.Run(tcase.Name, func(tt *testing.T) {
			assert.Equalf(tt, tcase.Out, isValidARPPacket(tcase.In), "expected the result to be %v", tcase.Out)
		})
	}
}

type updateBindingsArgs struct {
	Pkt  *ethernet.ARPPacket
	VID  *uint16
	Time time.Time
}

type updateBindingsCase struct {
	Name            string
	BindingsFixture map[string]Binding
	In              updateBindingsArgs
	Out             []Result
}

func TestUpdateBindings(t *testing.T) {
	timestamp := time.Now()
	testIP1 := net.ParseIP("10.0.0.1").To4()
	testIP2 := net.ParseIP("10.0.0.2").To4()
	table := []updateBindingsCase{
		{
			Name: "NewRequestPacket",
			In: updateBindingsArgs{
				Pkt: &ethernet.ARPPacket{
					HardwareType:    ethernet.HardwareTypeEthernet,
					ProtocolType:    ethernet.ProtocolTypeIPv4,
					HardwareAddrLen: 6,
					ProtocolAddrLen: 4,
					OpCode:          ethernet.OpRequest,
					SendHwdAddr:     net.HardwareAddr{0xc0, 0xff, 0xee, 0x15, 0xc0, 0x01},
					SendIPAddr:      netip.AddrFrom4([4]byte{testIP1[0], testIP1[1], testIP1[2], testIP1[3]}),
					TgtIPAddr:       netip.AddrFrom4([4]byte{testIP2[0], testIP2[1], testIP2[2], testIP2[3]}),
				},
				Time: timestamp,
			},
			Out: []Result{
				{
					IP:    "10.0.0.1",
					MAC:   "c0:ff:ee:15:c0:01",
					Time:  timestamp.Unix(),
					Event: EventNew,
				},
			},
		},
		{
			Name: "NewReplyPacket",
			In: updateBindingsArgs{
				Pkt: &ethernet.ARPPacket{
					HardwareType:    ethernet.HardwareTypeEthernet,
					ProtocolType:    ethernet.ProtocolTypeIPv4,
					HardwareAddrLen: 6,
					ProtocolAddrLen: 4,
					OpCode:          ethernet.OpReply,
					SendHwdAddr:     net.HardwareAddr{0xc0, 0xff, 0xee, 0x15, 0xc0, 0x01},
					SendIPAddr:      netip.AddrFrom4([4]byte{testIP1[0], testIP1[1], testIP1[2], testIP1[3]}),
					TgtHwdAddr:      net.HardwareAddr{0xc0, 0xff, 0xee, 0x15, 0xc0, 0x1d},
					TgtIPAddr:       netip.AddrFrom4([4]byte{testIP2[0], testIP2[1], testIP2[2], testIP2[3]}),
				},
				Time: timestamp,
			},
			Out: []Result{
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
		{
			Name: "NewVLANPacket",
			In: updateBindingsArgs{
				Pkt: &ethernet.ARPPacket{
					HardwareType:    ethernet.HardwareTypeEthernet,
					ProtocolType:    ethernet.ProtocolTypeIPv4,
					HardwareAddrLen: 6,
					ProtocolAddrLen: 4,
					OpCode:          ethernet.OpRequest,
					SendHwdAddr:     net.HardwareAddr{0xc0, 0xff, 0xee, 0x15, 0xc0, 0x01},
					SendIPAddr:      netip.AddrFrom4([4]byte{testIP1[0], testIP1[1], testIP1[2], testIP1[3]}),
					TgtIPAddr:       netip.AddrFrom4([4]byte{testIP2[0], testIP2[1], testIP2[2], testIP2[3]}),
				},
				VID:  uint16Pointer(2),
				Time: timestamp,
			},
			Out: []Result{
				{
					IP:    "10.0.0.1",
					MAC:   "c0:ff:ee:15:c0:01",
					Time:  timestamp.Unix(),
					VID:   uint16Pointer(2),
					Event: EventNew,
				},
			},
		},
		{
			Name: "Refresh",
			BindingsFixture: map[string]Binding{
				"0_10.0.0.1": {
					IP:   netip.AddrFrom4([4]byte{testIP1[0], testIP1[1], testIP1[2], testIP1[3]}),
					MAC:  net.HardwareAddr{0xc0, 0xff, 0xee, 0x15, 0xc0, 0x01},
					Time: timestamp,
				},
			},
			In: updateBindingsArgs{
				Pkt: &ethernet.ARPPacket{
					HardwareType:    ethernet.HardwareTypeEthernet,
					ProtocolType:    ethernet.ProtocolTypeIPv4,
					HardwareAddrLen: 6,
					ProtocolAddrLen: 4,
					OpCode:          ethernet.OpRequest,
					SendHwdAddr:     net.HardwareAddr{0xc0, 0xff, 0xee, 0x15, 0xc0, 0x01},
					SendIPAddr:      netip.AddrFrom4([4]byte{testIP1[0], testIP1[1], testIP1[2], testIP1[3]}),
					TgtIPAddr:       netip.AddrFrom4([4]byte{testIP2[0], testIP2[1], testIP2[2], testIP2[3]}),
				},
				Time: timestamp.Add(seenAgainThreshold + time.Second),
			},
			Out: []Result{
				{
					IP:    "10.0.0.1",
					MAC:   "c0:ff:ee:15:c0:01",
					Time:  timestamp.Add(seenAgainThreshold + time.Second).Unix(),
					Event: EventRefreshed,
				},
			},
		},
		{
			Name: "Move",
			BindingsFixture: map[string]Binding{
				"0_10.0.0.1": {
					IP:   netip.AddrFrom4([4]byte{testIP1[0], testIP1[1], testIP1[2], testIP1[3]}),
					MAC:  net.HardwareAddr{0xc0, 0xff, 0xee, 0x15, 0xc0, 0x01},
					Time: timestamp,
				},
			},
			In: updateBindingsArgs{
				Pkt: &ethernet.ARPPacket{
					HardwareType:    ethernet.HardwareTypeEthernet,
					ProtocolType:    ethernet.ProtocolTypeIPv4,
					HardwareAddrLen: 6,
					ProtocolAddrLen: 4,
					OpCode:          ethernet.OpRequest,
					SendHwdAddr:     net.HardwareAddr{0xc0, 0xff, 0xee, 0x15, 0xc0, 0x1d},
					SendIPAddr:      netip.AddrFrom4([4]byte{testIP1[0], testIP1[1], testIP1[2], testIP1[3]}),
					TgtIPAddr:       netip.AddrFrom4([4]byte{testIP2[0], testIP2[1], testIP2[2], testIP2[3]}),
				},
				Time: timestamp,
			},
			Out: []Result{
				{
					IP:    "10.0.0.1",
					MAC:   "c0:ff:ee:15:c0:1d",
					Time:  timestamp.Unix(),
					Event: EventMoved,
				},
			},
		},
	}

	for _, tcase := range table {
		t.Run(tcase.Name, func(tt *testing.T) {
			svc := NewService("lo")
			if tcase.BindingsFixture != nil {
				svc.bindings = tcase.BindingsFixture
			}

			res := svc.updateBindings(tcase.In.Pkt, tcase.In.VID, tcase.In.Time)
			for i, expected := range tcase.Out {
				var expectedVID int
				if expected.VID != nil {
					expectedVID = int(*expected.VID)
				}

				assert.Equalf(tt, expected.IP, res[i].IP, "expected Result at index of %d to have the IP %s", i, expected.IP)
				assert.Equalf(tt, expected.MAC, res[i].MAC, "expected Result at index of %d to have the MAC %s", i, expected.MAC)
				assert.Equalf(tt, expected.VID, res[i].VID, "expected Result at index of %d to have the VID %d", i, expectedVID)
				assert.Equalf(tt, expected.Time, res[i].Time, "expected Result at index of %d to have the Time of %d", i, int(expected.Time))
				assert.Equalf(tt, expected.Event, res[i].Event, "expected Result at index of %d to have the Event of %s", i, expected.Event)
			}
		})
	}
}

type handlePacketCase struct {
	Err  error
	In   pcap.Packet
	Name string
	Out  []Result
}

func TestServiceHandlePacket(t *testing.T) {
	timestamp := time.Now()
	table := []handlePacketCase{
		{
			Name: "ValidRequestPacket",
			In: pcap.Packet{
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
			Out: []Result{
				{
					IP:    "192.168.10.26",
					MAC:   "84:39:c0:0b:22:25",
					VID:   uint16Pointer(2),
					Time:  timestamp.Unix(),
					Event: EventNew,
				},
			},
		},
		{
			Name: "ValidReplyPacket",
			In: pcap.Packet{
				B: []byte{
					0x24, 0x4b, 0xfe, 0xe1, 0xea, 0x26, 0x80, 0x61, 0x5f, 0x08, 0xfc, 0x16, 0x08, 0x06, 0x00, 0x01,
					0x08, 0x00, 0x06, 0x04, 0x00, 0x02, 0x80, 0x61, 0x5f, 0x08, 0xfc, 0x16, 0xc0, 0xa8, 0x01, 0x6c,
					0x24, 0x4b, 0xfe, 0xe1, 0xea, 0x26, 0xc0, 0xa8, 0x01, 0x50,
				},
			},
			Out: []Result{
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
		{
			Name: "EmptyPacket",
			Err:  ErrEmptyPacket,
		},
		{
			Name: "MalformedPacket",
			In: pcap.Packet{
				B: []byte{
					0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x84, 0x39, 0xc0, 0x0b, 0x22,
					0x08, 0x06, 0x00, 0x01, 0x08, 0x06, 0x04, 0x00, 0x01, 0x84,
					0xc0, 0xa8, 0x0a, 0x1a, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xc0,
					0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
				},
			},
			// should return nil, nil
		},
		{
			Name: "ShortPacket",
			In: pcap.Packet{
				B: []byte{
					0x24, 0x4b, 0xfe, 0xe1, 0xea, 0x26, 0x80, 0x61, 0x5f, 0x08, 0xfc, 0x16, 0x08, 0x06, 0x00, 0x01,
					0x08, 0x00, 0x06, 0x04, 0x00, 0x02, 0x80, 0xfc, 0x16, 0xc0, 0xa8, 0x01, 0x6c,
					0x24, 0x4b, 0xfe, 0xe1, 0xea, 0x26, 0xc0, 0xa8, 0x01, 0x50,
				},
			},
			Err: ethernet.ErrMalformedARPPacket,
		},
	}

	svc := NewService("")

	for _, tcase := range table {
		t.Run(tcase.Name, func(tt *testing.T) {
			res, err := svc.handlePacket(tcase.In)
			assert.ErrorIsf(tt, err, tcase.Err, "expected handlePacket to return an error of: %s", tcase.Err)

			if tcase.Out != nil {
				for i, expected := range tcase.Out {
					assert.Equalf(tt, expected.IP, res[i].IP, "expected result at index %d to have an IP address of %s", i, expected.IP)
					assert.Equalf(tt, expected.MAC, res[i].MAC, "expected result at index %d to have a MAC address of %s", i, expected.MAC)
					assert.Equalf(tt, expected.VID, res[i].VID, "expected result at index %d to have a VID of %v", i, expected.VID)
					assert.Equalf(tt, expected.Time, res[i].Time, "expected result at index %d to have a Time of %s", i, expected.Time)
				}
			} else {
				assert.Nil(tt, res)
			}
		})
	}
}
