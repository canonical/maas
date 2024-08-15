// Copyright (c) 2023-2024 Canonical Ltd
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

package omapi

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"math"
	"math/big"
	"net"
)

const (
	OpUnknown int32 = iota
	OpOpen
	OpRefresh
	OpUpdate
	OpNotify
	OpStatus
	OpDelete
)

var (
	ErrUnsupportedMapType = errors.New("the given type is unsupported for MessageMap")
	ErrKeyTooLong         = errors.New("the given key is too long")
	ErrValueTooLarge      = errors.New("the given value is too large")
	ErrInvalidProto       = errors.New("the returned protocol is not supported")
	ErrInvalidMsgHandle   = errors.New("handle received from server is invalid")
	ErrObjNotFound        = errors.New("the requested object was not found")
	ErrObjNotCreated      = errors.New("the requested object was not able to be created")
	ErrObjNotDeleted      = errors.New("the requested object was not able to be deleted")
	ErrObjNotUpdated      = errors.New("the requested object was not able to be updated")
)

var (
	OpCodeToString = map[int32]string{
		OpUnknown: "UNKNOWN",
		OpOpen:    "OPEN",
		OpRefresh: "REFRESH",
		OpUpdate:  "UPDATE",
		OpNotify:  "NOTIFY",
		OpStatus:  "STATUS",
		OpDelete:  "DELETE",
	}

	StdInitMsg = &InitMessage{
		ProtoVer:   100,
		HeaderSize: 24,
	}
)

type HostReservation struct {
	Hostname string
	IP       net.IP
	MAC      net.HardwareAddr
}

type bufWriter struct {
	Buf io.Writer
	Err error
}

func (b *bufWriter) Write(v any) {
	err := binary.Write(b.Buf, binary.BigEndian, v)
	if err != nil {
		b.Err = err
	}
}

func (b *bufWriter) Bytes() []byte {
	buf, ok := b.Buf.(*bytes.Buffer)
	if !ok {
		return nil
	}

	return buf.Bytes()
}

type bufReader struct {
	Buf io.Reader
	Err error
}

func (b *bufReader) Read(v any) {
	err := binary.Read(b.Buf, binary.BigEndian, v)
	if err != nil {
		b.Err = err
	}
}

type InitMessage struct {
	ProtoVer   int32
	HeaderSize int32
}

func (i *InitMessage) MarshalBinary() ([]byte, error) {
	writer := &bufWriter{
		Buf: &bytes.Buffer{},
	}

	writer.Write(i.ProtoVer)
	writer.Write(i.HeaderSize)

	return writer.Bytes(), writer.Err
}

func (i *InitMessage) UnmarshalBinary(b []byte) error {
	reader := &bufReader{
		Buf: bytes.NewBuffer(b),
	}

	reader.Read(&i.ProtoVer)
	reader.Read(&i.HeaderSize)

	return reader.Err
}

func (i *InitMessage) Validate() error {
	if i.ProtoVer != StdInitMsg.ProtoVer || i.HeaderSize != StdInitMsg.HeaderSize {
		return ErrInvalidProto
	}

	return nil
}

type MessageMap map[string][]byte

func (m MessageMap) SetValue(k string, v any) error {
	if len(k) > math.MaxInt16 {
		return fmt.Errorf("%w: %s", ErrKeyTooLong, k)
	}

	var buf []byte

	switch val := v.(type) {
	case []byte:
		buf = val
	case string:
		buf = []byte(val)
	case encoding.BinaryMarshaler:
		b, err := val.MarshalBinary()
		if err != nil {
			return err
		}

		buf = b
	case encoding.TextMarshaler:
		b, err := val.MarshalText()
		if err != nil {
			return err
		}

		buf = b
	default:
		b, err := binaryWrite(val)
		if err != nil {
			return err
		}

		buf = b
	}

	if len(buf) > math.MaxInt32 {
		return ErrValueTooLarge
	}

	m[k] = buf

	return nil
}

func (m MessageMap) MarshalBinary() ([]byte, error) {
	var err error

	writer := &bufWriter{
		Buf: &bytes.Buffer{},
	}

	for k, v := range m {
		keyLen := int16(len(k))
		valLen := int32(len(v))

		key := []byte(k)

		writer.Write(keyLen)
		writer.Write(key)
		writer.Write(valLen)

		_, err = writer.Buf.Write(v) // value should already be Big Endian from SetValue()
		if err != nil {
			return nil, err
		}
	}

	// end
	_, err = writer.Buf.Write([]byte{0x00, 0x00})
	if err != nil {
		return nil, err
	}

	return writer.Bytes(), writer.Err
}

