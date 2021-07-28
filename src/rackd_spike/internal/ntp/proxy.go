package ntp

import (
	"bytes"
	"context"
	"encoding/binary"
	"errors"
	"net"
	"os"
	"rackd/internal/service"
	"sync"
	"syscall"
	"time"

	"github.com/rs/zerolog"
)

const (
	packetBufferSize = 512

	ClientSettings = 0x1B // 00 (leap year indicator, no warning) 011 (version 3) 011 (client mode)
	NTPEpochOffset = 2208988800
)

var (
	ErrNoUpstreamNTPServers = errors.New("error no NTP server configured")
)

type NTPService interface {
	service.Service
	Configure(context.Context, []string, []string) error
}

type Packet struct {
	Settings        uint8
	Stratum         uint8
	Poll            int8
	Precision       int8
	RootDelay       uint32
	RootDispersion  uint32
	ReferenceID     uint32
	RefTimeSec      uint32
	RefTimeFrac     uint32
	OrigTimeSecFrac uint32
	RxTimeSec       uint32
	RxTimeFrac      uint32
	TxTimeSec       uint32
	TxTimeFrac      uint32
}

type Proxy struct {
	sync.Mutex
	bindAddr     *net.UDPAddr
	upstreams    []*net.UDPAddr
	upstreamBind *net.UDPAddr
	bufPool      sync.Pool
	tick         *time.Ticker
	refreshRate  int
	listener     *net.UDPConn
	upstreamConn *net.UDPConn
}

func NewProxy(bindAddr string, refreshRate int) (*Proxy, error) {
	bAddr, err := net.ResolveUDPAddr("udp", net.JoinHostPort(bindAddr, "123"))
	if err != nil {
		return nil, err
	}
	lAddr, err := net.ResolveUDPAddr("udp", net.JoinHostPort(bindAddr, "0"))
	if err != nil {
		return nil, err
	}
	return &Proxy{
		bindAddr:     bAddr,
		upstreamBind: lAddr,
		refreshRate:  refreshRate,
		bufPool: sync.Pool{
			New: func() interface{} {
				buf := make([]byte, packetBufferSize)
				return &buf
			},
		},
	}, nil
}

func (p *Proxy) Name() string {
	return "ntp"
}

func (p *Proxy) Type() int {
	return service.SvcNTP
}

func (p *Proxy) PID() int {
	return os.Getpid()
}

func setLocalTime(pkt *Packet) error {
	return syscall.Settimeofday(&syscall.Timeval{
		Sec:  int64(float64(pkt.TxTimeSec) - NTPEpochOffset),
		Usec: (int64(pkt.TxTimeFrac) * 1e9) >> 32,
	})
}

func (p *Proxy) UpdateLocalTime(ctx context.Context) {
	logger := zerolog.Ctx(ctx)
	pkt := &Packet{
		Settings: ClientSettings,
	}
	err := binary.Write(p.upstreamConn, binary.BigEndian, pkt)
	if err != nil {
		logger.Err(err).Msg("error while requesting update local time")
		return
	}
	err = binary.Read(p.upstreamConn, binary.BigEndian, pkt)
	if err != nil {
		logger.Err(err).Msg("error while reading update local time")
		return
	}
	err = setLocalTime(pkt)
	if err != nil {
		logger.Err(err).Msg("error while settings update local time")
	}
}

