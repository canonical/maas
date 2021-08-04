package tftp

import (
	"bytes"
	"context"
	"encoding/binary"
	"errors"
	"net"
	"net/url"
	"os"
	"strconv"
	"sync"
	"time"

	"github.com/rs/zerolog"

	"rackd/internal/config"
	"rackd/internal/service"
)

const (
	bufferSize = 516 // max payload size is op (2 bytes) + block (2 bytes) + 512 bytes of data
)

const (
	OpUnknown uint16 = iota
	OpRRQ
	OpWRQ
	OpData
	OpAck
	OpError
	OpOAck
)

var (
	ErrInvalidTFTPPacket     = errors.New("the given buffer is not a valid TFTP packet")
	ErrUnknownTFTPPacketType = errors.New("the given packet is of an unknown operation type")
	ErrNoUpstreamConfigured  = errors.New("there is no upstream TFTP server configured")
)

type TFTPService interface {
	service.Service
	Configure(context.Context, []string) error
}

type Packet struct {
	OpCode  uint16
	File    string
	Mode    string
	Block   uint16
	ErrCode uint16
	ErrMsg  string
	Opts    map[string]string
	Data    []byte
}

func decodePkt(buf []byte) (*Packet, error) {
	if len(buf) < 4 { // min length as defined by RFC 1350, some types have a larger min length, those will be checked bellow
		return nil, ErrInvalidTFTPPacket
	}

	var pkt Packet
	pkt.OpCode = binary.BigEndian.Uint16(buf[:2])
	switch pkt.OpCode {
	case OpRRQ, OpWRQ:
		bufSlice := bytes.Split(buf[2:], []byte{0})
		if len(bufSlice) < 2 {
			return nil, ErrInvalidTFTPPacket
		}
		pkt.File = string(bufSlice[0])
		pkt.Mode = string(bufSlice[1])
		if len(bufSlice) < 4 {
			return &pkt, nil
		}
		pkt.Opts = make(map[string]string)
		for i := 2; i+1 < len(bufSlice); i += 2 {
			pkt.Opts[string(bufSlice[i])] = string(bufSlice[i+1])
		}
		return &pkt, nil
	case OpData:
		pkt.Block = binary.BigEndian.Uint16(buf[2:4])
		pkt.Data = buf[4:]
		return &pkt, nil
	case OpAck:
		pkt.Block = binary.BigEndian.Uint16(buf[2:4])
		return &pkt, nil
	case OpError:
		if len(buf) < 5 {
			return nil, ErrInvalidTFTPPacket
		}
		pkt.ErrCode = binary.BigEndian.Uint16(buf[2:4])
		pkt.ErrMsg = string(buf[4 : len(buf)-1])
		return &pkt, nil
	case OpOAck:
		if len(buf) < 6 {
			return nil, ErrInvalidTFTPPacket
		}
		bufSlice := bytes.Split(buf[2:], []byte{0})
		pkt.Opts = make(map[string]string)
		for i := 0; i+1 < len(bufSlice); i += 2 {
			pkt.Opts[string(bufSlice[i])] = string(bufSlice[i+1])
		}
		return &pkt, nil
	}
	return nil, ErrInvalidTFTPPacket
}

func encodePkt(pkt *Packet) (buf []byte, err error) {
	if pkt.OpCode == OpUnknown {
		return nil, ErrUnknownTFTPPacketType
	}
	var n int
	// RRQ and WRQ
	if pkt.OpCode == OpRRQ || pkt.OpCode == OpWRQ {
		buf = make([]byte, 4+len(pkt.File)+len(pkt.Mode)) // Op (2) + file (n) + delimiter (1) + mode (n) + delimiter (1)
		binary.BigEndian.PutUint16(buf[:2], pkt.OpCode)
		n += 2
		n += copy(buf[n:n+len(pkt.File)], pkt.File)
		buf[n] = 0 // file delimiter
		n++
		n += copy(buf[n:n+len(pkt.Mode)], pkt.Mode)
		buf[n] = 0
		n++
		for name, value := range pkt.Opts {
			buf = append(append(buf, name...), 0)
			buf = append(append(buf, value...), 0)
		}
		return buf, nil
	}
	// Error
	if pkt.OpCode == OpError {
		buf = make([]byte, 5+len(pkt.ErrMsg))
		binary.BigEndian.PutUint16(buf[:2], pkt.OpCode)
		binary.BigEndian.PutUint16(buf[2:4], pkt.ErrCode)
		n = 4
		n += copy(buf[n:n+len(pkt.ErrMsg)], pkt.ErrMsg)
		buf[n] = 0
		return buf, nil
	}
	// OAck
	if pkt.OpCode == OpOAck {
		buf = make([]byte, 2)
		binary.BigEndian.PutUint16(buf, pkt.OpCode)
		for name, value := range pkt.Opts {
			buf = append(append(buf, name...), 0)
			buf = append(append(buf, value...), 0)
		}
		return buf, nil
	}
	// Ack or Data
	buf = make([]byte, 4)
	binary.BigEndian.PutUint16(buf[:2], pkt.OpCode)
	binary.BigEndian.PutUint16(buf[2:4], pkt.Block)
	if len(pkt.Data) > 0 {
		buf = append(buf, pkt.Data...)
	}
	return buf, nil
}