func (m MessageMap) UnmarshalBinary(b []byte) error {
	var (
		keyLen   int16
		valueLen int32
	)

	// no using bufReader because errors should be captured early
	// else, malformed packets will block parsing
	buf := bytes.NewBuffer(b)

	for {
		err := binary.Read(buf, binary.BigEndian, &keyLen)
		if err != nil {
			return err
		}

		if keyLen == 0 {
			break // end of map
		}

		key := make([]byte, int(keyLen))

		err = binary.Read(buf, binary.BigEndian, key)
		if err != nil {
			return err
		}

		err = binary.Read(buf, binary.BigEndian, &valueLen)
		if err != nil {
			return err
		}

		val := make([]byte, int(valueLen))

		err = binary.Read(buf, binary.BigEndian, val)
		if err != nil {
			return err
		}

		m[string(key)] = val
	}

	return nil
}

func (m MessageMap) Size() int {
	size := 2 // last key len

	for k, v := range m {
		size = size + 2 + len(k) + 4 + len(v) // key len, key, val len, val
	}

	return size
}

type Message struct {
	Msg        MessageMap
	Obj        MessageMap
	Sig        string
	AuthID     int32
	Op         int32
	Handle     int32
	TID        int32
	RID        int32
	forSigning bool
}

func NewMessage(forSigning bool) *Message {
	return &Message{
		Msg:        make(MessageMap),
		Obj:        make(MessageMap),
		forSigning: forSigning,
	}
}

func NewMessageWithValues(
	forSigning bool,
	authID int32,
	op int32,
	handle int32,
	tid int32,
	rid int32,
	sig string,
) *Message {
	return &Message{
		AuthID:     authID,
		Op:         op,
		Handle:     handle,
		TID:        tid,
		RID:        rid,
		Sig:        sig,
		Msg:        make(MessageMap),
		Obj:        make(MessageMap),
		forSigning: forSigning,
	}
}

func (m *Message) MarshalBinary() ([]byte, error) {
	var err error

	writer := &bufWriter{
		Buf: &bytes.Buffer{},
	}

	if !m.forSigning {
		writer.Write(uint32(m.AuthID))
	}

	writer.Write(uint32(len(m.Sig)))
	writer.Write(m.Op)
	writer.Write(m.Handle)
	writer.Write(m.TID)
	writer.Write(m.RID)

	var msgBytes, objBytes []byte

	msgBytes, err = m.Msg.MarshalBinary()
	if err != nil {
		return nil, err
	}

	_, err = writer.Buf.Write(msgBytes)
	if err != nil {
		return nil, err
	}

	objBytes, err = m.Obj.MarshalBinary()
	if err != nil {
		return nil, err
	}

	_, err = writer.Buf.Write(objBytes)
	if err != nil {
		return nil, err
	}

	if !m.forSigning {
		_, err = writer.Buf.Write([]byte(m.Sig))
		if err != nil {
			return nil, err
		}
	}

	return writer.Bytes(), writer.Err
}

func (m *Message) UnmarshalBinary(b []byte) error {
	// not using bufReader here to ensure we error early and do not read from the wrong offset
	buf := bytes.NewBuffer(b)
	bytesRead := 0

	var sigLen int32

	err := binary.Read(buf, binary.BigEndian, &m.AuthID)
	if err != nil {
		return err
	}

	bytesRead += binary.Size(m.AuthID)

	err = binary.Read(buf, binary.BigEndian, &sigLen)
	if err != nil {
		return err
	}

	bytesRead += binary.Size(sigLen)

	err = binary.Read(buf, binary.BigEndian, &m.Op)
	if err != nil {
		return err
	}

	bytesRead += binary.Size(m.Op)

	err = binary.Read(buf, binary.BigEndian, &m.Handle)
	if err != nil {
		return err
	}

	bytesRead += binary.Size(m.Handle)

	err = binary.Read(buf, binary.BigEndian, &m.TID)
	if err != nil {
		return err
	}

	bytesRead += binary.Size(m.TID)

	err = binary.Read(buf, binary.BigEndian, &m.RID)
	if err != nil {
		return err
	}

	bytesRead += binary.Size(m.RID)

	err = m.Msg.UnmarshalBinary(b[bytesRead:])
	if err != nil {
		return err
	}

	bytesRead += m.Msg.Size()

	err = m.Obj.UnmarshalBinary(b[bytesRead:])
	if err != nil {
		return err
	}

	bytesRead += m.Obj.Size()

	sig := make([]byte, len(b)-bytesRead)

	err = binary.Read(bytes.NewBuffer(b[bytesRead:]), binary.BigEndian, sig)
	if err != nil {
		return err
	}

	m.Sig = string(sig)

	return nil
}

