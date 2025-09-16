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
	"database/sql"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"fmt"
	"math"
	"net"
	"strconv"
	"strings"
	"sync"
	"syscall"

	"github.com/canonical/microcluster/v2/state"
	"github.com/google/gopacket"
	"github.com/google/gopacket/layers"
	"github.com/insomniacslk/dhcp/dhcpv4"
	"github.com/rs/zerolog/log"
)

var (
	ErrNotDHCPv4             = errors.New("not a DHCPv4 message")
	ErrHandlerNotInitialized = errors.New("handler is not properly initialized")
	ErrNoSuitableServerIP    = errors.New("unable to determine server IP for DISCOVER")
	ErrInvalidMessageType    = errors.New("received a message of an unhandled type")
	ErrNotAnIP               = errors.New("attempted to parse non-IP as an IP")
	ErrNoIPRequested         = errors.New("no IP requested in REQUEST message")
	ErrPacketNotSerializable = errors.New("packet cannot be serialized")
	ErrInvalidOptionValue    = errors.New("the option provided is of an invalid value")
)

const (
	OptionTypeUint8 = iota
	OptionTypeUint16
	OptionTypeUint32
	OptionTypeUint64
	OptionTypeString
	OptionTypeIPv4
	OptionTypeIPv6
	OptionTypeIPv4List
	OptionTypeIPv6List
	OptionTypeHex
	OptionTypeSubOption
)

type optionMarshaler func(s string) ([]byte, error)

var (
	optionMarshalers = map[int]optionMarshaler{
		OptionTypeUint8: func(s string) ([]byte, error) {
			n, err := strconv.Atoi(s)
			if err != nil {
				return nil, err
			}

			if n > int(math.MaxUint8) {
				return nil, ErrInvalidOptionValue
			}

			return []byte{uint8(n)}, nil
		},
		OptionTypeUint16: func(s string) ([]byte, error) {
			n, err := strconv.Atoi(s)
			if err != nil {
				return nil, err
			}

			if n > int(math.MaxUint16) {
				return nil, ErrInvalidOptionValue
			}

			buf := make([]byte, 2)

			binary.BigEndian.PutUint16(buf, uint16(n))

			return buf, nil
		},
		OptionTypeUint32: func(s string) ([]byte, error) {
			n, err := strconv.Atoi(s)
			if err != nil {
				return nil, err
			}

			if n > int(math.MaxUint32) {
				return nil, ErrInvalidOptionValue
			}

			buf := make([]byte, 4)

			binary.BigEndian.PutUint32(buf, uint32(n))

			return buf, nil
		},
		OptionTypeUint64: func(s string) ([]byte, error) {
			n, err := strconv.Atoi(s)
			if err != nil {
				return nil, err
			}

			buf := make([]byte, 8)

			binary.BigEndian.PutUint64(buf, uint64(n))

			return buf, nil
		},
		OptionTypeIPv4: ipOptionMarshal(4),
		OptionTypeIPv6: ipOptionMarshal(6),
		OptionTypeIPv4List: func(s string) ([]byte, error) {
			list := strings.Split(s, ",")

			buf := make([]byte, 4*len(list))
			for i, addr := range list {
				ipBytes, err := ipOptionMarshal(4)(strings.TrimSpace(addr))
				if err != nil {
					return nil, err
				}

				if len(ipBytes) != 4 {
					return nil, ErrInvalidOptionValue
				}

				copy(buf[i*4:(i*4)+4], ipBytes)
			}

			return buf, nil
		},
		OptionTypeIPv6List: func(s string) ([]byte, error) {
			list := strings.Split(s, ",")

			buf := make([]byte, 16*len(list))
			for i, addr := range list {
				ipBytes, err := ipOptionMarshal(6)(strings.TrimSpace(addr))
				if err != nil {
					return nil, err
				}

				if len(ipBytes) != 16 {
					return nil, ErrInvalidOptionValue
				}

				copy(buf[i*16:(i*16)+16], ipBytes)
			}

			return buf, nil
		},
		OptionTypeHex: hex.DecodeString,
		// TODO: support suboptions
	}
)

