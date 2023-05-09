package ethernet

/*
	Copyright 2023 Canonical Ltd.  This software is licensed under the
	GNU Affero General Public License version 3 (see the file LICENSE).
*/

import (
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"net"
	"net/netip"
)

type HardwareType uint16

//go:generate go run golang.org/x/tools/cmd/stringer -type=HardwareType -trimprefix=HardwareType

const (
	// HardwareTypeReserved is a special value for hardware type
	HardwareTypeReserved HardwareType = 0 // see RFC5494
	// HardwareTypeEthernet is the hardware type value for Ethernet
	// we only care about ethernet, but additional types are defined for
	// testing and possible future use
	HardwareTypeEthernet HardwareType = 1
	// HardwareTypeExpEth is the hardware type for experimental ethernet
	HardwareTypeExpEth HardwareType = 2
	// HardwareTypeAX25 is the hardware type for Radio AX.25
	HardwareTypeAX25 HardwareType = 3
	// HardwareTypeChaos is a chaos value for hardware type
	HardwareTypeChaos HardwareType = 4
	// HardwareTypeIEEE802 is for IEEE 802 networks
	HardwareTypeIEEE802 HardwareType = 5

	// skipping propriatary networks

	// HardwareTypeFiberChannel is the hardware type for fiber channel
	HardwareTypeFiberChannel HardwareType = 18
	// HardwareTypeSerialLine is the hardware type for serial line
	HardwareTypeSerialLine HardwareType = 19
	// HardwareTypeHIPARP is the hardware type for HIPARP
	HardwareTypeHIPARP HardwareType = 28
	// HardwareTypeIPARPISO7163 is the hardware type for IP and ARP over ISO 7816-3
	HardwareTypeIPARPISO7163 HardwareType = 29
	// HardwareTypeARPSec is the hardware type for ARPSec
	HardwareTypeARPSec HardwareType = 30
	// HardwareTypeIPSec is the hardware type for IPSec tunnel
	HardwareTypeIPSec HardwareType = 31
	// HardwareTypeInfiniBand is the hardware type for InfiniBand
	HardwareTypeInfiniBand HardwareType = 32
)

type ProtocolType uint16

//go:generate go run golang.org/x/tools/cmd/stringer -type=ProtocolType -trimprefix=ProtocolType

const (
	// ProtocolTypeIPv4 is the value for IPv4 ARP packets
	ProtocolTypeIPv4 ProtocolType = 0x0800
	// ProtocolTypeIPv6 is the value for IPv6 ARP packets,
	// which shouldn't be used, this is defined for testing purposes
	ProtocolTypeIPv6 ProtocolType = 0x86dd
	// ProtocolTypeARP is the value for ARP packets with a protocol
	// value of ARP itself
	ProtocolTypeARP ProtocolType = 0x0806
)

const (
	// OpReserved is a special reserved OpCode
	OpReserved uint16 = iota // see RFC5494
	// OpRequest is the OpCode for ARP requests
	OpRequest
	// OpReply is the OpCode for ARP replies
	OpReply
)

var (
	// ErrMalformedPacket is an error returned when parsing a malformed ARP packet
	ErrMalformedARPPacket = errors.New("malformed ARP packet")
)

// ARPPacket is a struct containing the data of an ARP packet
type ARPPacket struct {
	SendIPAddr      netip.Addr
	TgtIPAddr       netip.Addr
	SendHwAddr      net.HardwareAddr
	TgtHwAddr       net.HardwareAddr
	HardwareType    HardwareType
	OpCode          uint16
	ProtocolType    ProtocolType
	HardwareAddrLen uint8
	ProtocolAddrLen uint8
}

func checkPacketLen(buf []byte, bytesRead, length int) error {
	if len(buf) == 0 {
		return io.ErrUnexpectedEOF
	}

	if len(buf[bytesRead:]) < length {
		return ErrMalformedARPPacket
	}

	return nil
}

// UnmarshalBinary takes the ARP packet bytes and parses it into a Packet
func (pkt *ARPPacket) UnmarshalBinary(buf []byte) error {
	var (
		bytesRead int
	)

	err := checkPacketLen(buf, bytesRead, 8)
	if err != nil {
		return fmt.Errorf("%w: packet missing initial ARP fields", err)
	}

	pkt.HardwareType = HardwareType(binary.BigEndian.Uint16(buf[0:2]))
	pkt.ProtocolType = ProtocolType(binary.BigEndian.Uint16(buf[2:4]))
	pkt.HardwareAddrLen = buf[4]
	pkt.ProtocolAddrLen = buf[5]
	pkt.OpCode = binary.BigEndian.Uint16(buf[6:8])

	bytesRead = 8
	hwdAddrLen := int(pkt.HardwareAddrLen)
	ipAddrLen := int(pkt.ProtocolAddrLen)

	err = checkPacketLen(buf, bytesRead, hwdAddrLen)
	if err != nil {
		return fmt.Errorf("%w: packet too short for sender hardware address", err)
	}

	sendHwAddrBuf := make([]byte, hwdAddrLen)
	copy(sendHwAddrBuf, buf[bytesRead:bytesRead+hwdAddrLen])
	pkt.SendHwAddr = sendHwAddrBuf
	bytesRead += hwdAddrLen

	err = checkPacketLen(buf, bytesRead, ipAddrLen)
	if err != nil {
		return fmt.Errorf("%w: packet too short for sender IP address", err)
	}

	var ok bool

	sendIPAddrBuf := make([]byte, ipAddrLen)
	copy(sendIPAddrBuf, buf[bytesRead:bytesRead+ipAddrLen])

	pkt.SendIPAddr, ok = netip.AddrFromSlice(sendIPAddrBuf)
	if !ok {
		return fmt.Errorf("%w: invalid sender IP address", ErrMalformedARPPacket)
	}

	bytesRead += ipAddrLen

	err = checkPacketLen(buf, bytesRead, hwdAddrLen)
	if err != nil {
		return fmt.Errorf("%w: packet too short for target hardware address", err)
	}

	tgtHwAddrBuf := make([]byte, hwdAddrLen)
	copy(tgtHwAddrBuf, buf[bytesRead:bytesRead+hwdAddrLen])

	pkt.TgtHwAddr = tgtHwAddrBuf
	bytesRead += hwdAddrLen

	err = checkPacketLen(buf, bytesRead, ipAddrLen)
	if err != nil {
		return fmt.Errorf("%w: packet too short for target IP address", err)
	}

	tgtIPAddrBuf := make([]byte, ipAddrLen)
	copy(tgtIPAddrBuf, buf[bytesRead:bytesRead+ipAddrLen])

	pkt.TgtIPAddr, ok = netip.AddrFromSlice(tgtIPAddrBuf)
	if !ok {
		return fmt.Errorf("%w: invalid target IP address", ErrMalformedARPPacket)
	}

	return nil
}
