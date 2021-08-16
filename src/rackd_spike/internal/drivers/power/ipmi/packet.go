package ipmi

import (
	"bytes"
	"encoding"
	"encoding/binary"
	"errors"
	"fmt"
)

const (
	rmcpClassASF      uint8 = 0x06
	rmcpClassIPMI     uint8 = 0x07
	rmcpClassNoAckSeq uint8 = 0xff

	rmcpV1 uint8 = 0x06

	ianaASF uint32 = 0x000011be

	asfTypePing uint8 = 0x80
	asfTypePong uint8 = 0x40

	NetworkFnChassis uint8 = 0x00
	NetworkFnApp     uint8 = 0x06
)

var (
	minPktSize = binary.Size(rmcpHeader{}) + binary.Size(session{}) + binary.Size(ipmiHeader{})

	ErrInvalidPacket = errors.New("the received packet is invalid")
)

func computeChecksum(data ...uint8) uint8 {
	var checksum uint8
	for _, d := range data {
		checksum += d
	}
	return -checksum
}

type rmcpHeader struct {
	Version  uint8
	Reserved uint8
	Sequence uint8
	Class    uint8
}

func (r *rmcpHeader) IsAck() bool {
	return r.Class&0x80 != 0
}

type session struct {
	AuthType uint8
	Seq      uint32
	ID       uint32
}

type ipmiHeader struct {
	Len        uint8
	RsAddr     uint8
	NetFnRsLUN uint8
	Checksum   uint8
	RqAddr     uint8
	RqSeq      uint8
	Cmd        uint8
}

type Packet struct {
	RMCPHeader rmcpHeader
	Session    session
	AuthCode   [16]byte
	IPMIHeader ipmiHeader
	Data       []byte
}

func (p *Packet) SetData(data interface{}) error {
	if data == nil {
		return nil
	}
	if encoder, ok := data.(encoding.BinaryMarshaler); ok {
		buf, err := encoder.MarshalBinary()
		if err != nil {
			return err
		}
		p.Data = buf
		return nil
	}
	byteBuf := &bytes.Buffer{}
	err := binary.Write(byteBuf, binary.BigEndian, data)
	if err != nil {
		return err
	}
	p.Data = byteBuf.Bytes()
	return nil
}

func MarshalPacket(p *Packet) ([]byte, error) {
	buf := &bytes.Buffer{}

	err := binary.Write(buf, binary.BigEndian, &p.RMCPHeader)
	if err != nil {
		return nil, err
	}

	err = binary.Write(buf, binary.BigEndian, &p.Session)
	if err != nil {
		return nil, err
	}

	if p.Session.AuthType != IPMIAuthTypeNone {
		err = binary.Write(buf, binary.BigEndian, p.AuthCode)
		if err != nil {
			return nil, err
		}
	}

	p.IPMIHeader.Len = uint8(binary.Size(p.IPMIHeader) + len(p.Data))
	p.IPMIHeader.Checksum = computeChecksum(p.IPMIHeader.RsAddr, p.IPMIHeader.NetFnRsLUN)
	err = binary.Write(buf, binary.BigEndian, &p.IPMIHeader)
	if err != nil {
		return nil, err
	}

	_, err = buf.Write(p.Data)
	if err != nil {
		return nil, err
	}

	payloadChecksum := computeChecksum(p.IPMIHeader.RqAddr, p.IPMIHeader.RqSeq, p.IPMIHeader.Cmd) + computeChecksum(p.Data...)

	err = binary.Write(buf, binary.BigEndian, payloadChecksum)
	if err != nil {
		return nil, err
	}

	return buf.Bytes(), nil
}