func ipOptionMarshal(ipVer int) optionMarshaler {
	return func(s string) ([]byte, error) {
		ip := net.ParseIP(s)
		if ip == nil {
			return nil, ErrNotAnIP
		}

		if ip4 := ip.To4(); ip4 != nil {
			if ipVer != 4 {
				return ip, nil
			}

			return ip4, nil
		}

		if ipVer == 4 {
			return nil, ErrInvalidOptionValue
		}

		return ip, nil
	}
}

func getDHCPv4OptionType(optCode uint16) int {
	// custom options
	if optCode >= 224 && optCode < 255 {
		// TODO: lookup custom option type
		return OptionTypeString
	}

	switch optCode {
	case uint16(dhcpv4.OptionSubnetMask): // we already calculate mask as byte
		return OptionTypeHex
	case uint16(dhcpv4.OptionRouter), uint16(dhcpv4.OptionTimeServer), uint16(dhcpv4.OptionNameServer), uint16(dhcpv4.OptionLogServer):
		return OptionTypeIPv4
	case uint16(dhcpv4.OptionBroadcastAddress), uint16(dhcpv4.OptionServerIdentifier): // new case for readability
		return OptionTypeIPv4
	case uint16(dhcpv4.OptionDomainNameServer), uint16(dhcpv4.OptionNTPServers):
		return OptionTypeIPv4List
	case uint16(dhcpv4.OptionInterfaceMTU):
		return OptionTypeUint16
	case uint16(dhcpv4.OptionIPAddressLeaseTime):
		return OptionTypeUint32
	}

	return OptionTypeString
}

type DORAHandler struct {
	allocator             Allocator4
	clusterState          state.State
	server                *Server
	discoverReplyOverride func(context.Context, int, *dhcpv4.DHCPv4) error
	requestReplyOverride  func(context.Context, *dhcpv4.DHCPv4) error
	informReplyOverride   func(context.Context, *dhcpv4.DHCPv4) error
	stateLock             sync.RWMutex
}

func NewDORAHandler(a Allocator4) *DORAHandler {
	return &DORAHandler{
		allocator: a,
	}
}

func (d *DORAHandler) SetClusterState(s state.State) {
	d.stateLock.Lock()
	defer d.stateLock.Unlock()

	d.clusterState = s
}

func (d *DORAHandler) ServeDHCPv4(ctx context.Context, msg Message) error {
	if msg.Pkt4 == nil {
		return ErrNotDHCPv4
	}

	d.stateLock.RLock()
	defer d.stateLock.RUnlock()

	if d.clusterState == nil {
		return ErrHandlerNotInitialized
	}

	switch msg.Pkt4.MessageType() {
	case dhcpv4.MessageTypeDiscover:
		return d.handleDiscover(ctx, msg)
	case dhcpv4.MessageTypeRequest:
		return d.handleRequest(ctx, msg)
	case dhcpv4.MessageTypeDecline:
		return d.handleDecline(ctx, msg)
	case dhcpv4.MessageTypeRelease:
		return d.handleRelease(ctx, msg)
	case dhcpv4.MessageTypeInform:
		return d.handleInform(ctx, msg)
	}

	return ErrInvalidMessageType
}

func (d *DORAHandler) reply(ctx context.Context, ifaceIdx int, addr net.Addr, reply *dhcpv4.DHCPv4) error {
	sock, err := d.server.GetSocketFor(4, ifaceIdx)
	if err != nil {
		return err
	}

	conn := sock.Conn()

	buf := reply.ToBytes()

	_, err = conn.WriteTo(buf, addr)

	return err
}

