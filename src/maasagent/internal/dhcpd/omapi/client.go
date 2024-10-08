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
	"encoding/binary"
	"fmt"
	"io"
	"net"
)

const (
	// OMAPI Protocol version
	protocolVersion uint32 = 100
	// OMAPI Header size
	headerSize uint32 = 24
)

type OMAPI interface {
	Close() error
	AddHost(net.IP, net.HardwareAddr) error
	GetHost(map[string][]byte) (Host, error)
	DeleteHost(net.HardwareAddr) error
}

type Client struct {
	authenticator Authenticator
	conn          net.Conn
}

// NewClient returns OMAPI Client with initialised startup and authentication.
// SEND: Startup
// RECV: Startup
// SEND: (unsigned authenticator payload)
// RECV: (unsigned authenticator payload)
func NewClient(conn net.Conn, authenticator Authenticator) (OMAPI, error) {
	client := Client{
		authenticator: authenticator,
		conn:          conn,
	}

	// SEND: Startup
	request := make([]byte, 8)
	binary.BigEndian.PutUint32(request[0:4], protocolVersion)
	binary.BigEndian.PutUint32(request[4:8], headerSize)

	_, err := conn.Write(request)
	if err != nil {
		return nil, err
	}

	// RECV: Startup
	response := make([]byte, 8)

	_, err = io.ReadFull(conn, response)
	if err != nil {
		return nil, err
	}

	if !bytes.Equal(request, response) {
		return nil, fmt.Errorf("protocol mismatch")
	}

	// SEND: (unsigned authenticator payload)
	message := NewOpenMessage()
	message.Message["type"] = []byte("authenticator")
	message.Object = authenticator.Object()

	// We mark is as "signed", because we want to include empty AuthID and
	// Signature for proper OMAPI Authenticator initialisation
	message.signed = true

	req, err := message.MarshalBinary()
	if err != nil {
		return nil, fmt.Errorf("failed to marshal message: %s", message)
	}

	_, err = conn.Write(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send message: %w", err)
	}

	// RECV: (unsigned authenticator payload)
	buf := make([]byte, 2048)
	resp := NewEmptyMessage()

	n, err := conn.Read(buf)
	if err != nil {
		return nil, fmt.Errorf("failed to read message: %w", err)
	}

	err = resp.UnmarshalBinary(buf[:n])
	if err != nil {
		return nil, fmt.Errorf("failed to unmarshal message %s: %w", message, err)
	}

	authID := resp.Handle

	if resp.Operation != OpUpdate || authID == 0 {
		return nil, fmt.Errorf("invalid authentication")
	}

	client.authenticator.SetAuthID(authID)

	return &client, nil
}

func (c *Client) Close() error {
	if c.conn != nil {
		return c.conn.Close()
	}

	return nil
}

// AddHost adds a new host to the DHCP server via OMAPI.
//
// This function constructs an OMAPI message to create a new host with the
// specified IP and MAC address. It sets the message type to "host".
//
// Parameters:
//   - ip: The IP address to assign to the new host.
//   - mac: The MAC address of the new host.
func (c *Client) AddHost(ip net.IP, mac net.HardwareAddr) error {
	message := NewOpenMessage()
	message.Message["type"] = []byte("host")
	message.Message["create"] = boolToBytes(true)
	message.Message["exclusive"] = boolToBytes(true)

	message.Object["hardware-address"] = mac
	message.Object["hardware-type"] = int32ToBytes(1)
	message.Object["ip-address"] = ipToBytes(ip)

	_, err := c.send(message, func(resp *Message) error {
		if resp.Operation != OpUpdate {
			if text, ok := resp.Message["message"]; ok && len(text) > 0 {
				return fmt.Errorf("%s", text)
			}

			return fmt.Errorf("wrong response type, got %s", resp.Operation)
		}

		return nil
	})

	if err != nil {
		return fmt.Errorf("adding host %s failed: %w", mac, err)
	}

	return nil
}

type Host struct {
	Hostname string
	IP       net.IP
	MAC      net.HardwareAddr
}

