package ipmi

import (
	"bytes"
	"crypto/md5"
	"crypto/rand"
	"encoding"
	"encoding/binary"
	"io"
	"net"
	"strconv"
	"strings"
	"sync/atomic"
	"time"
)

const (
	recvBufferSize = 1024
)

const (
	IPMICMDGetDeviceID              uint8 = 0x01
	IPMICMDChassisStatus            uint8 = 0x01
	IPMICMDChassisControl           uint8 = 0x02
	IPMICMDSetSystemBootOptions     uint8 = 0x08
	IPMICMDGetSystemBootOptions     uint8 = 0x09
	IPMICMDAuthCapabilities         uint8 = 0x38
	IPMICMDGetSessionChallenge      uint8 = 0x39
	IPMICMDActivateSession          uint8 = 0x3a
	IPMICMDSetSessionPrivilegeLevel uint8 = 0x3b
	IPMICMDCloseSession             uint8 = 0x3c
	IPMICMDSetUsername              uint8 = 0x45
	IPMICMDGetUsername              uint8 = 0x46

	IPMIBootDeviceNone          uint8 = 0x00
	IPMIBootDevicePxe           uint8 = 0x04
	IPMIBootDeviceDisk          uint8 = 0x08
	IPMIBootDeviceSafe          uint8 = 0x0c
	IPMIBootDeviceDiag          uint8 = 0x10
	IPMIBootDeviceCDROM         uint8 = 0x14
	IPMIBootDeviceBios          uint8 = 0x18
	IPMIBootDeviceRemoteFloppy  uint8 = 0x1c
	IPMIBootDeviceRemoteCDROM   uint8 = 0x20
	IPMIBootDeviceRemotePrimary uint8 = 0x24
	IPMIBootDeviceRemoteDisk    uint8 = 0x2c
	IPMIBootDeviceFloppy        uint8 = 0x3c

	IPMIAuthTypeNone     uint8 = 0x0
	IPMIAuthTypeMD2      uint8 = 0x1
	IPMIAuthTypeMD5      uint8 = 0x2
	IPMIAuthTypeKey      uint8 = 0x4
	IPMIAuthTypePassword uint8 = 0x4
	IPMIAuthTypeOEM      uint8 = 0x5
	IPMIAuthTypeRMCPPlus uint8 = 0x6
)

const (
	IPMIInProgressSetComplete uint8 = iota
	IPMIInProgressInProgress
	IPMIInProgressCommit
)

const (
	IPMIPowerStateOff uint8 = iota
	IPMIPowerStateOn
	IPMIPowerStateCycle
	IPMIPowerStateHardReset
	IPMIPowerStatePulseDiag
	IPMIPowerStateAcpiSoft
)

const (
	IPMIBootParamInProgress uint8 = iota
	IPMIBootParamSvcPartSelect
	IPMIBootParamSvcPartScan
	IPMIBootParamFlagValid
	IPMIBootParamInfoAck
	IPMIBootParamBootFlags
	IPMIBootParamInitInfo
	IPMIBootParamInitMbox
)

const (
	IPMIPrivLevelNone = iota
	IPMIPrivLevelCallback
	IPMIPrivLevelUser
	IPMIPrivLevelOperator
	IPMIPrivLevelAdmin
	IPMIPrivLevelOEM
)

type ConnInfo struct {
	Port     int
	Path     string
	IP       string
	BindAddr string
	Username string
	Password string
	PrivLvl  string
}

type Request struct {
	NetworkFn uint8
	Cmd       uint8
	Data      interface{}
}

type Response interface {
	encoding.BinaryUnmarshaler
	Data() interface{}
}

type LanConn struct {
	Session    session
	IPMIHeader ipmiHeader
	Info       ConnInfo
	rqSeq      uint8
	transport  net.Conn
	connected  bool
	authCode   [16]byte
	username   [16]byte
	priv       uint8
	lun        uint8
	timeout    time.Duration
}

func NewLanConn(info ConnInfo) *LanConn {
	conn := &LanConn{
		Info: info,
	}
	switch strings.ToLower(info.PrivLvl) {
	case "user":
		conn.priv = IPMIPrivLevelUser
	case "operator":
		conn.priv = IPMIPrivLevelOperator
	case "administrator":
		conn.priv = IPMIPrivLevelAdmin
	}
	copy(conn.username[:], info.Username[:])
	copy(conn.authCode[:], info.Password[:])
	return conn
}