func (d *DORAHandler) replyEth(ctx context.Context, ifaceIdx int, mac net.HardwareAddr, reply *dhcpv4.DHCPv4) error {
	buf := reply.ToBytes()

	iface, err := net.InterfaceByIndex(ifaceIdx)
	if err != nil {
		return fmt.Errorf("error fetching reply interface: %w", err)
	}

	eth := layers.Ethernet{
		SrcMAC:       iface.HardwareAddr,
		DstMAC:       mac,
		EthernetType: layers.EthernetTypeIPv4,
	}

	ipPkt := layers.IPv4{
		Version:  4,
		TTL:      64,
		SrcIP:    reply.ServerIPAddr,
		DstIP:    reply.YourIPAddr,
		Protocol: layers.IPProtocolUDP,
		Flags:    layers.IPv4DontFragment,
	}

	udpPkt := layers.UDP{
		SrcPort: dhcp4Port,
		DstPort: 68,
	}

	err = udpPkt.SetNetworkLayerForChecksum(&ipPkt)
	if err != nil {
		return fmt.Errorf("error setting network layer checksum")
	}

	packet := gopacket.NewPacket(buf, layers.LayerTypeDHCPv4, gopacket.NoCopy)
	dhcpLayer := packet.Layer(layers.LayerTypeDHCPv4)

	pktBuf := gopacket.NewSerializeBuffer()

	dhcpPkt, ok := dhcpLayer.(gopacket.SerializableLayer)
	if !ok {
		return fmt.Errorf("%w: packet is type %s", ErrPacketNotSerializable, dhcpLayer.LayerType().String())
	}

	err = gopacket.SerializeLayers(
		pktBuf,
		gopacket.SerializeOptions{
			ComputeChecksums: true,
			FixLengths:       true,
		},
		&eth,
		&ipPkt,
		&udpPkt,
		dhcpPkt,
	)
	if err != nil {
		return err
	}

	data := pktBuf.Bytes()

	fd, err := syscall.Socket(syscall.AF_PACKET, syscall.SOCK_RAW, 0)
	if err != nil {
		return fmt.Errorf("error opening raw reply socket: %w", err)
	}

	defer func() {
		cErr := syscall.Close(fd)
		if err == nil && cErr != nil {
			err = cErr
		}
	}()

	err = syscall.SetsockoptInt(fd, syscall.SOL_SOCKET, syscall.SO_REUSEADDR, 1)
	if err != nil {
		return fmt.Errorf("error setting raw socket options: %w", err)
	}

	dstMac := make([]byte, 8)
	copy(dstMac[0:6], reply.ClientHWAddr[0:6])

	ethAddr := syscall.SockaddrLinklayer{
		Protocol: 0,
		Ifindex:  ifaceIdx,
		Halen:    6,
		Addr:     [8]byte(dstMac),
	}

	err = syscall.Sendto(fd, data, 0, &ethAddr)
	if err != nil {
		return fmt.Errorf("error writing raw frame: %w", err)
	}

	return nil
}

func getServerAddr(msg Message) (net.IP, error) {
	iface, err := net.InterfaceByIndex(int(msg.IfaceIdx))
	if err != nil {
		return nil, err
	}

	addrs, err := iface.Addrs()
	if err != nil {
		return nil, err
	}

	var serverIP net.IP

	serverAddr, ok := addrs[0].(*net.IPAddr)
	if !ok {
		serverNetAddr, ok := addrs[0].(*net.IPNet)
		if !ok {
			return nil, ErrNoSuitableServerIP
		}

		serverIP = serverNetAddr.IP.To4()
	} else {
		serverIP = serverAddr.IP.To4()
	}

	return serverIP, nil
}

