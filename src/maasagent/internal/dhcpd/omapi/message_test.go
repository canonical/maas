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
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestMessageUnmarshal(t *testing.T) {
	// This is a valid message of type Open that is sent
	// during authentication setup.
	// ISC Object Management API, Opcode: Open
	// Authentication ID: 0
	// Authentication length: 0
	// Opcode: Open (1)
	// Handle: 0
	// ID: 722912184
	// Response ID: 0
	// Message name length: 4
	// Message name: type
	// Message value length: 13
	// Message value: authenticator
	// Message end tag
	// Object name length: 9
	// Object name: algorithm
	// Object value length: 25
	// Object value: 686d61632d6d64352e5349472d414c472e5245472e494e542e
	// Object name length: 4
	// Object name: name
	// Object value length: 9
	// Object value: 6f6d6170695f6b6579
	// Object end tag
	data := []byte{
		0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00,
		0x2b, 0x16, 0xc3, 0xb8, 0x00, 0x00, 0x00, 0x00,
		0x00, 0x04, 0x74, 0x79, 0x70, 0x65, 0x00, 0x00,
		0x00, 0x0d, 0x61, 0x75, 0x74, 0x68, 0x65, 0x6e,
		0x74, 0x69, 0x63, 0x61, 0x74, 0x6f, 0x72, 0x00,
		0x00, 0x00, 0x09, 0x61, 0x6c, 0x67, 0x6f, 0x72,
		0x69, 0x74, 0x68, 0x6d, 0x00, 0x00, 0x00, 0x19,
		0x68, 0x6d, 0x61, 0x63, 0x2d, 0x6d, 0x64, 0x35,
		0x2e, 0x53, 0x49, 0x47, 0x2d, 0x41, 0x4c, 0x47,
		0x2e, 0x52, 0x45, 0x47, 0x2e, 0x49, 0x4e, 0x54,
		0x2e, 0x00, 0x04, 0x6e, 0x61, 0x6d, 0x65, 0x00,
		0x00, 0x00, 0x09, 0x6f, 0x6d, 0x61, 0x70, 0x69,
		0x5f, 0x6b, 0x65, 0x79, 0x00, 0x00,
	}

	m := NewEmptyMessage()
	err := m.UnmarshalBinary(data)
	assert.NoError(t, err)

	assert.Equal(t, uint32(0), m.AuthID)
	assert.Equal(t, 0, len(m.Signature))
	assert.Equal(t, OpOpen, m.Operation)
	assert.Equal(t, uint32(0), m.Handle)
	assert.Equal(t, uint32(722912184), m.TransactionID)
	assert.Equal(t, uint32(0), m.ResponseID)
	assert.Equal(t, []byte("authenticator"), m.Message["type"])
	assert.Equal(t, []byte("hmac-md5.SIG-ALG.REG.INT."), m.Object["algorithm"])
	assert.Equal(t, []byte("omapi_key"), m.Object["name"])
}
