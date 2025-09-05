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
	"bytes"
	"context"
	"database/sql"
	"encoding/binary"
	"errors"
	"net"
	"strconv"

	"github.com/canonical/microcluster/v2/state"
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
)

var (
	optionMarshalers = map[uint16]func(string) ([]byte, error){
		uint16(dhcpv4.OptionIPAddressLeaseTime): func(s string) ([]byte, error) {
			n, err := strconv.Atoi(s)
			if err != nil {
				return nil, err
			}

			buf := make([]byte, 4)
			binary.BigEndian.PutUint32(buf, uint32(n))
			return buf, nil
		},
		uint16(dhcpv4.OptionRouter):           ipOptionMarshal,
		uint16(dhcpv4.OptionSubnetMask):       ipOptionMarshal,
		uint16(dhcpv4.OptionTimeServer):       ipOptionMarshal,
		uint16(dhcpv4.OptionNameServer):       ipOptionMarshal,
		uint16(dhcpv4.OptionDomainNameServer): ipOptionMarshal,
	}
)

func ipOptionMarshal(s string) ([]byte, error) {
	ip := net.ParseIP(s)
	if ip == nil {
		return nil, ErrNotAnIP
	}

	if ip4 := ip.To4(); ip4 != nil {
		return ip4, nil
	}

	return ip, nil
}

type DHCPv4Handler struct {
	allocator    Allocator4
	clusterState state.State
}

func NewDHCPv4Handler(a Allocator4, clusterState state.State) *DHCPv4Handler {
	return &DHCPv4Handler{
		allocator:    a,
		clusterState: clusterState,
	}
}

type dhcpV4Message struct {
	Message
	Packet *dhcpv4.DHCPv4
}

func (h *DHCPv4Handler) ServeDHCP(ctx context.Context, msg Message) (Response, error) {
	p, err := dhcpv4.FromBytes(msg.Payload)
	if err != nil {
		return Response{}, ErrNotDHCPv4
	}

	dhcp := dhcpV4Message{Message: msg, Packet: p}

	switch p.MessageType() {
	case dhcpv4.MessageTypeDiscover:
		return h.handleDiscover(ctx, dhcp)
	case dhcpv4.MessageTypeRequest:
		return h.handleRequest(ctx, dhcp)
	case dhcpv4.MessageTypeDecline:
		h.handleDecline(ctx, dhcp)
	case dhcpv4.MessageTypeRelease:
		h.handleRelease(ctx, dhcp)
	case dhcpv4.MessageTypeInform:
		return h.handleInform(ctx, dhcp)
	}

	return Response{}, ErrInvalidMessageType
}

