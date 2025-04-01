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
	"fmt"
	"math/rand"
)

// Opcode indicates the type of operation being requested or performed
type Opcode uint32

//go:generate go run golang.org/x/tools/cmd/stringer -type=Opcode -linecomment=true

const (
	OpUnknown Opcode = iota // UNKNOWN
	OpOpen                  // OPEN
	OpRefresh               // REFRESH
	OpUpdate                // UPDATE
	OpNotify                // NOTIFY
	OpStatus                // STATUS
	OpDelete                // DELETE
)

// Message is structured packet of data used for communication with ISC-DHCP
// using OMAPI
type Message struct {
	Message       map[string][]byte
	Object        map[string][]byte
	Signature     []byte
	AuthID        uint32
	Operation     Opcode
	Handle        uint32
	TransactionID uint32
	ResponseID    uint32
	signed        bool
}

// NewMessage returns Message with a random TransactionID
func NewMessage() *Message {
	m := &Message{
		Message: make(map[string][]byte),
		Object:  make(map[string][]byte),
		//nolint:gosec // we can use pseudo-random generator here
		TransactionID: uint32(rand.Int31()),
	}

	return m
}

// NewEmptyMessage returns Message without TransactionID
func NewEmptyMessage() *Message {
	m := &Message{
		Message: make(map[string][]byte),
		Object:  make(map[string][]byte),
	}

	return m
}

// NewOpenMessage returns Message with a random TransactionID
// and Operation set to OpOpen
func NewOpenMessage() *Message {
	m := NewMessage()
	m.Operation = OpOpen

	return m
}

// NewDeleteMessage returns Message with a random TransactionID
// and Operation set to OpDelete
func NewDeleteMessage(handle uint32) *Message {
	m := NewMessage()
	m.Operation = OpDelete
	m.Handle = handle

	return m
}

// MarshalBinary created a binary representation of Message that is compatible
// with ISC-DHCP OMAPI protocol.
func (m *Message) MarshalBinary() ([]byte, error) {
	var buf bytes.Buffer
	writer := &errWriter{w: &buf}

	if m.signed {
		writer.writeUint32(m.AuthID)
	}

	//nolint:gosec // OMAPI protocol requires uint32
	writer.writeUint32(uint32(len(m.Signature)))
	writer.writeUint32(uint32(m.Operation))

	writer.writeUint32(m.Handle)
	writer.writeUint32(m.TransactionID)
	writer.writeUint32(m.ResponseID)
	writer.writeMap(m.Message)
	writer.writeMap(m.Object)

	if m.signed {
		writer.writeBytes(m.Signature)
	}

	return buf.Bytes(), writer.err
}

// UnmarshalBinary decodes a binary-encoded representation of a Message.
// The binary data is expected to be in a specific order that corresponds
// to the fields of the Message struct.
func (m *Message) UnmarshalBinary(b []byte) error {
	reader := &errReader{r: bytes.NewBuffer(b)}

	var authlen uint32

	reader.readUint32(&m.AuthID)
	reader.readUint32(&authlen)
	reader.readUint32((*uint32)(&m.Operation))
	reader.readUint32(&m.Handle)
	reader.readUint32(&m.TransactionID)
	reader.readUint32(&m.ResponseID)
	reader.readMap(m.Message)
	reader.readMap(m.Object)

	signature := make([]byte, authlen)
	reader.readBytes(signature)
	m.Signature = signature

	return reader.err
}

func (m *Message) String() string {
	return fmt.Sprintf("OMAPI message{Operation: %s, TID: %d, RID: %d}",
		m.Operation, m.TransactionID, m.ResponseID)
}