func (d *DORAHandler) handleDiscover(ctx context.Context, msg Message) error {
	var (
		offer *Offer
		err   error
	)

	err = d.clusterState.Database().Transaction(ctx, func(ctx context.Context, tx *sql.Tx) error {
		offer, err = d.allocator.GetOfferFromDiscover(ctx, tx, msg.Pkt4, int(msg.IfaceIdx), msg.SrcMAC)

		return err
	})
	if err != nil {
		return err
	}

	serverIP, err := getServerAddr(msg)
	if err != nil {
		return err
	}

	reply, err := dhcpv4.New(
		dhcpv4.WithReply(msg.Pkt4),
		dhcpv4.WithMessageType(dhcpv4.MessageTypeOffer),
		dhcpv4.WithServerIP(serverIP),
		dhcpv4.WithClientIP(msg.Pkt4.ClientIPAddr),
		dhcpv4.WithYourIP(offer.IP),
		dhcpv4.WithHwAddr(msg.Pkt4.ClientHWAddr),
	)
	if err != nil {
		return err
	}

	for optCode, optValue := range offer.Options {
		value := []byte(optValue)

		if marshaler, ok := optionMarshalers[getDHCPv4OptionType(optCode)]; ok {
			value, err = marshaler(optValue)
			if err != nil {
				return err
			}
		}

		reply.Options[uint8(optCode)] = value //nolint:gosec // as long as it's a V4 Option, it will fit uint8

		if optCode == uint16(dhcpv4.OptionRouter) {
			reply.GatewayIPAddr = net.IP(value)
		}
	}

	if d.discoverReplyOverride != nil {
		return d.discoverReplyOverride(ctx, int(msg.IfaceIdx), reply)
	}

	return d.replyEth(ctx, int(msg.IfaceIdx), reply.ClientHWAddr, reply)
}

func (d *DORAHandler) handleRequest(ctx context.Context, msg Message) error {
	var (
		reply *dhcpv4.DHCPv4
		lease *Lease
		err   error
	)

	requestedIPBytes, ok := msg.Pkt4.Options[uint8(dhcpv4.OptionRequestedIPAddress)]
	if !ok || (len(requestedIPBytes) != 4 && len(requestedIPBytes) != 16) {
		return ErrNoIPRequested
	}

	requestedIP := net.IP(requestedIPBytes).To4()

	err = d.clusterState.Database().Transaction(ctx, func(ctx context.Context, tx *sql.Tx) error {
		lease, err = d.allocator.ACKLease(ctx, tx, requestedIP, msg.Pkt4.ClientHWAddr)
		if err != nil {
			log.Err(err).Send()

			if errors.Is(err, sql.ErrNoRows) {
				return err
			}

			err = d.allocator.NACKLease(ctx, tx, msg.Pkt4.YourIPAddr, msg.Pkt4.ClientHWAddr)
			if err != nil {
				return err
			}

			reply, err = dhcpv4.New(
				dhcpv4.WithReply(msg.Pkt4),
				dhcpv4.WithMessageType(dhcpv4.MessageTypeNak),
			)

			return err
		} else {
			var serverIP net.IP

			serverIP, err = getServerAddr(msg)
			if err != nil {
				return err
			}

			reply, err = dhcpv4.New(
				dhcpv4.WithReply(msg.Pkt4),
				dhcpv4.WithMessageType(dhcpv4.MessageTypeAck),
				dhcpv4.WithServerIP(serverIP.To4()),
				dhcpv4.WithClientIP(msg.Pkt4.ClientIPAddr),
				dhcpv4.WithYourIP(lease.IP.To4()),
			)

			return err
		}
	})
	if err != nil {
		return err
	}

	for optCode, optValue := range lease.Options {
		value := []byte(optValue)

		if marshaler, ok := optionMarshalers[getDHCPv4OptionType(optCode)]; ok {
			value, err = marshaler(optValue)
			if err != nil {
				return err
			}
		}

		reply.Options[uint8(optCode)] = value //nolint:gosec // as long as it's a V4 Option, it will fit uint8

		if optCode == uint16(dhcpv4.OptionRouter) {
			reply.GatewayIPAddr = net.IP(value)
		}
	}

	if d.requestReplyOverride != nil {
		return d.requestReplyOverride(ctx, reply)
	}

	if reply.ClientIPAddr.To4().Equal(net.IPv4zero) {
		return d.replyEth(ctx, int(msg.IfaceIdx), msg.SrcMAC, reply)
	}

	addr := &net.UDPAddr{
		IP:   reply.ClientIPAddr,
		Port: 68,
	}

	return d.reply(ctx, int(msg.IfaceIdx), addr, reply)
}