func (m *Message) String() string {
	return fmt.Sprintf("Omapi Message: Op %s TID %d RID %d", OpCodeToString[m.Op], m.TID, m.RID)
}

func (m *Message) GenerateTID() error {
	max := big.NewInt(math.MaxInt32)

	tid, err := rand.Int(rand.Reader, max)
	if err != nil {
		return err
	}

	m.TID = int32(tid.Int64())

	return nil
}

func (m *Message) Sign(auth Authenticator) error {
	msg, err := m.MarshalBinary()
	if err != nil {
		return err
	}

	m.Sig, err = auth.Sign(msg)

	return err
}

func (m *Message) Verify(auth Authenticator) error {
	msg, err := m.MarshalBinary()
	if err != nil {
		return err
	}

	sig, err := auth.Sign(msg)
	if err != nil {
		return err
	}

	if sig != m.Sig {
		return ErrNoAuth
	}

	return nil
}

type Client struct {
	requestAuthenticator Authenticator
	conn                 net.Conn
	dialer               *net.Dialer
	endpoint             string
	secret               string
	reuseConn            bool
	authID               int32
}

func NewClient(endpoint string, secret string, reuseConn bool, dialer *net.Dialer) *Client {
	return &Client{
		endpoint:  endpoint,
		secret:    secret,
		reuseConn: reuseConn,
		dialer:    dialer,
	}
}

func (c *Client) connect(ctx context.Context) (net.Conn, error) {
	if c.reuseConn && c.conn != nil {
		return c.conn, nil
	}

	var (
		conn net.Conn
		err  error
	)

	if c.reuseConn && c.conn != nil {
		conn = c.conn
	} else {
		conn, err = c.dialer.DialContext(ctx, "tcp", c.endpoint)
		if err != nil {
			return nil, err
		}

		if c.reuseConn {
			c.conn = conn
		}
	}

	return conn, nil
}

func (c *Client) Close() error {
	if c.conn != nil {
		return c.conn.Close()
	}

	return nil
}

func (c *Client) initAuthenticator(ctx context.Context, conn net.Conn) error {
	open := NewMessage(true)
	open.Op = OpOpen

	err := open.Msg.SetValue("type", "authenticator")
	if err != nil {
		return err
	}

	err = open.GenerateTID()
	if err != nil {
		return err
	}

	authenticator := NewAuthenticator(c.secret)

	open.Obj = authenticator.Obj()

	req, err := open.MarshalBinary()
	if err != nil {
		return err
	}

	_, err = conn.Write(req)
	if err != nil {
		return err
	}

	buf := make([]byte, 2048)

	n, err := conn.Read(buf)
	if err != nil {
		return err
	}

	resp := &Message{}

	err = resp.UnmarshalBinary(buf[:n])
	if err != nil {
		return err
	}

	if resp.Op != OpUpdate {
		return ErrInvalidAuthType
	}

	if resp.AuthID == 0 {
		return ErrInvalidAuthType
	}

	c.requestAuthenticator = authenticator
	c.authID = resp.AuthID

	return nil
}

func (c *Client) init(ctx context.Context) (net.Conn, error) {
	conn, err := c.connect(ctx)
	if err != nil {
		return nil, err
	}

	if c.requestAuthenticator == nil {
		init, err := StdInitMsg.MarshalBinary()
		if err != nil {
			return nil, err
		}

		_, err = conn.Write(init)
		if err != nil {
			return nil, err
		}

		buf := make([]byte, binary.Size(*StdInitMsg))

		_, err = conn.Read(buf)
		if err != nil {
			return nil, err
		}

		resp := &InitMessage{}

		err = resp.UnmarshalBinary(buf)
		if err != nil {
			return nil, err
		}

		err = resp.Validate()
		if err != nil {
			return nil, err
		}

		err = c.initAuthenticator(ctx, conn)
		if err != nil {
			return nil, err
		}
	}

	return conn, nil
}

