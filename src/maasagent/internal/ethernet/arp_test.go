package ethernet

/*
	Copyright 2023 Canonical Ltd.  This software is licensed under the
	GNU Affero General Public License version 3 (see the file LICENSE).
*/

import (
	"io"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestUnmarshal(t *testing.T) {
	table := []unmarshalCase{
		{
			basePacketTestCase: basePacketTestCase{
				Name: "ValidRequestPacket",
				// generated from tcpdump
				In: []byte{
					0x00, 0x01, 0x08, 0x00, 0x06, 0x04, 0x00, 0x01, 0x84, 0x39, 0xc0, 0x0b, 0x22, 0x25,
					0xc0, 0xa8, 0x0a, 0x1a, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xc0, 0xa8, 0x0a, 0x19,
				},
			},
			Out: &ARPPacket{
				HardwareType:    HardwareTypeEthernet,
				ProtocolType:    ProtocolTypeIPv4,
				HardwareAddrLen: 6,
				ProtocolAddrLen: 4,
				OpCode:          OpRequest,
				SendHwdAddr:     parseMACNoError("84:39:c0:0b:22:25"),
				SendIPAddr:      parseAddrNoError("192.168.10.26"),
				TgtHwdAddr:      parseMACNoError("00:00:00:00:00:00"),
				TgtIPAddr:       parseAddrNoError("192.168.10.25"),
			},
		},
		{
			basePacketTestCase: basePacketTestCase{
				Name: "ValidReplyPacket",
				// generated from tcpdump
				In: []byte{
					0x00, 0x01, 0x08, 0x00, 0x06, 0x04, 0x00, 0x02, 0x80, 0x61, 0x5f, 0x08, 0xfc, 0x16, 0xc0, 0xa8,
					0x01, 0x6c, 0x24, 0x4b, 0xfe, 0xe1, 0xea, 0x26, 0xc0, 0xa8, 0x01, 0x50,
				},
			},
			Out: &ARPPacket{
				HardwareType:    HardwareTypeEthernet,
				ProtocolType:    ProtocolTypeIPv4,
				HardwareAddrLen: 6,
				ProtocolAddrLen: 4,
				OpCode:          OpReply,
				SendHwdAddr:     parseMACNoError("80:61:5f:08:fc:16"),
				SendIPAddr:      parseAddrNoError("192.168.1.108"),
				TgtHwdAddr:      parseMACNoError("24:4b:fe:e1:ea:26"),
				TgtIPAddr:       parseAddrNoError("192.168.1.80"),
			},
		},
		{
			basePacketTestCase: basePacketTestCase{
				Name: "EmptyPacket",
				Err:  io.ErrUnexpectedEOF,
			},
		},
		{
			basePacketTestCase: basePacketTestCase{
				Name: "TooShortPacket",
				In: []byte{
					0x00, 0x01, 0x08, 0x00, 0x06, 0x04, 0x00, 0x01, 0x84, 0x39, 0xc0, 0x0b, 0x22, 0x25,
					0xc0, 0xa8,
				},
				Err: ErrMalformedARPPacket,
			},
		},
	}

	for _, tcase := range table {
		t.Run(tcase.Name, func(tt *testing.T) {
			res := &ARPPacket{}

			err := res.UnmarshalBinary(tcase.In)
			assert.ErrorIsf(tt, err, tcase.Err, "expected Unmarshal to return an error of %s", tcase.Err)

			if tcase.Out != nil {
				compareARPPacket(tt, tcase.Out, res)
			}
		})
	}
}