// GetHost retrieves a host from the DHCP server via OMAPI.
//
// This function constructs an OMAPI message to query a host based on the options.
// The available options for host lookup include, but are not limited to:
//   - ip-address
//   - hardware-address
//   - hardware-type
//
// These options are packed into the message.Object to refine the search criteria.
func (c *Client) GetHost(options map[string][]byte) (Host, error) {
	message := NewOpenMessage()
	message.Message["type"] = []byte("host")

	for k, v := range options {
		message.Object[k] = v
	}

	resp, err := c.send(message, func(resp *Message) error {
		if resp.Operation != OpUpdate {
			if text, ok := resp.Message["message"]; ok && len(text) > 0 {
				return fmt.Errorf("%s", text)
			}

			return fmt.Errorf("wrong response type, got %s", resp.Operation)
		}

		return nil
	})

	host := Host{}
	if err != nil {
		return host, fmt.Errorf("host lookup failed: %w", err)
	}

	host = Host{
		Hostname: string(resp.Object["name"]),
		IP:       net.IP(resp.Object["ip-address"]),
		MAC:      net.HardwareAddr(resp.Object["hardware-address"]),
	}

	return host, nil
}

// DeleteHost deletes a host from the DHCP server via OMAPI.
//
// This function first attempts to locate the host with the specified MAC address.
// If the host is found, it then proceeds to delete it by using returned handle.
func (c *Client) DeleteHost(mac net.HardwareAddr) error {
	message := NewOpenMessage()
	message.Message["type"] = []byte("host")
	message.Message["exclusive"] = boolToBytes(true)
	message.Object["hardware-address"] = mac

	resp, err := c.send(message, func(resp *Message) error {
		if resp.Operation != OpUpdate {
			if text, ok := resp.Message["message"]; ok && len(text) > 0 {
				return fmt.Errorf("%s", text)
			}

			return fmt.Errorf("wrong response type, got %s", resp.Operation)
		}

		if resp.Handle == 0 {
			return fmt.Errorf("invalid message handle")
		}

		return nil
	})

	if err != nil {
		return fmt.Errorf("failed deleting host %s: %w", mac, err)
	}

	message = NewDeleteMessage(resp.Handle)

	_, err = c.send(message, func(resp *Message) error {
		if resp.Operation != OpStatus {
			if text, ok := resp.Message["message"]; ok && len(text) > 0 {
				return fmt.Errorf("%s", text)
			}

			return fmt.Errorf("wrong response type, got %s", resp.Operation)
		}

		return nil
	})

	if err != nil {
		return fmt.Errorf("failed deleting host %s: %w", mac, err)
	}

	return nil
}

type validator func(*Message) error

func (c *Client) send(message *Message, validator validator) (*Message, error) {
	err := sign(c.authenticator, message)
	if err != nil {
		return nil, err
	}

	req, err := message.MarshalBinary()
	if err != nil {
		return nil, fmt.Errorf("failed to marshal message binary: %w", err)
	}

	_, err = c.conn.Write(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send a message: %w", err)
	}

	buf := make([]byte, 2048)
	resp := NewEmptyMessage()

	n, err := c.conn.Read(buf)
	if err != nil {
		return resp, fmt.Errorf("failed to read response: %w", err)
	}

	err = resp.UnmarshalBinary(buf[:n])
	if err != nil {
		return resp, fmt.Errorf("failed to unmarshal message binary: %w", err)
	}

	if err := verify(c.authenticator, buf[:n]); err != nil {
		return resp, err
	}

	return resp, validator(resp)
}

type Authenticator interface {
	AuthID() uint32
	SetAuthID(i uint32)
	AuthLen() uint32
	Sign([]byte) []byte
	Object() map[string][]byte
}

// sign signs a message using provided Authenticator.
// We set m.signed to false/true because it is checked in MarshalBinary.
// During signing we need to skip AuthID and Signature properties for proper
// signature calculation.
func sign(auth Authenticator, m *Message) error {
	m.signed = false
	m.AuthID = auth.AuthID()
	m.Signature = make([]byte, auth.AuthLen())

	data, err := m.MarshalBinary()
	if err != nil {
		return fmt.Errorf("failed signing message: %w", err)
	}

	m.Signature = auth.Sign(data)
	m.signed = true

	return nil
}

// verify checks the signature of the message
// We don't want to Unmarshal to Message and re-calculate signature by calling
// Sign because we cannot guarantee the same order of fields.
// Instead we recalculate signature using bytes received and ignoring some data.
func verify(auth Authenticator, data []byte) error {
	// first 4 bytes is AuthID
	authlen := int(binary.BigEndian.Uint32(data[4:8]))
	expected := make([]byte, authlen)
	copy(expected, data[len(data)-authlen:])

	// skipping 4 bytes of AuthID and ignoring last bytes storing signature.
	signature := auth.Sign(data[4 : len(data)-authlen])

	if !bytes.Equal(expected, signature) {
		return fmt.Errorf("signature mismatch")
	}

	return nil
}