func (c *Client) lookup(ctx context.Context, entity string, args map[string]any) (*Message, error) {
	conn, err := c.init(ctx)
	if err != nil {
		return nil, err
	}

	if !c.reuseConn {
		defer func() {
			c.requestAuthenticator = nil

			cErr := conn.Close()
			if cErr != nil {
				if err == nil {
					err = cErr
				}
			}
		}()
	}

	open := NewMessage(true)
	open.Op = OpOpen

	err = open.GenerateTID()
	if err != nil {
		return nil, err
	}

	err = open.Msg.SetValue("type", entity)
	if err != nil {
		return nil, err
	}

	for k, v := range args {
		err = open.Obj.SetValue(k, v)
		if err != nil {
			return nil, err
		}
	}

	err = open.Sign(c.requestAuthenticator)
	if err != nil {
		return nil, err
	}

	req, err := open.MarshalBinary()
	if err != nil {
		return nil, err
	}

	_, err = conn.Write(req)
	if err != nil {
		return nil, err
	}

	resp := make([]byte, 2048)

	n, err := conn.Read(resp)
	if err != nil {
		return nil, err
	}

	result := &Message{}

	err = result.UnmarshalBinary(resp[:n])
	if err != nil {
		return nil, err
	}

	err = result.Verify(c.requestAuthenticator)
	if err != nil {
		return nil, err
	}

	if result.Op != OpUpdate {
		return nil, ErrObjNotFound
	}

	return result, nil
}

func (c *Client) LookupHostIPForMAC(ctx context.Context, mac net.HardwareAddr) (net.IP, error) {
	msg, err := c.lookup(ctx, "host", map[string]any{"hardware-address": []byte(mac)})
	if err != nil {
		return nil, err
	}

	ipBytes, ok := msg.Obj["ip-address"]
	if !ok {
		return nil, ErrObjNotFound
	}

	return net.IP(ipBytes), nil
}

func (c *Client) LookupLeaseIPForMAC(ctx context.Context, mac net.HardwareAddr) (net.IP, error) {
	msg, err := c.lookup(ctx, "lease", map[string]any{"hardware-address": []byte(mac)})
	if err != nil {
		return nil, err
	}

	ipBytes, ok := msg.Obj["ip-address"]
	if !ok {
		return nil, ErrObjNotFound
	}

	return net.IP(ipBytes), nil
}

func (c *Client) LookupLeaseMACForIP(ctx context.Context, ip net.IP) (net.HardwareAddr, error) {
	msg, err := c.lookup(ctx, "lease", map[string]any{"ip-address": []byte(ip)})
	if err != nil {
		return nil, err
	}

	macBytes, ok := msg.Obj["hardware-address"]
	if !ok {
		return nil, ErrObjNotFound
	}

	return net.HardwareAddr(macBytes), nil
}

func (c *Client) LookupHostByName(ctx context.Context, hostname string) (*HostReservation, error) {
	msg, err := c.lookup(ctx, "host", map[string]any{"hostname": hostname})
	if err != nil {
		return nil, err
	}

	ipBytes, ok := msg.Obj["ip-address"]
	if !ok {
		return nil, ErrObjNotFound
	}

	macBytes, ok := msg.Obj["hardware-address"]
	if !ok {
		return nil, ErrObjNotFound
	}

	return &HostReservation{
		IP:       net.IP(ipBytes),
		MAC:      net.HardwareAddr(macBytes),
		Hostname: hostname,
	}, nil
}

func (c *Client) LookupHostByIP(ctx context.Context, ip net.IP) (*HostReservation, error) {
	msg, err := c.lookup(ctx, "host", map[string]any{"ip-address": []byte(ip)})
	if err != nil {
		return nil, err
	}

	macBytes, ok := msg.Obj["hardware-address"]
	if !ok {
		return nil, ErrObjNotFound
	}

	hostname, ok := msg.Obj["hostname"]
	if !ok {
		return nil, ErrObjNotFound
	}

	return &HostReservation{
		IP:       ip,
		MAC:      net.HardwareAddr(macBytes),
		Hostname: string(hostname),
	}, nil
}

