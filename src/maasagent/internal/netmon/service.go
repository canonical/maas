package netmon

/*
	Copyright 2023 Canonical Ltd.  This software is licensed under the
	GNU Affero General Public License version 3 (see the file LICENSE).
*/

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"net"
	"net/netip"
	"time"

	pcap "github.com/packetcap/go-pcap"
	"github.com/rs/zerolog/log"

	"launchpad.net/maas/maas/src/maasagent/internal/ethernet"
)

const (
	snapLen            int32         = 64
	timeout            time.Duration = -1
	seenAgainThreshold time.Duration = 600 * time.Second
)

var (
	// ErrEmptyPacket is returned when a packet of 0 bytes has been received
	ErrEmptyPacket = errors.New("received an empty packet")
	// ErrPacketCaptureClosed is returned when the packet capture channel
	// has been closed unexpectedly
	ErrPacketCaptureClosed = errors.New("packet capture channel closed")
)

// Binding represents the binding between an IP address and MAC address
type Binding struct {
	// VID is the associated VLAN ID, if one exists
	VID *uint16
	// Time is the time the packet creating / updating the binding
	// was observed
	Time time.Time
	// IP is the IP a binding is tracking
	IP netip.Addr
	// MAC is the MAC address the IP is currently bound to
	MAC net.HardwareAddr
}

// Result is the result of observed ARP packets
type Result struct {
	// VID is the VLAN ID if one exists
	VID *uint16 `json:"vid"`
	// IP is the presentation format of an observed IP
	IP string `json:"ip"`
	// MAC is the presentation format of an observed MAC
	MAC string `json:"mac"`
	// Previous MAC is the presentation format of a previous MAC if
	// an EventMoved was observed
	PreviousMAC string `json:"previous_mac,omitempty"`
	// Time is the time the packet creating the Result was observed
	Time int64 `json:"time"`
	// Event is the type of event the Result is
	Event Event `json:"event"`
}

// Service is responsible for starting packet capture and
// converting observed ARP packets into discovered Results
type Service struct {
	bindings map[string]Binding
	iface    string
}

// NewService returns a pointer to a Service. It
// takes the desired interface to observe's name as an argument
func NewService(iface string) *Service {
	return &Service{
		iface:    iface,
		bindings: make(map[string]Binding),
	}
}

func (s *Service) updateBindings(pkt *ethernet.ARPPacket, vid *uint16, timestamp time.Time) []Result {
	var res []Result

	if timestamp.IsZero() {
		timestamp = time.Now()
	}

	var vidLabel int
	if vid != nil {
		vidLabel = int(*vid)
	}

	discoveredBindings := []Binding{
		{
			IP:   pkt.SendIPAddr,
			MAC:  pkt.SendHwAddr,
			VID:  vid,
			Time: timestamp,
		},
	}

	if pkt.OpCode == ethernet.OpReply {
		discoveredBindings = append(discoveredBindings, Binding{
			IP:   pkt.TgtIPAddr,
			MAC:  pkt.TgtHwAddr,
			VID:  vid,
			Time: timestamp,
		})
	}

	for _, discoveredBinding := range discoveredBindings {
		key := fmt.Sprintf("%d_%s", vidLabel, discoveredBinding.IP.String())

		binding, ok := s.bindings[key]
		if !ok {
			s.bindings[key] = discoveredBinding
			res = append(res, Result{
				IP:    discoveredBinding.IP.String(),
				MAC:   discoveredBinding.MAC.String(),
				VID:   discoveredBinding.VID,
				Time:  discoveredBinding.Time.Unix(),
				Event: EventNew,
			})

			continue
		}

		if !bytes.Equal(binding.MAC, discoveredBinding.MAC) {
			s.bindings[key] = discoveredBinding
			res = append(res, Result{
				IP:          discoveredBinding.IP.String(),
				PreviousMAC: binding.MAC.String(),
				MAC:         discoveredBinding.MAC.String(),
				VID:         discoveredBinding.VID,
				Time:        discoveredBinding.Time.Unix(),
				Event:       EventMoved,
			})
		} else if discoveredBinding.Time.Sub(binding.Time) >= seenAgainThreshold {
			s.bindings[key] = discoveredBinding
			res = append(res, Result{
				IP:    discoveredBinding.IP.String(),
				MAC:   discoveredBinding.MAC.String(),
				VID:   discoveredBinding.VID,
				Time:  discoveredBinding.Time.Unix(),
				Event: EventRefreshed,
			})
		}
	}

	return res
}

func isValidARPPacket(pkt *ethernet.ARPPacket) bool {
	if pkt.HardwareType != ethernet.HardwareTypeEthernet && pkt.HardwareType != ethernet.HardwareTypeExpEth {
		return false
	}

	if pkt.ProtocolType != ethernet.ProtocolTypeIPv4 && pkt.ProtocolType != ethernet.ProtocolTypeARP {
		return false
	}

	if pkt.HardwareAddrLen != 6 {
		return false
	}

	if pkt.ProtocolAddrLen != 4 {
		return false
	}

	return true
}

func (s *Service) handlePacket(pkt pcap.Packet) ([]Result, error) {
	if pkt.Error != nil {
		return nil, pkt.Error
	}

	if len(pkt.B) == 0 {
		return nil, ErrEmptyPacket
	}

	eth := &ethernet.EthernetFrame{}

	err := eth.UnmarshalBinary(pkt.B)
	if err != nil {
		return nil, err
	}

	if eth.EthernetType != ethernet.EthernetTypeVLAN && eth.EthernetType != ethernet.EthernetTypeARP {
		log.Debug().Msg("skipping non-ARP packet")
		return nil, nil
	}

	var vid *uint16

	if eth.EthernetType == ethernet.EthernetTypeVLAN {
		var vlan *ethernet.VLAN

		vlan, err = eth.ExtractVLAN()
		if err != nil {
			return nil, err
		}

		vid = &vlan.ID
	}

	arpPkt, err := eth.ExtractARPPacket()
	if err != nil {
		return nil, err
	}

	if !isValidARPPacket(arpPkt) {
		log.Debug().Msg("skipping non-ethernet+IPv4 ARP packet")
		return nil, nil
	}

	return s.updateBindings(arpPkt, vid, pkt.Info.Timestamp), nil
}

func isRecoverableError(err error) bool {
	return errors.Is(
		err,
		ethernet.ErrMalformedARPPacket) || errors.Is(err, ethernet.ErrMalformedVLAN) || errors.Is(err, ethernet.ErrMalformedFrame)
}

// Start will start packet capture and send results to a channel
func (s *Service) Start(ctx context.Context, resultC chan<- Result) error {
	defer close(resultC)

	hndlr, err := pcap.OpenLive(s.iface, snapLen, false, timeout, true)
	if err != nil {
		return err
	}

	defer hndlr.Close()

	err = hndlr.SetBPFFilter("ether proto arp")
	if err != nil {
		return err
	}

	pkts := hndlr.Listen()

	for {
		select {
		case <-ctx.Done():
			return nil
		case pkt, ok := <-pkts:
			if !ok {
				log.Debug().Msg("packet capture has closed")
				return ErrPacketCaptureClosed
			}

			res, err := s.handlePacket(pkt)
			if err != nil {
				if isRecoverableError(err) {
					log.Error().Err(err).Send()
					continue
				}

				return err
			}

			for _, r := range res {
				resultC <- r
			}
		}
	}
}