func (l *LanConn) Open() error {
	lAddr, err := net.ResolveUDPAddr("udp", net.JoinHostPort(l.Info.BindAddr, "0"))
	if err != nil {
		return err
	}
	rAddr, err := net.ResolveUDPAddr("udp", net.JoinHostPort(l.Info.IP, strconv.Itoa(l.Info.Port)))
	if err != nil {
		return err
	}
	conn, err := net.DialUDP("udp", lAddr, rAddr)
	if err != nil {
		return err
	}
	l.transport = conn
	l.connected = true
	return nil
}

func (l *LanConn) Close() error {
	if l.connected {
		l.Session = session{}
		return l.transport.Close()
	}
	return nil
}

func (l *LanConn) nextSeq() uint32 {
	if l.Session.Seq != 0 {
		atomic.AddUint32(&l.Session.Seq, 1)
	}
	return atomic.LoadUint32(&l.Session.Seq) << 2
}

func (l *LanConn) nextRqSeq() uint8 {
	l.IPMIHeader.RqSeq++
	return l.IPMIHeader.RqSeq
}

func (l *LanConn) sigMD5(data []byte) []byte {
	hash := md5.New()
	binary.Write(hash, binary.BigEndian, l.authCode)
	binary.Write(hash, binary.BigEndian, l.Session.ID)
	binary.Write(hash, binary.BigEndian, data)
	binary.Write(hash, binary.BigEndian, l.Session.Seq)
	binary.Write(hash, binary.BigEndian, l.authCode)
	return hash.Sum(nil)
}

func (l *LanConn) Send(req *Request, resp Response) error {
	pkt := &Packet{
		RMCPHeader: rmcpHeader{
			Version:  rmcpV1,
			Sequence: 0xff,
			Class:    rmcpClassIPMI,
		},
		Session: session{
			AuthType: l.Session.AuthType,
			Seq:      l.nextSeq(),
			ID:       l.Session.ID,
		},
		IPMIHeader: ipmiHeader{
			RsAddr:     0x20,
			NetFnRsLUN: req.NetworkFn<<2 | l.IPMIHeader.NetFnRsLUN&3,
			Cmd:        req.Cmd,
			RqAddr:     0x81,
			RqSeq:      l.nextRqSeq(),
		},
	}

	if l.Session.AuthType != 0 {
		copy(pkt.AuthCode[:], l.authCode[:])
	}

	err := pkt.SetData(req.Data)
	if err != nil {
		return err
	}

	msg, err := MarshalPacket(pkt)
	if err != nil {
		return err
	}

	if l.Session.AuthType == IPMIAuthTypeMD5 {
		hlen := binary.Size(rmcpHeader{}) + binary.Size(session{})
		offset := hlen + len(pkt.AuthCode) + 1
		sig := l.sigMD5(msg[offset:])
		copy(msg[hlen:], sig)
	}

	_, err = l.transport.Write(msg)
	if err != nil {
		return err
	}

	buf := make([]byte, recvBufferSize)
	if l.timeout > 0 {
		err = l.transport.SetReadDeadline(time.Now().Add(l.timeout))
		if err != nil {
			return err
		}
	}
	n, err := l.transport.Read(buf)
	if err != nil && err != io.EOF {
		return err
	}
	rPkt, err := UnmarshalPacket(buf[:n])
	if err != nil {
		return err
	}
	if resp != nil {
		return resp.UnmarshalBinary(rPkt.Data)
	}
	return nil
}

func (l *LanConn) genSeq() ([4]byte, error) {
	var seq [4]byte
	_, err := rand.Read(seq[:])
	if err != nil {
		return seq, err
	}
	return seq, nil
}

func (l *LanConn) Ping() (err error) {
	pkt := &ASFPacket{
		RMCPHeader: rmcpHeader{
			Version:  rmcpV1,
			Class:    rmcpClassASF,
			Sequence: 0xff,
		},
		ASFHeader: asfHeader{
			IANANum: ianaASF,
			Type:    asfTypePing,
		},
	}

	payload := MarshalASFPacket(pkt)
	_, err = l.transport.Write(payload)
	if err != nil {
		return err
	}
	buf := make([]byte, recvBufferSize)
	if l.timeout > 0 {
		err = l.transport.SetReadDeadline(time.Now().Add(l.timeout))
		if err != nil {
			return err
		}
	}

	n, err := l.transport.Read(buf)
	if err != nil {
		return err
	}
	pkt, err = UnmarshalASFPacket(buf[n:])
	if err != nil {
		return err
	}
	return pkt.ValidatePong()
}