func (c *Client) LookupHostByMAC(ctx context.Context, mac net.HardwareAddr) (*HostReservation, error) {
	msg, err := c.lookup(ctx, "host", map[string]any{"hardware-address": []byte(mac)})
	if err != nil {
		return nil, err
	}

	ipBytes, ok := msg.Obj["ip-address"]
	if !ok {
		return nil, ErrObjNotFound
	}

	hostname, ok := msg.Obj["hostname"]
	if !ok {
		return nil, ErrObjNotFound
	}

	return &HostReservation{
		IP:       []byte(ipBytes),
		MAC:      mac,
		Hostname: string(hostname),
	}, nil
}

func (c *Client) LookupLeaseHostForIP(ctx context.Context, ip net.IP) (string, error) {
	msg, err := c.lookup(ctx, "lease", map[string]any{"ip-address": []byte(ip)})
	if err != nil {
		return "", err
	}

	hostname, ok := msg.Obj["hostname"]
	if !ok {
		return "", ErrObjNotFound
	}

	return string(hostname), nil
}

func (c *Client) LookupFailoverState(ctx context.Context, name string, attr string) (MessageMap, error) {
	msg, err := c.lookup(ctx, "failover-state", map[string]any{name: attr})
	if err != nil {
		return nil, err
	}

	return msg.Obj, nil
}

func (c *Client) add(ctx context.Context, entity string, args map[string]any) error {
	conn, err := c.init(ctx)
	if err != nil {
		return err
	}

	open := NewMessage(true)
	open.Op = OpOpen

	err = open.GenerateTID()
	if err != nil {
		return err
	}

	err = open.Msg.SetValue("type", entity)
	if err != nil {
		return err
	}

	err = open.Msg.SetValue("create", true)
	if err != nil {
		return err
	}

	if entity == "host" {
		err = open.Msg.SetValue("exclusive", true)
		if err != nil {
			return err
		}
	}

	for k, v := range args {
		err = open.Obj.SetValue(k, v)
		if err != nil {
			return err
		}
	}

	err = open.Sign(c.requestAuthenticator)
	if err != nil {
		return err
	}

	req, err := open.MarshalBinary()
	if err != nil {
		return err
	}

	_, err = conn.Write(req)
	if err != nil {
		return err
	}

	buf := make([]byte, 2048)

	n, err := conn.Read(buf)
	if err != nil {
		return err
	}

	resp := &Message{}

	err = resp.UnmarshalBinary(buf[:n])
	if err != nil {
		return err
	}

	err = resp.Verify(c.requestAuthenticator)
	if err != nil {
		return err
	}

	if resp.Op != OpUpdate {
		return ErrObjNotCreated
	}

	return nil
}

func (c *Client) AddHost(ctx context.Context, ip net.IP, mac net.HardwareAddr) error {
	return c.add(ctx, "host", map[string]any{
		"ip-address":       []byte(ip),
		"hardware-address": []byte(mac),
		"hardware-type":    1,
	})
}

func (c *Client) AddHostWithSetName(ctx context.Context, ip net.IP, mac net.HardwareAddr, name string) error {
	return c.add(ctx, "host", map[string]any{
		"ip-address":       []byte(ip),
		"hardware-address": []byte(mac),
		"hostname":         []byte(name),
		"hardware-type":    1,
	})
}

func (c *Client) AddHostWithoutIP(ctx context.Context, mac net.HardwareAddr, options ...map[string]any) error {
	args := map[string]any{
		"hardware-address": []byte(mac),
		"hardware-type":    1,
	}

	for _, option := range options {
		for k, v := range option {
			args[k] = v
		}
	}

	return c.add(ctx, "host", args)
}

func (c *Client) AddHostWithOptions(ctx context.Context, ip net.IP, mac net.HardwareAddr, options map[string]any) error {
	args := map[string]any{
		"ip-address":       []byte(ip),
		"hardware-address": []byte(mac),
		"hardware-type":    1,
	}

	for k, v := range options {
		args[k] = v
	}

	return c.add(ctx, "host", args)
}

func (c *Client) AddGroup(ctx context.Context, groupName string, statements string) error {
	return c.add(ctx, "group", map[string]any{"statements": statements})
}

