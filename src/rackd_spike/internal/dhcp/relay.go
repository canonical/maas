package dhcp

import (
	"context"
	"net"
	"os"
	"sync"

	"github.com/insomniacslk/dhcp/dhcpv4"
	client4 "github.com/insomniacslk/dhcp/dhcpv4/nclient4"
	"github.com/insomniacslk/dhcp/dhcpv4/server4"
	"github.com/insomniacslk/dhcp/dhcpv6"
	"github.com/insomniacslk/dhcp/dhcpv6/server6"
	"github.com/rs/zerolog"

	"rackd/internal/config"
	"rackd/internal/service"
)

const (
	pktSize = 4096
)

type RelayHandler struct {
	sync.Mutex
	upstream     *net.UDPConn
	upstreamAddr *net.UDPAddr
	localAddr    *net.UDPAddr
	iface        net.HardwareAddr
}

func dhcpv4NextMsgMatcher(msg *dhcpv4.DHCPv4) client4.Matcher {
	switch msg.MessageType() {
	case dhcpv4.MessageTypeDiscover:
		return client4.IsMessageType(dhcpv4.MessageTypeOffer, dhcpv4.MessageTypeDecline)
	case dhcpv4.MessageTypeRequest:
		return client4.IsMessageType(dhcpv4.MessageTypeAck, dhcpv4.MessageTypeNak)
	}
	return nil
}

func (r *RelayHandler) RelayMsg4(ctx context.Context, conn net.PacketConn, msg *dhcpv4.DHCPv4, peer net.Addr) (err error) {
	if msg.MessageType() == dhcpv4.MessageTypeRelease {
		buf := msg.ToBytes()
		_, err = r.upstream.Write(buf)
		return err
	}
	client, err := client4.NewWithConn(r.upstream, r.iface)
	if err != nil {
		return err
	}
	resp, err := client.SendAndRead(ctx, r.upstreamAddr, msg, dhcpv4NextMsgMatcher(msg))
	if err != nil {
		return err
	}
	buf := resp.ToBytes()
	_, err = conn.WriteTo(buf, peer)
	if err != nil {
		return err
	}
	return nil
}

func (r *RelayHandler) RelayMsg6(ctx context.Context, conn net.PacketConn, m dhcpv6.DHCPv6, peer *net.UDPAddr) error {
	relayMsg, err := dhcpv6.EncapsulateRelay(m, dhcpv6.MessageTypeRelayForward, r.upstreamAddr.IP, peer.IP)
	relayMsgBuf := relayMsg.ToBytes()
	_, err = r.upstream.Write(relayMsgBuf)
	if err != nil {
		return err
	}
	respBuf := make([]byte, len(relayMsgBuf))
	n, err := r.upstream.Read(respBuf)
	if err != nil {
		return err
	}
	resp, err := dhcpv6.MessageFromBytes(respBuf[:n])
	if err != nil {
		return err
	}
	relayRsp, err := dhcpv6.EncapsulateRelay(resp, dhcpv6.MessageTypeRelayReply, r.upstreamAddr.IP, peer.IP)
	if err != nil {
		return err
	}
	buf := relayRsp.ToBytes()
	_, err = conn.WriteTo(buf, peer)
	if err != nil {
		return err
	}
	return nil
}

func (r *RelayHandler) HandleV4(ctx context.Context, conn net.PacketConn, m *dhcpv4.DHCPv4, peer *net.UDPAddr) error {
	dhcpv4.WithRelay(r.localAddr.IP)(m)
	dhcpv4.WithOption(dhcpv4.OptRelayAgentInfo(
		dhcpv4.OptGeneric(dhcpv4.AgentRemoteIDSubOption, []byte(config.Config.ClusterUUID)),
	))(m)
	return r.RelayMsg4(ctx, conn, m, peer)
}

func (r *RelayHandler) HandleV6(ctx context.Context, conn net.PacketConn, m dhcpv6.DHCPv6, peer *net.UDPAddr) error {
	return r.RelayMsg6(ctx, conn, m, peer)
}

type Relay struct {
	server  *net.UDPConn
	handler *RelayHandler
	bufPool sync.Pool
	v6      bool
}