func getServerAddr(msg dhcpV4Message) (net.IP, error) {
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

func (h *DHCPv4Handler) handleDiscover(ctx context.Context, msg dhcpV4Message) (Response, error) {
	var (
		offer *Offer
		err   error
	)

	err = h.clusterState.Database().Transaction(ctx, func(ctx context.Context, tx *sql.Tx) error {
		offer, err = h.allocator.GetOfferFromDiscover(ctx, tx, msg.Packet, int(msg.IfaceIdx), msg.SrcMAC)

		return err
	})
	if err != nil {
		return Response{}, err
	}

	serverIP, err := getServerAddr(msg)
	if err != nil {
		return Response{}, err
	}

	reply, err := dhcpv4.New(
		dhcpv4.WithReply(msg.Packet),
		dhcpv4.WithMessageType(dhcpv4.MessageTypeOffer),
		dhcpv4.WithServerIP(serverIP),
		dhcpv4.WithClientIP(msg.Packet.ClientIPAddr),
		dhcpv4.WithYourIP(offer.IP),
	)
	if err != nil {
		return Response{}, err
	}

	for optCode, optValue := range offer.Options {
		value := []byte(optValue)

		if marshaler, ok := optionMarshalers[optCode]; ok {
			value, err = marshaler(optValue)
			if err != nil {
				return Response{}, err
			}
		}

		reply.Options[uint8(optCode)] = value

		if optCode == uint16(dhcpv4.OptionRouter) {
			reply.GatewayIPAddr = net.IP(value)
		}
	}

	return Response{
		SrcAddress: reply.ServerIPAddr,
		DstAddress: reply.YourIPAddr,
		DstMAC:     msg.SrcMAC,
		Payload:    reply.ToBytes(),
		Mode:       SendL2,
		IfaceIdx:   int(msg.IfaceIdx),
	}, nil
}

func (h *DHCPv4Handler) handleRequest(ctx context.Context, msg dhcpV4Message) (Response, error) {
	var (
		reply *dhcpv4.DHCPv4
		lease *Lease
		err   error
	)

	requestedIPBytes, ok := msg.Packet.Options[uint8(dhcpv4.OptionRequestedIPAddress)]
	if !ok || (len(requestedIPBytes) != 4 && len(requestedIPBytes) != 16) {
		return Response{}, ErrNoIPRequested
	}

	requestedIP := net.IP(requestedIPBytes).To4()

	err = h.clusterState.Database().Transaction(ctx, func(ctx context.Context, tx *sql.Tx) error {
		lease, err = h.allocator.ACKLease(ctx, tx, requestedIP, msg.Packet.ClientHWAddr)
		if err != nil {
			log.Err(err).Send()

			if errors.Is(err, sql.ErrNoRows) {
				return err
			}

			err = h.allocator.NACKLease(ctx, tx, msg.Packet.YourIPAddr, msg.Packet.ClientHWAddr)
			if err != nil {
				return err
			}

			reply, err = dhcpv4.New(
				dhcpv4.WithReply(msg.Packet),
				dhcpv4.WithMessageType(dhcpv4.MessageTypeNak),
			)

			return err
		} else {
			serverIP, err := getServerAddr(msg)
			if err != nil {
				return err
			}

			reply, err = dhcpv4.New(
				dhcpv4.WithReply(msg.Packet),
				dhcpv4.WithMessageType(dhcpv4.MessageTypeAck),
				dhcpv4.WithServerIP(serverIP.To4()),
				dhcpv4.WithClientIP(msg.Packet.ClientIPAddr),
				dhcpv4.WithYourIP(lease.IP.To4()),
			)

			return err
		}
	})
	if err != nil {
		return Response{}, err
	}

	for optCode, optValue := range lease.Options {
		value := []byte(optValue)

		if marshaler, ok := optionMarshalers[optCode]; ok {
			value, err = marshaler(optValue)
			if err != nil {
				return Response{}, err
			}
		}

		reply.Options[uint8(optCode)] = value

		if optCode == uint16(dhcpv4.OptionRouter) {
			reply.GatewayIPAddr = net.IP(value)
		}
	}

	response := Response{
		SrcAddress: reply.ServerIPAddr,
		DstAddress: reply.YourIPAddr,
		DstMAC:     msg.SrcMAC,
		Payload:    reply.ToBytes(),
		IfaceIdx:   int(msg.IfaceIdx),
	}

	if bytes.Equal(reply.ClientIPAddr.To4(), net.IPv4zero) {
		response.Mode = SendL2
		return response, nil
	}

	response.DstAddress = reply.ClientIPAddr

	return response, nil
}

func (h *DHCPv4Handler) handleDecline(ctx context.Context, msg dhcpV4Message) error {
	// given a decline should remove the offered lease, we can actually
	// reuse the logic from allocator.Release() here, so long as it can delete
	// the lease on VLAN + MAC, if we were to release only on IP and MAC, that cannot
	// apply here as DECLINE will not have a client IP in the message
	return h.clusterState.Database().Transaction(ctx, func(ctx context.Context, tx *sql.Tx) error {
		err := h.allocator.Release(ctx, tx, int(msg.IfaceIdx), msg.Packet.ClientHWAddr)
		if err != nil {
			if errors.Is(err, sql.ErrNoRows) {
				return nil
			}

			return err
		}

		conflictedIPBytes, ok := msg.Packet.Options[uint8(dhcpv4.OptionRequestedIPAddress)]
		if !ok || (len(conflictedIPBytes) != 4 && len(conflictedIPBytes) != 16) {
			return ErrNoIPRequested
		}

		return h.allocator.MarkConflicted(ctx, tx, net.IP(conflictedIPBytes))
	})
}

func (h *DHCPv4Handler) handleRelease(ctx context.Context, msg dhcpV4Message) error {
	return h.clusterState.Database().Transaction(ctx, func(ctx context.Context, tx *sql.Tx) error {
		return h.allocator.Release(ctx, tx, int(msg.IfaceIdx), msg.Packet.ClientHWAddr)
	})
}

func (h *DHCPv4Handler) handleInform(ctx context.Context, msg dhcpV4Message) (Response, error) {
	requestedIPBytes, ok := msg.Packet.Options[uint8(dhcpv4.OptionRequestedIPAddress)]
	if !ok || (len(requestedIPBytes) != 4 && len(requestedIPBytes) != 16) {
		return Response{}, ErrNoIPRequested
	}

	requestedIP := net.IP(requestedIPBytes).To4()

	var lease *Lease

	err := h.clusterState.Database().Transaction(ctx, func(ctx context.Context, tx *sql.Tx) error {
		var err error

		lease, err = h.allocator.ACKLease(ctx, tx, requestedIP, msg.SrcMAC)

		return err
	})
	if err != nil {
		return Response{}, err
	}

	serverIP, err := getServerAddr(msg)
	if err != nil {
		return Response{}, err
	}

	reply, err := dhcpv4.New(
		dhcpv4.WithReply(msg.Packet),
		dhcpv4.WithMessageType(dhcpv4.MessageTypeAck),
		dhcpv4.WithServerIP(serverIP.To4()),
		dhcpv4.WithClientIP(msg.Packet.ClientIPAddr),
		dhcpv4.WithYourIP(lease.IP.To4()),
	)
	if err != nil {
		return Response{}, err
	}

	for optCode, optValue := range lease.Options {
		value := []byte(optValue)

		if marshaler, ok := optionMarshalers[optCode]; ok {
			value, err = marshaler(optValue)
			if err != nil {
				return Response{}, err
			}
		}

		reply.Options[uint8(optCode)] = value

		if optCode == uint16(dhcpv4.OptionRouter) {
			reply.GatewayIPAddr = net.IP(value)
		}
	}

	response := Response{
		SrcAddress: reply.ServerIPAddr,
		DstAddress: reply.YourIPAddr,
		DstMAC:     msg.SrcMAC,
		Payload:    reply.ToBytes(),
		IfaceIdx:   int(msg.IfaceIdx),
	}

	if bytes.Equal(reply.ClientIPAddr.To4(), net.IPv4zero) {
		response.Mode = SendL2
		return response, nil
	}

	response.DstAddress = reply.ClientIPAddr

	return response, nil
}