type AuthCapReq struct {
	Channel   uint8
	PrivLevel uint8
}

type AuthCapResp struct {
	Channel         uint8
	AuthTypeSupport uint8
	Flags           uint8
	V1              uint8
	V2              uint8
	OEMID           [3]byte
	OEMAux          uint8
}

func (a *AuthCapResp) UnmarshalBinary(b []byte) error {
	buf := bytes.NewReader(b)
	err := binary.Read(buf, binary.BigEndian, a)
	if err != nil && err != io.EOF {
		return err
	}
	return nil
}

func (a *AuthCapResp) Data() interface{} {
	return a
}

func (l *LanConn) GetAuthCaps() (*AuthCapResp, error) {
	req := &Request{
		NetworkFn: NetworkFnApp,
		Cmd:       IPMICMDAuthCapabilities,
		Data: AuthCapReq{
			Channel:   0x0e,
			PrivLevel: l.priv,
		},
	}
	var resp AuthCapResp

	err := l.Send(req, &resp)
	if err != nil {
		return nil, err
	}

	return &resp, nil
}

type SessionChallengeRequest struct {
	AuthType uint8
	Username [16]byte
}

type SessionChallengeResp struct {
	Code      uint8
	SessionID uint32
	Challenge [16]byte
}

func (s *SessionChallengeResp) UnmarshalBinary(b []byte) error {
	buf := bytes.NewReader(b)
	return binary.Read(buf, binary.BigEndian, s)
}

func (s *SessionChallengeResp) Data() interface{} {
	return s
}

func (l *LanConn) GetSessionChallenge(authType uint8) (*SessionChallengeResp, error) {
	req := &Request{
		NetworkFn: NetworkFnApp,
		Cmd:       IPMICMDGetSessionChallenge,
		Data: SessionChallengeRequest{
			AuthType: authType,
			Username: l.username,
		},
	}
	var resp SessionChallengeResp

	err := l.Send(req, &resp)
	if err != nil {
		return nil, err
	}
	l.Session.AuthType = authType
	return &resp, nil
}

type ActivateSessionReq struct {
	AuthType  uint8
	PrivLevel uint8
	AuthCode  [16]byte
	Seq       [4]byte
}

type ActivateSessionResp struct {
	Code      uint8
	AuthType  uint8
	SessionID uint32
	Seq       uint32
	MaxPriv   uint8
}

func (a *ActivateSessionResp) UnmarshalBinary(b []byte) error {
	buf := bytes.NewReader(b)
	return binary.Read(buf, binary.BigEndian, a)
}

func (a *ActivateSessionResp) Data() interface{} {
	return a
}

func (l *LanConn) ActivateSession(challenge *SessionChallengeResp) error {
	outboundSeq, err := l.genSeq()
	if err != nil {
		return err
	}
	req := &Request{
		NetworkFn: NetworkFnApp,
		Cmd:       IPMICMDActivateSession,
		Data: ActivateSessionReq{
			AuthType:  l.Session.AuthType,
			PrivLevel: l.priv,
			AuthCode:  challenge.Challenge,
			Seq:       outboundSeq,
		},
	}
	var resp ActivateSessionResp
	err = l.Send(req, &resp)
	if err != nil {
		return err
	}

	l.connected = true
	l.Session.ID = resp.SessionID
	l.Session.AuthType = resp.AuthType
	l.Session.Seq = resp.Seq
	return nil
}

type SetPrivilegeReq struct {
	Priv uint8
}

type SetPrivilegeResponse struct {
	Code uint8
	Priv uint8
}

func (s *SetPrivilegeResponse) UnmarshalBinary(b []byte) error {
	buf := bytes.NewReader(b)
	return binary.Read(buf, binary.BigEndian, s)
}

func (s *SetPrivilegeResponse) Data() interface{} {
	return s
}

func (l *LanConn) SetPrivilege() error {
	req := &Request{
		NetworkFn: NetworkFnApp,
		Cmd:       IPMICMDSetSessionPrivilegeLevel,
		Data: SetPrivilegeReq{
			Priv: l.priv,
		},
	}
	var resp SetPrivilegeResponse
	err := l.Send(req, &resp)
	if err != nil {
		return err
	}
	l.priv = resp.Priv
	return nil
}