func (d *DORAHandler) handleDecline(ctx context.Context, msg Message) error {
	// given a decline should remove the offered lease, we can actually
	// reuse the logic from allocator.Release() here, so long as it can delete
	// the lease on VLAN + MAC, if we were to release only on IP and MAC, that cannot
	// apply here as DECLINE will not have a client IP in the message
	return d.clusterState.Database().Transaction(ctx, func(ctx context.Context, tx *sql.Tx) error {
		err := d.allocator.Release(ctx, tx, int(msg.IfaceIdx), msg.Pkt4.ClientHWAddr)
		if err != nil {
			if errors.Is(err, sql.ErrNoRows) {
				return nil
			}

			return err
		}

		conflictedIPBytes, ok := msg.Pkt4.Options[uint8(dhcpv4.OptionRequestedIPAddress)]
		if !ok || (len(conflictedIPBytes) != 4 && len(conflictedIPBytes) != 16) {
			return ErrNoIPRequested
		}

		return d.allocator.MarkConflicted(ctx, tx, net.IP(conflictedIPBytes))
	})
}

func (d *DORAHandler) handleRelease(ctx context.Context, msg Message) error {
	return d.clusterState.Database().Transaction(ctx, func(ctx context.Context, tx *sql.Tx) error {
		return d.allocator.Release(ctx, tx, int(msg.IfaceIdx), msg.Pkt4.ClientHWAddr)
	})
}

func (d *DORAHandler) handleInform(ctx context.Context, msg Message) error {
	requestedIPBytes, ok := msg.Pkt4.Options[uint8(dhcpv4.OptionRequestedIPAddress)]
	if !ok || (len(requestedIPBytes) != 4 && len(requestedIPBytes) != 16) {
		return ErrNoIPRequested
	}

	requestedIP := net.IP(requestedIPBytes).To4()

	var lease *Lease

	err := d.clusterState.Database().Transaction(ctx, func(ctx context.Context, tx *sql.Tx) error {
		var err error

		lease, err = d.allocator.ACKLease(ctx, tx, requestedIP, msg.SrcMAC)

		return err
	})
	if err != nil {
		return err
	}

	serverIP, err := getServerAddr(msg)
	if err != nil {
		return err
	}

	reply, err := dhcpv4.New(
		dhcpv4.WithReply(msg.Pkt4),
		dhcpv4.WithMessageType(dhcpv4.MessageTypeAck),
		dhcpv4.WithServerIP(serverIP.To4()),
		dhcpv4.WithClientIP(msg.Pkt4.ClientIPAddr),
		dhcpv4.WithYourIP(lease.IP.To4()),
	)
	if err != nil {
		return err
	}

	for optCode, optValue := range lease.Options {
		value := []byte(optValue)

		if marshaler, ok := optionMarshalers[getDHCPv4OptionType(optCode)]; ok {
			value, err = marshaler(optValue)
			if err != nil {
				return err
			}
		}

		reply.Options[uint8(optCode)] = value //nolint:gosec // as long as it's a V4 Option, it will fit uint8

		if optCode == uint16(dhcpv4.OptionRouter) {
			reply.GatewayIPAddr = net.IP(value)
		}
	}

	if d.requestReplyOverride != nil {
		return d.requestReplyOverride(ctx, reply)
	}

	if reply.ClientIPAddr.To4().Equal(net.IPv4zero) {
		return d.replyEth(ctx, int(msg.IfaceIdx), msg.SrcMAC, reply)
	}

	addr := &net.UDPAddr{
		IP:   reply.ClientIPAddr,
		Port: 68,
	}

	return d.reply(ctx, int(msg.IfaceIdx), addr, reply)
}