type Forwarder struct {
	sync.Mutex
	lAddr        *net.UDPAddr
	upstreams    []*net.UDPAddr
	upstreamAddr *net.UDPAddr
	listener     *net.UDPConn
	client       *net.UDPConn
	readTimeout  time.Duration
	bufPool      sync.Pool
}

func New(bindAddr string, readTimeout int) (*Forwarder, error) {
	lAddr, err := net.ResolveUDPAddr("udp", bindAddr)
	if err != nil {
		return nil, err
	}
	return &Forwarder{
		lAddr:       lAddr,
		readTimeout: time.Duration(readTimeout) * time.Second,
		bufPool: sync.Pool{
			New: func() interface{} {
				buf := make([]byte, bufferSize)
				return &buf
			},
		},
	}, nil
}

func (f *Forwarder) Name() string {
	return "tftp"
}

func (f *Forwarder) Type() int {
	return service.SvcTFTP
}

func (f *Forwarder) PID() int {
	return os.Getpid()
}

func (f *Forwarder) sendReadOnlyErr(peer *net.UDPAddr) error {
	msg := &Packet{
		OpCode:  OpError,
		ErrCode: 20, // TFTP illegal operation
		ErrMsg:  "this TFTP server is read-only",
	}
	buf, err := encodePkt(msg)
	if err != nil {
		return err
	}
	_, err = f.listener.WriteToUDP(buf, peer)
	if err != nil {
		return err
	}
	return nil
}

func (f *Forwarder) transaction(ctx context.Context, peer *net.UDPAddr, buf []byte) error {
	f.Lock() // Lock forwarder for duration of transaction
	defer f.Unlock()
	pkt, err := decodePkt(buf)
	if err != nil {
		return err
	}
	if pkt.OpCode == OpWRQ {
		return f.sendReadOnlyErr(peer)
	}

	var lastData bool
	currPkt := pkt
	currBuf := buf
	lastWriter := peer
	readBuffer := f.bufPool.Get().(*[]byte)
	readBuf := *readBuffer
	defer f.bufPool.Put(readBuffer)
	for {
		select {
		case <-ctx.Done():
			return nil
		default:
			if currPkt.OpCode == OpRRQ {
				_, err = f.client.Write(currBuf)
				if err != nil {
					return err
				}
				n, err := f.client.Read(readBuf)
				if err != nil {
					return err
				}
				err = f.setListenerDeadline()
				if err != nil {
					return err
				}
				currBuf = readBuf[:n]
				currPkt, err = decodePkt(currBuf)
				if err != nil {
					return err
				}
				continue
			}
			if currPkt.OpCode == OpData {
				_, err = f.listener.WriteToUDP(currBuf, peer)
				if err != nil {
					return err
				}
				var (
					n      int
					remote *net.UDPAddr
				)
				for {
					n, remote, err = f.listener.ReadFromUDP(readBuf)
					if err != nil {
						return err
					}
					if remote == peer { // we only care that the peer within the transaction responds, other clients will have to retransmit
						break
					}
				}
				err = f.setClientDeadline()
				if err != nil {
					return err
				}
				currBuf = readBuf[:n]
				currPkt, err = decodePkt(currBuf)
				if err != nil {
					return err
				}
				lastWriter = f.upstreamAddr
				if len(currPkt.Data) < 512 {
					lastData = true
				}
				continue
			}
			if currPkt.OpCode == OpAck || currPkt.OpCode == OpOAck {
				_, err = f.client.Write(currBuf)
				if err != nil {
					return err
				}
				n, err := f.client.Read(readBuf)
				if err != nil {
					return err
				}
				err = f.setListenerDeadline()
				currBuf = readBuf[:n]
				currPkt, err = decodePkt(currBuf)
				if err != nil {
					return err
				}
				lastWriter = peer
				if lastData {
					return nil
				}
				continue
			}
			// Error
			if lastWriter == f.upstreamAddr {
				_, err = f.client.Write(currBuf)
				if err != nil {
					return err
				}
				return nil
			}
			_, err = f.listener.WriteToUDP(currBuf, peer)
			if err != nil {
				return err
			}
			return nil
		}
	}
}