func (l *LanConn) StartSession() error {
	err := l.Ping()
	if err != nil {
		return err
	}
	authCaps, err := l.GetAuthCaps()
	if err != nil {
		return err
	}

	authType := IPMIAuthTypeNone
	for _, authT := range []uint8{IPMIAuthTypeMD5, IPMIAuthTypePassword, IPMIAuthTypeMD2} {
		if authCaps.AuthTypeSupport&authT == 0 {
			authType = authT
			break
		}
	}

	challenge, err := l.GetSessionChallenge(authType)
	if err != nil {
		return err
	}

	err = l.ActivateSession(challenge)
	if err != nil {
		return err
	}
	return l.SetPrivilege()
}

type CloseSessionReq struct {
	SessionID uint32
}

func (l *LanConn) EndSession() error {
	req := &Request{
		NetworkFn: NetworkFnApp,
		Cmd:       IPMICMDCloseSession,
		Data: CloseSessionReq{
			SessionID: l.Session.ID,
		},
	}
	return l.Send(req, nil)
}

type DeviceIDResp struct {
	Code                    uint8
	DeviceID                uint8
	DeviceRevision          uint8
	FirmwareRevision1       uint8
	FirmwareRevision2       uint8
	IPMIVersion             uint8
	AdditionalDeviceSupport uint8
	ManufacturerID          uint16
	ProductID               uint16
}

func (d *DeviceIDResp) UnmarshalBinary(b []byte) error {
	buf := bytes.NewReader(b)
	return binary.Read(buf, binary.BigEndian, d)
}

func (d *DeviceIDResp) Data() interface{} {
	return d
}

func (l *LanConn) DeviceID() (*DeviceIDResp, error) {
	req := &Request{
		NetworkFn: NetworkFnApp,
		Cmd:       IPMICMDGetDeviceID,
	}
	var resp DeviceIDResp
	err := l.Send(req, &resp)
	if err != nil {
		return nil, err
	}
	return &resp, nil
}

type SetBootOptionsReq struct {
	Param uint8
	Data  []uint8
}

func (l *LanConn) SetBootParam(param uint8, vals ...uint8) error {
	req := &Request{
		NetworkFn: NetworkFnChassis,
		Cmd:       IPMICMDSetSystemBootOptions,
		Data: SetBootOptionsReq{
			Param: param,
			Data:  vals,
		},
	}
	return l.Send(req, nil)
}

func (l *LanConn) SetBootDevice(bootDev uint8) error {
	err := l.SetBootParam(IPMIBootParamInProgress, IPMIInProgressInProgress)
	if err != nil {
		return err
	}
	defer l.SetBootParam(IPMIBootParamInProgress, IPMIInProgressSetComplete)

	err = l.SetBootParam(IPMIBootParamInfoAck, 0x01, 0x01)
	if err != nil {
		return err
	}

	err = l.SetBootParam(IPMIBootParamBootFlags, 0x80, bootDev, 0x00, 0x00, 0x00)
	if err != nil {
		return err
	}
	err = l.SetBootParam(IPMIBootParamInProgress, IPMIInProgressCommit)
	if err != nil {
		return err
	}
	return nil
}

func (l *LanConn) PowerCtrl(state uint8) error {
	req := &Request{
		NetworkFn: NetworkFnChassis,
		Cmd:       IPMICMDChassisControl,
		Data:      state,
	}
	return l.Send(req, nil)
}

type GetUsernameReq struct {
	UserID uint8
}

type GetUsernameResp struct {
	Code     uint8
	Username string
}

func (g *GetUsernameResp) UnmarshalBinary(b []byte) error {
	buf := bytes.NewReader(b)
	return binary.Read(buf, binary.BigEndian, g)
}

func (g *GetUsernameResp) Data() interface{} {
	return g
}

func (l *LanConn) GetUserName(id uint8) (string, error) {
	req := &Request{
		NetworkFn: NetworkFnApp,
		Cmd:       IPMICMDGetUsername,
		Data: GetUsernameReq{
			UserID: id,
		},
	}
	var resp GetUsernameResp
	err := l.Send(req, &resp)
	if err != nil {
		return "", err
	}
	return resp.Username, nil
}

type SetUsernameReq struct {
	UserID   uint8
	Username string
}

func (l *LanConn) SetUsername(id uint8, username string) error {
	req := &Request{
		NetworkFn: NetworkFnApp,
		Cmd:       IPMICMDSetUsername,
		Data: SetUsernameReq{
			UserID:   id,
			Username: username,
		},
	}
	return l.Send(req, nil)
}
