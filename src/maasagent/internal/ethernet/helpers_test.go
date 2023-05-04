package ethernet

/*
	Copyright 2023 Canonical Ltd.  This software is licensed under the
	GNU Affero General Public License version 3 (see the file LICENSE).
*/

import (
	"net"
	"net/netip"
	"testing"

	"github.com/stretchr/testify/assert"
)

type basePacketTestCase struct {
	Name string
	Err  error
	In   []byte
}

type unmarshalVLANCase struct {
	Out *VLAN
	basePacketTestCase
}

type unmarshalEthernetCase struct {
	Out *EthernetFrame
	basePacketTestCase
}

type unmarshalCase struct {
	Out *ARPPacket
	basePacketTestCase
}

func parseMACNoError(s string) net.HardwareAddr {
	addr, _ := net.ParseMAC(s)
	return addr
}

func parseAddrNoError(s string) netip.Addr {
	addr, _ := netip.ParseAddr(s)
	return addr
}

func ethernetTypeToString(t uint16) string {
	switch t {
	case EthernetTypeLLC:
		return "LLC"
	case EthernetTypeIPv4:
		return "IPv4"
	case EthernetTypeARP:
		return "ARP"
	case EthernetTypeIPv6:
		return "IPv6"
	case EthernetTypeVLAN:
		return "VLAN"
	}

	return "unknown"
}

func hardwareTypeToString(t uint16) string {
	switch t {
	case HardwareTypeReserved:
		return "Reserved"
	case HardwareTypeEthernet:
		return "Ethernet"
	case HardwareTypeExpEth:
		return "Experimetnal Ethernet"
	case HardwareTypeAX25:
		return "AX25"
	case HardwareTypeChaos:
		return "Chaos"
	case HardwareTypeIEEE802:
		return "802"
	case HardwareTypeFiberChannel:
		return "Fiber Channel"
	case HardwareTypeSerialLine:
		return "Serial Line"
	case HardwareTypeHIPARP:
		return "HIPARP"
	case HardwareTypeIPARPISO7163:
		return "IP-ARP"
	case HardwareTypeARPSec:
		return "ARP-Sec"
	case HardwareTypeIPSec:
		return "IP-Sec"
	case HardwareTypeInfiniBand:
		return "InfiniBand"
	}

	return "unknown"
}

func protocolTypeToString(t uint16) string {
	switch t {
	case ProtocolTypeIPv4:
		return "IPv4"
	case ProtocolTypeIPv6:
		return "IPv6"
	case ProtocolTypeARP:
		return "ARP"
	}

	return "unknown"
}

func compareVLANs(t *testing.T, expected, actual *VLAN) {
	assert.Equalf(t, expected.Priority, actual.Priority, "expected Priority to be %d", int(expected.Priority))
	assert.Equalf(t, expected.DropEligible, actual.DropEligible, "exptected DropEligible to be %v", expected.DropEligible)
	assert.Equalf(t, expected.ID, actual.ID, "expected ID to be %d", int(expected.ID))
	assert.Equalf(t, expected.EthernetType, actual.EthernetType, "expected EthernetType to be %s", ethernetTypeToString(expected.EthernetType))
}

func compareEthernetFrames(t *testing.T, expected, actual *EthernetFrame) {
	assert.Equalf(t, expected.SrcMAC, actual.SrcMAC, "expected SrcMAC to be %s", expected.SrcMAC)
	assert.Equalf(t, expected.DstMAC, actual.DstMAC, "expected DstMAC to be %s", expected.DstMAC)
	assert.Equalf(t, expected.EthernetType, actual.EthernetType, "expected EthernetType to be %s", ethernetTypeToString(expected.EthernetType))
	assert.Equalf(t, expected.Len, actual.Len, "expected a length of %d", int(expected.Len))
	assert.Equalf(t, expected.Payload, actual.Payload, "expected a payload of %x", expected.Payload)
}

func compareARPPacket(t *testing.T, expected, actual *ARPPacket) {
	assert.Equalf(t, expected.HardwareType, actual.HardwareType, "expected a HardwareType of %s", hardwareTypeToString(expected.HardwareType))
	assert.Equalf(t, expected.ProtocolType, actual.ProtocolType, "expected a ProtocolType of %s", protocolTypeToString(expected.ProtocolType))
	assert.Equalf(t, expected.HardwareAddrLen, actual.HardwareAddrLen, "expected a HardwareAddrLen of %d", int(expected.HardwareAddrLen))
	assert.Equalf(t, expected.ProtocolAddrLen, actual.ProtocolAddrLen, "expected a ProtocolAddrLen of %d", int(expected.ProtocolAddrLen))
	assert.Equalf(t, expected.OpCode, actual.OpCode, "expected a ProtocolLen of %d", int(expected.OpCode))
	assert.Equalf(t, expected.SendHwdAddr, actual.SendHwdAddr, "expected a SendHwdAddr of %s", expected.SendHwdAddr)
	assert.Equalf(t, expected.SendIPAddr, actual.SendIPAddr, "expected a SendIPAddr of %s", expected.SendIPAddr)
	assert.Equalf(t, expected.TgtHwdAddr, actual.TgtHwdAddr, "expected a TgtHwdAddr of %s", expected.TgtHwdAddr)
	assert.Equalf(t, expected.TgtIPAddr, actual.TgtIPAddr, "expected a TgtIPAddr of %s", expected.TgtIPAddr)
}