func (f *Forwarder) setListenerDeadline() error {
	return f.listener.SetReadDeadline(time.Now().Add(f.readTimeout))
}

func (f *Forwarder) setClientDeadline() error {
	return f.client.SetReadDeadline(time.Now().Add(f.readTimeout))
}

func (f *Forwarder) Start(ctx context.Context) (err error) {
	f.listener, err = net.ListenUDP("udp", f.lAddr)
	if err != nil {
		return err
	}
	clientBindAddr := &net.UDPAddr{} // bind to any
	logger := zerolog.Ctx(ctx)
	go func() {
		for {
			select {
			case <-ctx.Done():
				return
			default:
				func() {
					f.upstreamAddr, err = f.getUpstream()
					if err != nil {
						logger.Err(err).Msg("error fetching upstream address")
						time.Sleep(time.Second)
						return
					}
					f.client, err = net.DialUDP("udp", clientBindAddr, f.upstreamAddr)
					if err != nil {
						logger.Err(err).Msg("error connecting to TFTP upstream")
						return
					}
					defer f.client.Close()
					err := f.setListenerDeadline()
					if err != nil {
						logger.Err(err).Msg("error setting read deadline for TFTP")
						return
					}
					buffer := f.bufPool.Get().(*[]byte)
					buf := *buffer
					n, peer, err := f.listener.ReadFromUDP(buf)
					if err != nil {
						f.bufPool.Put(buffer)
						var nErr net.Error
						if errors.As(err, &nErr); !nErr.Timeout() {
							logger.Err(err).Msgf("error reading from: %s", peer.String())
						}
						return
					}
					defer f.bufPool.Put(buffer)
					err = f.transaction(ctx, peer, buf[:n]) // packets are handled sequentially to ensure a full transaction
					if err != nil {
						logger.Err(err).Msgf("remote addr: %s", peer.String())
					}
				}()
			}
		}
	}()
	return nil
}

func (f *Forwarder) Stop(ctx context.Context) error {
	err := f.listener.Close()
	if err != nil {
		return err
	}
	if f.client != nil {
		return f.client.Close()
	}
	return nil
}

func (f *Forwarder) Restart(ctx context.Context) error {
	err := f.Stop(ctx)
	if err != nil {
		return err
	}
	return f.Start(ctx)
}

func (f *Forwarder) getUpstream() (*net.UDPAddr, error) {
	f.Lock()
	defer f.Unlock()
	if len(f.upstreams) == 0 {
		return nil, ErrNoUpstreamConfigured
	}
	upstream := f.upstreams[0]
	f.upstreams = append(f.upstreams[1:], upstream) // place selected at end of slice
	return upstream, nil
}

func (f *Forwarder) Configure(_ context.Context, regions []string) (err error) {
	f.Lock()
	defer f.Unlock()
	f.upstreams = make([]*net.UDPAddr, len(regions))
	for i, region := range regions {
		if regionURL, err := url.Parse(region); err == nil {
			port := regionURL.Port()
			if len(port) == 0 {
				port = strconv.Itoa(config.Config.TftpPort)
			}
			f.upstreams[i], err = net.ResolveUDPAddr("udp", net.JoinHostPort(regionURL.Hostname(), port))
			if err != nil {
				return err
			}
		} else if host, port, err := net.SplitHostPort(region); err == nil {
			f.upstreams[i], err = net.ResolveUDPAddr("udp", net.JoinHostPort(host, port))
			if err != nil {
				return err
			}
		} else { // if not url, try as host or IP
			f.upstreams[i], err = net.ResolveUDPAddr("udp", net.JoinHostPort(region, strconv.Itoa(config.Config.TftpPort)))
			if err != nil {
				return err
			}
		}
	}
	return nil
}

func (f *Forwarder) Status(_ context.Context) error {
	return nil
}
