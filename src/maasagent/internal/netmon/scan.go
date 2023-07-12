package netmon

import (
	"context"
	"errors"
	"net"
	"net/netip"
	"time"

	"github.com/google/gopacket"
	"github.com/google/gopacket/layers"

	pcap "github.com/packetcap/go-pcap"
	"golang.org/x/net/bpf"
	"golang.org/x/net/icmp"
	"golang.org/x/net/ipv4"
	"golang.org/x/net/ipv6"
)

const (
	// Redefine constant to avoid import of gopacket/pcap which requires CGO
	// https://github.com/google/gopacket/blob/v1.1.19/pcap/pcap.go#L124
	BlockForever     time.Duration = -time.Millisecond * 10
	OperationTimeout time.Duration = 3 * time.Second
	SnapLen          int32         = 64
)

var (
	// Raw instruction of BPF filter generated with:
	// tcpdump -dd "icmp[icmptype]=icmp-echoreply or icmp6[icmp6type]=icmp6-echoreply"
	icmpEchoReplyFilter = []bpf.RawInstruction{
		{Op: 0x28, Jt: 0, Jf: 0, K: 0x0000000c},
		{Op: 0x15, Jt: 0, Jf: 7, K: 0x00000800},
		{Op: 0x30, Jt: 0, Jf: 0, K: 0x00000017},
		{Op: 0x15, Jt: 0, Jf: 11, K: 0x00000001},
		{Op: 0x28, Jt: 0, Jf: 0, K: 0x00000014},
		{Op: 0x45, Jt: 9, Jf: 0, K: 0x00001fff},
		{Op: 0xb1, Jt: 0, Jf: 0, K: 0x0000000e},
		{Op: 0x50, Jt: 0, Jf: 0, K: 0x0000000e},
		{Op: 0x15, Jt: 5, Jf: 6, K: 0x00000000},
		{Op: 0x15, Jt: 0, Jf: 5, K: 0x000086dd},
		{Op: 0x30, Jt: 0, Jf: 0, K: 0x00000014},
		{Op: 0x15, Jt: 0, Jf: 3, K: 0x0000003a},
		{Op: 0x30, Jt: 0, Jf: 0, K: 0x00000036},
		{Op: 0x15, Jt: 0, Jf: 1, K: 0x00000081},
		{Op: 0x6, Jt: 0, Jf: 0, K: 0x00040000},
		{Op: 0x6, Jt: 0, Jf: 0, K: 0x00000000},
	}
)

// Scan sends ICMP Echo requests to provided IP addresses.
func Scan(ctx context.Context, ips ...netip.Addr) ([]IPHwAddressPair, error) {
	queue := make(map[netip.Addr]struct{})
	conns := make(map[int]*icmp.PacketConn)

	cctx, ccancel := context.WithCancel(ctx)
	defer ccancel()

	result, err := capture(cctx)
	if err != nil {
		return nil, err
	}

	for i, ip := range ips {
		if !ip.IsValid() {
			continue
		}

		c, ok := conns[ip.BitLen()]
		if !ok {
			c, err = getConn(ip)
			if err != nil {
				return nil, err
			}

			defer func() {
				err := c.Close()
				if err != nil {
					panic(err)
				}
			}()

			conns[ip.BitLen()] = c
		}

		_, err := c.WriteTo(icmpMessage(ip, i), &net.IPAddr{IP: ip.AsSlice()})
		if err != nil {
			return nil, err
		}

		queue[ip] = struct{}{}
	}

	ch := make(chan struct{})
	timer := time.AfterFunc(OperationTimeout, func() {
		close(ch)
	})

	defer timer.Stop()

	var pairs []IPHwAddressPair

	for {
		select {
		case <-ctx.Done():
			return pairs, nil
		case pair := <-result:
			if _, ok := queue[pair.IP]; ok {
				pairs = append(pairs, pair)
			}

			delete(queue, pair.IP)

			if len(queue) == 0 {
				ccancel()
				return pairs, nil
			}
		case <-ch:
			ccancel()
			return pairs, nil
		}
	}
}

func getConn(ip netip.Addr) (*icmp.PacketConn, error) {
	switch ip.BitLen() {
	case 0, 32:
		return icmp.ListenPacket("ip4:icmp", "0.0.0.0")
	case 128:
		return icmp.ListenPacket("ip6:ipv6-icmp", "::")
	default:
		return nil, errors.New("unsupported size")
	}
}

func icmpMessage(ip netip.Addr, id int) []byte {
	var icmpType icmp.Type

	if ip.Is4() {
		icmpType = ipv4.ICMPTypeEcho
	}

	if ip.Is6() {
		icmpType = ipv6.ICMPTypeEchoRequest
	}

	msg := icmp.Message{
		Type: icmpType,
		Body: &icmp.Echo{ID: id},
	}

	b, err := msg.Marshal(nil)
	if err != nil {
		panic(err)
	}

	return b
}

func capture(ctx context.Context) (chan IPHwAddressPair, error) {
	h, err := pcap.OpenLive("", SnapLen, false, BlockForever, true)
	if err != nil {
		return nil, err
	}

	err = h.SetRawBPFFilter(icmpEchoReplyFilter)
	if err != nil {
		h.Close()
		return nil, err
	}

	packetSource := gopacket.NewPacketSource(h, layers.LinkTypeEthernet)
	packetSource.Lazy = true
	packetSource.NoCopy = true

	out := make(chan IPHwAddressPair)

	go func() {
		for {
			select {
			case <-ctx.Done():
				h.Close()
				return
			case packet := <-packetSource.Packets():
				out <- getIPHwAddressPair(packet)
			}
		}
	}()

	return out, nil
}

type IPHwAddressPair struct {
	IP        netip.Addr
	HwAddress net.HardwareAddr
}

func getIPHwAddressPair(p gopacket.Packet) IPHwAddressPair {
	var layer gopacket.Layer

	pair := IPHwAddressPair{}

	layer = p.Layer(layers.LayerTypeEthernet)
	if layer != nil {
		//nolint:errcheck // safe to have this assert
		p := layer.(*layers.Ethernet)
		pair.HwAddress = p.SrcMAC
	}

	layer = p.Layer(layers.LayerTypeIPv4)
	if layer != nil {
		//nolint:errcheck // safe to have this assert
		p := layer.(*layers.IPv4)
		ip, _ := netip.AddrFromSlice(p.SrcIP)
		pair.IP = ip

		return pair
	}

	layer = p.Layer(layers.LayerTypeIPv6)
	if layer != nil {
		//nolint:errcheck // safe to have this assert
		p := layer.(*layers.IPv6)
		ip, _ := netip.AddrFromSlice(p.SrcIP)
		pair.IP = ip

		return pair
	}

	return pair
}