func UnmarshalPacket(buf []byte) (*Packet, error) {
	if len(buf) < minPktSize {
		return nil, fmt.Errorf("%w: too short", ErrInvalidPacket)
	}

	pkt := &Packet{}
	reader := bytes.NewReader(buf)

	err := binary.Read(reader, binary.BigEndian, &pkt.RMCPHeader)
	if err != nil {
		return nil, err
	}

	err = binary.Read(reader, binary.BigEndian, &pkt.Session)
	if err != nil {
		return nil, err
	}
	if pkt.Session.AuthType != 0 {
		err = binary.Read(reader, binary.BigEndian, pkt.AuthCode)
		if err != nil {
			return nil, err
		}
	}

	err = binary.Read(reader, binary.BigEndian, &pkt.IPMIHeader)
	if err != nil {
		return nil, err
	}

	if computeChecksum(pkt.IPMIHeader.RsAddr, pkt.IPMIHeader.NetFnRsLUN) != pkt.IPMIHeader.Checksum {
		return nil, fmt.Errorf("%w: checksum does not match", ErrInvalidPacket)
	}
	if pkt.IPMIHeader.Len <= 0 {
		return nil, fmt.Errorf("%w: malformed message len", ErrInvalidPacket)
	}

	dataLen := int(pkt.IPMIHeader.Len) - binary.Size(ipmiHeader{})
	data := make([]byte, dataLen+1)
	_, err = reader.Read(data)
	if err != nil {
		return nil, err
	}

	dataChecksum := data[len(data)-1]
	localChecksum := computeChecksum(
		pkt.IPMIHeader.RqAddr,
		pkt.IPMIHeader.RqSeq,
		pkt.IPMIHeader.Cmd,
	) + computeChecksum(data[:len(data)-1]...)
	if dataChecksum != localChecksum {
		return nil, fmt.Errorf("%w: checksum does not match", ErrInvalidPacket)
	}

	pkt.Data = data[:len(data)-1]
	return pkt, nil
}

func Marshal(data interface{}) ([]byte, error) {
	pkt := &Packet{}
	pkt.SetData(data)
	return MarshalPacket(pkt)
}

func Unmarshal(buf []byte, data interface{}) error {
	pkt, err := UnmarshalPacket(buf)
	if err != nil {
		return err
	}
	if decoder, ok := data.(encoding.BinaryUnmarshaler); ok {
		return decoder.UnmarshalBinary(pkt.Data)
	}
	reader := bytes.NewReader(buf)
	err = binary.Read(reader, binary.BigEndian, pkt.Data)
	if err != nil {
		return err
	}
	return nil
}

type asfHeader struct {
	IANANum  uint32
	Type     uint8
	Tag      uint8
	Reserved uint8
	DataLen  uint8
}

type ASFPong struct {
	IANANum               uint32
	OEM                   uint32
	Entities              uint8
	SupportedInteractions uint8
	Reserved              [6]uint8
}

type ASFPacket struct {
	RMCPHeader rmcpHeader
	ASFHeader  asfHeader
	Data       []byte
}

func (a *ASFPacket) SetData(data interface{}) (err error) {
	if encoder, ok := data.(encoding.BinaryMarshaler); ok {
		a.Data, err = encoder.MarshalBinary()
		if err != nil {
			return err
		}
		return nil
	}
	buf := &bytes.Buffer{}
	err = binary.Write(buf, binary.BigEndian, data)
	if err != nil {
		return err
	}
	a.Data = buf.Bytes()
	return nil
}

func (a *ASFPacket) ValidatePong() error {
	return nil
}

func MarshalASFPacket(pkt *ASFPacket) []byte {
	buf := &bytes.Buffer{}
	binary.Write(buf, binary.BigEndian, pkt.RMCPHeader)
	binary.Write(buf, binary.BigEndian, pkt.ASFHeader)
	buf.Write(pkt.Data)
	return buf.Bytes()
}

func UnmarshalASFPacket(buf []byte) (*ASFPacket, error) {
	hlen := binary.Size(rmcpHeader{}) + binary.Size(asfHeader{})
	if len(buf) < hlen {
		return nil, fmt.Errorf("%w: too short", ErrInvalidPacket)
	}
	var pkt ASFPacket
	reader := bytes.NewReader(buf)
	fullLen := reader.Len()
	err := binary.Read(reader, binary.BigEndian, &pkt.RMCPHeader)
	if err != nil {
		return nil, err
	}
	err = binary.Read(reader, binary.BigEndian, &pkt.ASFHeader)
	remainder := fullLen - reader.Len()
	if remainder > 0 {
		copy(pkt.Data[:], buf[remainder:])
	}
	return &pkt, nil
}