func (c *Client) AddHostWithGroup(ctx context.Context, ip net.IP, mac net.HardwareAddr, group string) error {
	return c.add(ctx, "host", map[string]any{
		"ip-address":       []byte(ip),
		"hardware-address": []byte(mac),
		"hardware-type":    1,
		"group":            group,
	})
}

func (c *Client) del(ctx context.Context, entity string, args map[string]any) error {
	conn, err := c.init(ctx)
	if err != nil {
		return err
	}

	open := NewMessage(true)
	open.Op = OpOpen

	err = open.GenerateTID()
	if err != nil {
		return err
	}

	err = open.Msg.SetValue("type", entity)
	if err != nil {
		return err
	}

	for k, v := range args {
		err = open.Obj.SetValue(k, v)
		if err != nil {
			return err
		}
	}

	err = open.Sign(c.requestAuthenticator)
	if err != nil {
		return err
	}

	req1, err := open.MarshalBinary()
	if err != nil {
		return err
	}

	_, err = conn.Write(req1)
	if err != nil {
		return err
	}

	buf := make([]byte, 2048)

	n, err := conn.Read(buf)
	if err != nil {
		return err
	}

	resp1 := &Message{}

	err = resp1.UnmarshalBinary(buf[:n])
	if err != nil {
		return err
	}

	err = resp1.Verify(c.requestAuthenticator)
	if err != nil {
		return err
	}

	if resp1.Op != OpUpdate {
		return ErrObjNotFound
	}

	if resp1.Handle == 0 {
		return ErrInvalidMsgHandle
	}

	del := NewMessageWithValues(
		true,
		0,
		OpDelete,
		resp1.Handle,
		0,
		0,
		"",
	)

	err = del.GenerateTID()
	if err != nil {
		return err
	}

	err = del.Sign(c.requestAuthenticator)
	if err != nil {
		return err
	}

	req2, err := del.MarshalBinary()
	if err != nil {
		return err
	}

	_, err = conn.Write(req2)
	if err != nil {
		return err
	}

	n, err = conn.Read(buf)
	if err != nil {
		return err
	}

	resp2 := &Message{}

	err = resp2.UnmarshalBinary(buf[:n])
	if err != nil {
		return err
	}

	err = resp2.Verify(c.requestAuthenticator)
	if err != nil {
		return err
	}

	if resp2.Op != OpStatus {
		return ErrObjNotDeleted
	}

	return nil
}

func (c *Client) DelHost(ctx context.Context, mac net.HardwareAddr) error {
	return c.del(ctx, "host", map[string]any{"hardware-address": []byte(mac)})
}

func (c *Client) SetHostToGroup(ctx context.Context, hostname string, groupname string) error {
	conn, err := c.init(ctx)
	if err != nil {
		return err
	}

	open := NewMessage(true)
	open.Op = OpOpen

	err = open.GenerateTID()
	if err != nil {
		return err
	}

	err = open.Obj.SetValue("hostname", hostname)
	if err != nil {
		return err
	}

	err = open.Sign(c.requestAuthenticator)
	if err != nil {
		return err
	}

	req1, err := open.MarshalBinary()
	if err != nil {
		return err
	}

	_, err = conn.Write(req1)
	if err != nil {
		return err
	}

	buf := make([]byte, 2048)

	n, err := conn.Read(buf)
	if err != nil {
		return err
	}

	resp1 := &Message{}

	err = resp1.UnmarshalBinary(buf[:n])
	if err != nil {
		return err
	}

	err = resp1.Verify(c.requestAuthenticator)
	if err != nil {
		return err
	}

	if resp1.Op != OpUpdate {
		return ErrObjNotFound
	}

	update := NewMessageWithValues(
		false,
		0,
		OpUpdate,
		resp1.Handle,
		0,
		0,
		"",
	)

	err = update.Obj.SetValue("group", groupname)
	if err != nil {
		return err
	}

	err = update.GenerateTID()
	if err != nil {
		return err
	}

	err = update.Sign(c.requestAuthenticator)
	if err != nil {
		return err
	}

	n, err = conn.Read(buf)
	if err != nil {
		return err
	}

	resp2 := &Message{}

	err = resp2.UnmarshalBinary(buf[:n])
	if err != nil {
		return err
	}

	err = resp2.Verify(c.requestAuthenticator)
	if err != nil {
		return err
	}

	if resp2.Op != OpUpdate {
		return ErrObjNotUpdated
	}

	return nil
}
