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
	"encoding/binary"
	"io"
	"net"
	"sort"
)

// errWriter is a wrapper that helps to get rid of repetitive error handling.
// As soon as an error occurs, the write method becomes a no-op but the error
// value is saved.
// Reference: https://go.dev/blog/errors-are-values
type errWriter struct {
	w   io.Writer
	err error
}

func (ew *errWriter) writeInt16(v int16) {
	if ew.err != nil {
		return
	}

	ew.err = binary.Write(ew.w, binary.BigEndian, v)
}

func (ew *errWriter) writeInt32(v int32) {
	if ew.err != nil {
		return
	}

	ew.err = binary.Write(ew.w, binary.BigEndian, v)
}

func (ew *errWriter) writeUint32(v uint32) {
	if ew.err != nil {
		return
	}

	ew.err = binary.Write(ew.w, binary.BigEndian, v)
}

func (ew *errWriter) writeBytes(v []byte) {
	if ew.err != nil {
		return
	}

	ew.err = binary.Write(ew.w, binary.BigEndian, v)
}

func (ew *errWriter) writeMap(data map[string][]byte) {
	if ew.err != nil {
		return
	}

	// map[string][]byte should be traversed in a deterministic order for signing
	keys := make(sort.StringSlice, 0, len(data))
	for key := range data {
		keys = append(keys, key)
	}

	sort.Sort(keys)

	for _, key := range keys {
		value := data[key]
		ew.writeInt16(int16(len(key)))
		ew.writeBytes([]byte(key))
		ew.writeInt32(int32(len(value)))
		ew.writeBytes(value)
	}

	ew.writeBytes([]byte{0x00, 0x00})
}

// errReader is a wrapper that helps to get rid of repetitive error handling.
// As soon as an error occurs, the read method becomes a no-op but the error
// value is saved.
// Reference: https://go.dev/blog/errors-are-values
type errReader struct {
	r   io.Reader
	err error
}

func (er *errReader) readInt16(v *int16) {
	if er.err != nil {
		return
	}

	er.err = binary.Read(er.r, binary.BigEndian, v)
}

func (er *errReader) readInt32(v *int32) {
	if er.err != nil {
		return
	}

	er.err = binary.Read(er.r, binary.BigEndian, v)
}

func (er *errReader) readUint32(v *uint32) {
	if er.err != nil {
		return
	}

	er.err = binary.Read(er.r, binary.BigEndian, v)
}

func (er *errReader) readBytes(v []byte) {
	if er.err != nil {
		return
	}

	er.err = binary.Read(er.r, binary.BigEndian, v)
}

func (er *errReader) readMap(data map[string][]byte) {
	var (
		keylen   int16
		valuelen int32
	)

	for {
		er.readInt16(&keylen)

		if keylen == 0 {
			break
		}

		key := make([]byte, keylen)
		er.readBytes(key)

		er.readInt32(&valuelen)
		value := make([]byte, valuelen)
		er.readBytes(value)
		data[string(key)] = value
	}
}

func boolToBytes(v bool) []byte {
	// OMAPI is expecting bool value to be 4 bytes
	b := [4]byte{0, 0, 0, 0}

	if v {
		b[3] = 1
	}

	return b[:]
}

func int32ToBytes(i int32) []byte {
	b := make([]byte, 4)
	binary.BigEndian.PutUint32(b, uint32(i))

	return b
}

func ipToBytes(ip net.IP) []byte {
	if v4 := ip.To4(); v4 != nil {
		return v4
	}

	return ip
}