func NewRelay(ifname, bindAddr, upstream string, packetBufferSize int) (r *Relay, err error) {
	bindIP := net.ParseIP(bindAddr)
	destIP := net.ParseIP(upstream)
	iface, err := net.InterfaceByName(ifname)
	if err != nil {
		return nil, err
	}

	r = &Relay{
		handler: &RelayHandler{
			iface: iface.HardwareAddr,
		},
		bufPool: sync.Pool{
			New: func() interface{} {
				buf := make([]byte, packetBufferSize)
				return &buf
			},
		},
	}

	if bindIP.To4() != nil {
		r.handler.localAddr = &net.UDPAddr{
			IP:   bindIP,
			Port: dhcpv4.ServerPort,
		}
		caddr := &net.UDPAddr{
			IP:   bindIP,
			Port: dhcpv4.ClientPort,
		}
		r.handler.upstreamAddr = &net.UDPAddr{
			IP:   destIP,
			Port: dhcpv4.ServerPort,
		}
		r.handler.upstream, err = net.DialUDP("udp", caddr, r.handler.upstreamAddr)
		if err != nil {
			return nil, err
		}
		r.server, err = server4.NewIPv4UDPConn(ifname, r.handler.localAddr)
		if err != nil {
			return nil, err
		}
	} else {
		r.handler.localAddr = &net.UDPAddr{
			IP:   bindIP,
			Port: dhcpv6.DefaultServerPort,
		}
		caddr := &net.UDPAddr{
			IP:   bindIP,
			Port: dhcpv6.DefaultClientPort,
		}
		r.handler.upstreamAddr = &net.UDPAddr{
			IP:   destIP,
			Port: dhcpv6.DefaultServerPort,
		}
		r.v6 = true
		r.handler.upstream, err = net.DialUDP("udp6", caddr, r.handler.upstreamAddr)
		if err != nil {
			return nil, err
		}
		r.server, err = server6.NewIPv6UDPConn(ifname, r.handler.localAddr)
		if err != nil {
			return nil, err
		}
	}
	return r, nil
}

func (r *Relay) handleRawPacket(ctx context.Context, conn net.PacketConn, buffer []byte, peer *net.UDPAddr) error {
	if r.v6 {
		msg, err := dhcpv6.FromBytes(buffer)
		if err != nil {
			return err
		}
		return r.handler.HandleV6(ctx, conn, msg, peer)
	}
	msg, err := dhcpv4.FromBytes(buffer)
	if err != nil {
		return err
	}
	return r.handler.HandleV4(ctx, conn, msg, peer)
}

func (r *Relay) Start(ctx context.Context) error {
	logger := zerolog.Ctx(ctx)
	go func() {
		defer r.Stop(ctx)
		for {
			select {
			case <-ctx.Done():
				return
			default:
				buffer := r.bufPool.Get().(*[]byte)
				buf := *buffer
				n, peer, err := r.server.ReadFromUDP(buf)
				if err != nil {
					r.bufPool.Put(buffer)
					logger.Err(err)
					continue
				}
				go func() {
					defer func() {
						r.bufPool.Put(buffer)
						if e := recover(); e != nil {
							if err, ok := e.(error); ok {
								logger.Err(err).Msgf("remote conn: %s", peer.String())
							} else {
								logger.Info().Msgf("recover returned: %v", e)
							}
						}
					}()
					err := r.handleRawPacket(ctx, r.server, buf[:n], peer)
					if err != nil {
						logger.Err(err).Msgf("remote conn: %s", peer.String())
					}
				}()
			}
		}
	}()
	return nil
}

func (r *Relay) Stop(ctx context.Context) error {
	err := r.server.Close()
	if err != nil {
		return err
	}
	return r.handler.upstream.Close()
}

func (r *Relay) Restart(ctx context.Context) error {
	err := r.Stop(ctx)
	if err != nil {
		return err
	}
	return r.Start(ctx)
}

type RelaySvc struct {
	sync.Mutex
	relays map[string]*Relay
}

func NewRelaySvc() *RelaySvc {
	return &RelaySvc{
		relays: make(map[string]*Relay),
	}
}

func (r *RelaySvc) Name() string {
	return "dhcp_relay"
}

func (r *RelaySvc) Type() int {
	return service.SvcDHCPRelay
}

func (r *RelaySvc) PID() int {
	return os.Getpid()
}

func (r *RelaySvc) Start(ctx context.Context) (err error) {
	for _, relay := range r.relays {
		err = relay.Start(ctx)
		if err != nil {
			return err
		}
	}
	return nil
}

func (r *RelaySvc) Stop(ctx context.Context) (err error) {
	for _, relay := range r.relays {
		err = relay.Stop(ctx)
		if err != nil {
			return err
		}
	}
	return nil
}

func (r *RelaySvc) Restart(ctx context.Context) error {
	err := r.Stop(ctx)
	if err != nil {
		return err
	}
	return r.Start(ctx)
}

func (r *RelaySvc) Status(ctx context.Context) (err error) {
	return nil
}

func (r *RelaySvc) Configure(ctx context.Context, data ConfigData, regionIP string) error {
	r.Lock()
	defer r.Unlock()
	for _, ifname := range data.Interfaces {
		iface, err := net.InterfaceByName(ifname)
		if err != nil {
			return err
		}
		if _, ok := r.relays[ifname]; !ok {
			addrs, err := iface.Addrs()
			if err != nil {
				return err
			}
			relay, err := NewRelay(ifname, addrs[0].String(), regionIP, pktSize)
			if err != nil {
				return err
			}
			r.relays[ifname] = relay
			err = r.Start(ctx)
			if err != nil {
				return err
			}
		}
	}
	return nil
}