func (p *Proxy) handlePkt(ctx context.Context, peer *net.UDPAddr, buf []byte) error {
	byteBuf := bytes.NewBuffer(buf)
	var pkt Packet
	err := binary.Read(byteBuf, binary.BigEndian, &pkt)
	if err != nil {
		return err
	}
	byteBuf.Reset()
	err = binary.Write(byteBuf, binary.BigEndian, pkt)
	if err != nil {
		return err
	}
	var currSrvrIdx, attempts int
	err = func() error {
		p.Lock()
		defer p.Unlock()
		recvBuffer := p.bufPool.Get().(*[]byte)
		defer p.bufPool.Put(recvBuffer)
		recvBuf := *recvBuffer
		for {
			attempts++
			srvr, err := p.getNextAvailableServer(&currSrvrIdx)
			if err != nil {
				if attempts == len(p.upstreams) {
					return err
				}
				continue
			}
			_, err = p.upstreamConn.WriteTo(byteBuf.Bytes(), srvr)
			if err != nil {
				if attempts == len(p.upstreams) {
					return err
				}
				continue
			}
			n, err := p.upstreamConn.Read(recvBuf)
			if err != nil {
				if attempts == len(p.upstreams) {
					return err
				}
				return err
			}
			byteBuf.Reset()
			_, err = byteBuf.Write(recvBuf[:n])
			if err != nil {
				if attempts == len(p.upstreams) {
					return err
				}
				return err
			}
			err = binary.Read(byteBuf, binary.BigEndian, &pkt)
			if err != nil {
				if attempts == len(p.upstreams) {
					return err
				}
				continue
			}
			break
		}
		return nil
	}()
	if err != nil {
		return err
	}
	if pkt.Stratum < 16 {
		pkt.Stratum++
	}
	byteBuf.Reset()
	err = binary.Write(byteBuf, binary.BigEndian, pkt)
	if err != nil {
		return err
	}
	_, err = p.listener.WriteToUDP(byteBuf.Bytes(), peer)
	if err != nil {
		return err
	}
	return nil
}

func (p *Proxy) getNextAvailableServer(currIdx *int) (*net.UDPAddr, error) {
	p.Lock()
	defer p.Unlock()
	if len(p.upstreams) == 0 {
		return nil, ErrNoUpstreamNTPServers
	}
	*currIdx++
	if *currIdx >= len(p.upstreams) {
		*currIdx = 0
	}
	return p.upstreams[*currIdx], nil
}

func (p *Proxy) Start(ctx context.Context) (err error) {
	logger := zerolog.Ctx(ctx)
	refreshRate := time.Duration(p.refreshRate) * time.Second
	p.listener, err = net.ListenUDP("udp", p.bindAddr)
	if err != nil {
		return err
	}
	p.upstreamConn, err = net.ListenUDP("udp", p.upstreamBind)
	if err != nil {
		p.listener.Close()
		return err
	}
	go func() {
		p.tick = time.NewTicker(refreshRate)
		for {
			select {
			case <-ctx.Done():
				return
			case <-p.tick.C:
				go p.UpdateLocalTime(ctx)
			default:
				err = p.listener.SetReadDeadline(time.Now().Add(refreshRate))
				if err != nil {
					logger.Err(err).Msg("failed to set listener deadline")
					continue
				}
				buffer := p.bufPool.Get().(*[]byte)
				buf := *buffer
				n, peer, err := p.listener.ReadFromUDP(buf)
				if err != nil {
					p.bufPool.Put(buffer)
					continue
				}
				go func() {
					defer p.bufPool.Put(buffer)
					err := p.handlePkt(ctx, peer, buf[:n])
					if err != nil {
						logger.Err(err).Msgf("remote addr: %s", peer.String())
					}
				}()
			}
		}
	}()
	return nil
}

func (p *Proxy) Stop(ctx context.Context) error {
	p.tick.Stop()
	err := p.listener.Close()
	if err != nil {
		return err
	}
	err = p.upstreamConn.Close()
	if err != nil {
		return err
	}
	p.listener = nil
	p.upstreamConn = nil
	return nil
}

func (p *Proxy) Restart(ctx context.Context) error {
	if p.listener != nil && p.upstreamConn != nil {
		err := p.Stop(ctx)
		if err != nil {
			return err
		}
	}
	return p.Start(ctx)
}

func (p *Proxy) Status(ctx context.Context) error {
	return nil
}

func (p *Proxy) Configure(_ context.Context, servers, _ []string) error {
	p.Lock()
	defer p.Unlock()
	p.upstreams = []*net.UDPAddr{} // clear existing servers
	for _, server := range servers {
		addr, err := net.ResolveUDPAddr("udp", server)
		if err != nil {
			return err
		}
		p.upstreams = append(p.upstreams, addr)
	}
	return nil
}
