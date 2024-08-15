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
	"errors"
	"fmt"
	"io"
	"net"
	"strconv"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestBufWriterWrite(t *testing.T) {
	testcases := map[string]struct {
		in  []any
		out []byte
		err error
	}{
		"one write": {
			in:  []any{int32(1)},
			out: []byte{0x00, 0x00, 0x00, 0x01},
		},
		"multi write": {
			in: []any{int32(1), int32(2)},
			out: []byte{
				0x00, 0x00, 0x00, 0x01,
				0x00, 0x00, 0x00, 0x02,
			},
		},
		"one error": {
			in:  []any{int(1)},
			err: errors.New("binary.Write: some values are not fixed-sized in type int"),
		},
		"multi error": {
			in:  []any{int(1), int32(2), "abc"},
			err: errors.New("binary.Write: some values are not fixed-sized in type string"),
		},
	}

	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			bw := &bufWriter{
				Buf: &bytes.Buffer{},
			}

			for _, in := range tc.in {
				bw.Write(in)
			}

			if tc.err != nil {
				assert.Equal(t, tc.err.Error(), bw.Err.Error())
				return
			}

			assert.Equal(t, tc.out, bw.Bytes())
		})
	}
}

func TestBufReaderRead(t *testing.T) {
	testcases := map[string]struct {
		in  io.Reader
		out []int32
		err error
	}{
		"one read": {
			in:  bytes.NewBuffer([]byte{0x00, 0x00, 0x00, 0x01}),
			out: []int32{1},
		},
		"multi read": {
			in:  bytes.NewBuffer([]byte{0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x02}),
			out: []int32{1, 2},
		},
		"empty": {
			in:  bytes.NewBuffer(nil),
			out: []int32{-1},
			err: io.EOF,
		},
		"short byte length": {
			in:  bytes.NewBuffer([]byte{0x00, 0x00, 0x01}),
			out: []int32{-1},
			err: io.ErrUnexpectedEOF,
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			br := &bufReader{
				Buf: tc.in,
			}

			for _, expected := range tc.out {
				var i int32

				br.Read(&i)

				fmt.Printf("%s: %d\n", name, i)
				fmt.Printf("%s: %d\n", name, expected)

				if expected > -1 { // use -1 to force an iteration when there is no output
					assert.Equal(t, expected, i)
				}
			}

			if tc.err != nil {
				assert.ErrorIs(t, tc.err, br.Err)
			}
		})
	}
}

func TestInitMessageMarshalBinary(t *testing.T) {
	// use byte literals to ensure MarshalBinary and UnmarshalBinary are not both wrong but working together
	testcases := map[string]struct {
		in  *InitMessage
		out []byte
		err error
	}{
		"empty": {
			in:  &InitMessage{},
			out: []byte{0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00},
		},
		"std": {
			in:  StdInitMsg,
			out: []byte{0x00, 0x00, 0x00, 0x64, 0x00, 0x00, 0x00, 0x18},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			result, err := tc.in.MarshalBinary()
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, tc.err, err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, tc.out, result)
		})
	}
}

func TestInitMessageUnmarshalBinary(t *testing.T) {
	testcases := map[string]struct {
		in  []byte
		out *InitMessage
		err error
	}{
		"no bytes": {
			err: io.EOF,
		},
		"zero": {
			in:  []byte{0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00},
			out: &InitMessage{},
		},
		"std": {
			in:  []byte{0x00, 0x00, 0x00, 0x64, 0x00, 0x00, 0x00, 0x18},
			out: StdInitMsg,
		},
		"too short": {
			in:  []byte{0x00, 0x00, 0x00, 0x64, 0x00, 0x00, 0x00},
			err: io.ErrUnexpectedEOF,
		},
		"too long": {
			in:  []byte{0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x18},
			out: &InitMessage{},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			msg := &InitMessage{}

			err := msg.UnmarshalBinary(tc.in)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, tc.err, err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, *tc.out, *msg)
		})
	}
}

func TestInitMessageValidate(t *testing.T) {
	testcases := map[string]struct {
		in  *InitMessage
		out error
	}{
		"valid": {
			in: &InitMessage{ProtoVer: StdInitMsg.ProtoVer, HeaderSize: StdInitMsg.HeaderSize},
		},
		"invalid": {
			in:  &InitMessage{ProtoVer: 99, HeaderSize: 23},
			out: ErrInvalidProto,
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			err := tc.in.Validate()
			assert.ErrorIs(t, tc.out, err)
		})
	}
}

type mockBinaryMarshaler struct {
	content []byte
	err     error
}

func (m *mockBinaryMarshaler) MarshalBinary() ([]byte, error) {
	if m.err != nil {
		return nil, m.err
	}

	return m.content, nil
}

func (m *mockBinaryMarshaler) UnmarshalBinary([]byte) error {
	return nil
}

type mockTextMarshaler struct {
	content []byte
	err     error
}

func (m *mockTextMarshaler) MarshalText() ([]byte, error) {
	if m.err != nil {
		return nil, m.err
	}

	return m.content, nil
}

func (m *mockTextMarshaler) UnmarshalText([]byte) error {
	return nil
}

func TestMessageMapSetValue(t *testing.T) {
	testMac, _ := net.ParseMAC("00:00:5e:00:53:01")
	testInfinibandMac, _ := net.ParseMAC("00:00:00:00:fe:80:00:00:00:00:00:00:02:00:5e:10:00:00:00:01")

	// bytes literals are generated from tcpdump of omshell
	testcases := map[string]struct {
		in  map[string]any
		out MessageMap
		err map[string]error
	}{
		"valid primitives": {
			in: map[string]any{
				"int":     int(1),
				"int8":    int8(1),
				"int16":   int16(1),
				"int32":   int32(1),
				"int64":   int64(1),
				"uint":    uint(1),
				"uint8":   uint8(1),
				"uint16":  uint16(1),
				"uint32":  uint32(1),
				"uint64":  uint64(1),
				"float32": float32(1.1),
				"float64": float64(1.1),
				"string":  "Hello, World!",
				"bytes":   []byte{0xc0, 0x07},
				"byte":    byte(0x02),
				"rune":    'a',
			},
			out: MessageMap{
				"int":     []byte{0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01}, // defaults to arch's max width (i.e amd64 == int64, i386 == int32)
				"int8":    []byte{0x01},
				"int16":   []byte{0x00, 0x01},
				"int32":   []byte{0x00, 0x00, 0x00, 0x01},
				"int64":   []byte{0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01},
				"uint":    []byte{0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01},
				"uint8":   []byte{0x01},
				"uint16":  []byte{0x00, 0x01},
				"uint32":  []byte{0x00, 0x00, 0x00, 0x01},
				"uint64":  []byte{0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01},
				"float32": []byte{0x3f, 0x8c, 0xcc, 0xcd},
				"float64": []byte{0x3f, 0xf1, 0x99, 0x99, 0x99, 0x99, 0x99, 0x9a},
				"string":  []byte("Hello, World!"),
				"bytes":   []byte{0xc0, 0x07},
				"byte":    []byte{0x02},
				"rune":    []byte{0x00, 0x00, 0x00, 'a'},
			},
		},
		"valid complex": {
			in: map[string]any{
				"binaryMarshaler":                   &mockBinaryMarshaler{content: []byte("hello, world!")},
				"textMarshaler":                     &mockTextMarshaler{content: []byte("hello, world!")},
				"net.IP (IPv4)":                     net.ParseIP("10.0.0.1").To4(),
				"net.IP (IPv6)":                     net.ParseIP("fe80::e38b:c3a7:748e:14ce"),
				"net.HardwareAddr":                  testMac,
				"net.HardwareAddr (infiniband MAC)": testInfinibandMac,
			},
			out: MessageMap{
				"binaryMarshaler": []byte("hello, world!"),
				"textMarshaler":   []byte("hello, world!"),
				"net.IP (IPv4)":   []byte{0x31, 0x30, 0x2e, 0x30, 0x2e, 0x30, 0x2e, 0x31},
				"net.IP (IPv6)": []byte{
					0x66, 0x65, 0x38, 0x30, 0x3a, 0x3a, 0x65, 0x33, 0x38,
					0x62, 0x3a, 0x63, 0x33, 0x61, 0x37, 0x3a, 0x37, 0x34,
					0x38, 0x65, 0x3a, 0x31, 0x34, 0x63, 0x65,
				},
				"net.HardwareAddr": []byte(testMac),
				"net.HardwareAddr (infiniband MAC)": []byte{
					0x0, 0x0, 0x0, 0x0, 0xfe, 0x80, 0x0, 0x0, 0x0, 0x0,
					0x0, 0x0, 0x2, 0x0, 0x5e, 0x10, 0x0, 0x0, 0x0, 0x1,
				},
			},
		},
		"error complex": {
			in: map[string]any{
				"binaryMarshaler": &mockBinaryMarshaler{err: io.ErrUnexpectedEOF},
			},
			out: make(MessageMap),
			err: map[string]error{
				"binaryMarshaler": io.ErrUnexpectedEOF,
			},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			mm := make(MessageMap)

			for k, v := range tc.in {
				err := mm.SetValue(k, v)
				if err != nil {
					if tc.err != nil {
						assert.ErrorIs(t, tc.err[k], err)
						continue
					}

					t.Fatal(err)
				}

				assert.Equal(t, tc.out[k], mm[k], k)
			}
		})
	}
}

func TestMessageMapMarshalBinary(t *testing.T) {
	testMac, _ := net.ParseMAC("00:00:5e:00:53:01")

	testcases := map[string]struct {
		in  MessageMap
		out [][]byte // maps are unordered, so we check each value is in the payload
		err error
	}{
		"one value": {
			in: MessageMap{
				"ip": []byte{0x31, 0x30, 0x2e, 0x30, 0x2e, 0x30, 0x2e, 0x31}, // Big Endian 10.0.0.1
			},
			out: [][]byte{
				{
					0x00, 0x02, 0x69, 0x70, 0x00, 0x00, 0x00, 0x08,
					0x31, 0x30, 0x2e, 0x30, 0x2e, 0x30, 0x2e, 0x31,
				},
				{
					0x00, 0x00,
				},
			},
		},
		"multiple values": {
			in: MessageMap{
				"ip":  []byte{0x31, 0x30, 0x2e, 0x30, 0x2e, 0x30, 0x2e, 0x31},
				"mac": []byte(testMac),
			},
			out: [][]byte{
				{
					0x00, 0x02, 0x69, 0x70, 0x00, 0x00, 0x00, 0x08,
					0x31, 0x30, 0x2e, 0x30, 0x2e, 0x30, 0x2e, 0x31,
				},
				{
					0x00, 0x03, 0x6d, 0x61, 0x63, 0x00, 0x00, 0x00,
					0x06, 0x00, 0x00, 0x5e, 0x00, 0x53, 0x01,
				},
				{
					0x00, 0x00,
				},
			},
		},
		"empty": {
			out: [][]byte{{0x00, 0x00}}, // we still add a keylen of 0 when a map is empty to know to move to the next section if one exists
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			result, err := tc.in.MarshalBinary()
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, tc.err, err)
					return
				}

				t.Fatal(err)
			}

			for _, out := range tc.out {
				// assert.Contains does not support bytes, so here we use bytes.Contains()
				assert.True(t, bytes.Contains(result, out))
			}
		})
	}
}

func TestMessageMapUnmarhsalBinary(t *testing.T) {
	testcases := map[string]struct {
		in  []byte
		out MessageMap
		err error
	}{
		"one value": {
			in: []byte{
				0x00, 0x02, 0x69, 0x70, 0x00, 0x00, 0x00, 0x08,
				0x31, 0x30, 0x2e, 0x30, 0x2e, 0x30, 0x2e, 0x31,
				0x00, 0x00,
			},
			out: MessageMap{
				"ip": []byte{0x31, 0x30, 0x2e, 0x30, 0x2e, 0x30, 0x2e, 0x31},
			},
		},
		"multiple values": {
			in: []byte{
				0x00, 0x02, 0x69, 0x70, 0x00, 0x00, 0x00, 0x08,
				0x31, 0x30, 0x2e, 0x30, 0x2e, 0x30, 0x2e, 0x31,
				0x00, 0x03, 0x6d, 0x61, 0x63, 0x00, 0x00, 0x00,
				0x06, 0x00, 0x00, 0x5e, 0x00, 0x53, 0x01, 0x00,
				0x00,
			},
			out: MessageMap{
				"ip":  []byte{0x31, 0x30, 0x2e, 0x30, 0x2e, 0x30, 0x2e, 0x31},
				"mac": []byte{0x00, 0x00, 0x5e, 0x00, 0x53, 0x01},
			},
		},
		"no values": {
			in:  []byte{0x00, 0x00},
			out: make(MessageMap),
		},
		"empty": {
			err: io.EOF,
		},
		"too short": {
			in:  []byte{0x00, 0x02},
			err: io.EOF,
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			mm := make(MessageMap)

			err := mm.UnmarshalBinary(tc.in)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, tc.err, err)
					return
				}

				t.Fatal(err)
			}

			for k, v := range tc.out {
				assert.Equal(t, v, mm[k])
			}
		})
	}
}

func TestMessageMapSize(t *testing.T) {
	testcases := map[string]struct {
		in  []any
		out int
	}{
		"empty": {
			out: 2,
		},
		"one value": {
			in:  []any{uint8(1)},
			out: 10,
		},
		"four values": {
			in: []any{
				uint8(1),
				uint16(1),
				uint32(1),
				uint64(1),
			},
			out: 45,
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			mm := make(MessageMap)

			for i, val := range tc.in {
				mm.SetValue(strconv.Itoa(i), val)
			}

			assert.Equal(t, tc.out, mm.Size())
		})
	}
}

func TestMessageMarshalBinary(t *testing.T) {
	testcases := map[string]struct {
		in  *Message
		out []byte
	}{
		"empty": {
			in: &Message{},
			out: []byte{
				0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
				0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
				0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
			},
		},
		"header only": {
			in: &Message{
				forSigning: true,
				AuthID:     1,
				Op:         OpOpen,
				Handle:     1,
				TID:        1,
				RID:        1,
			},
			out: []byte{
				0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x1,
				0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0, 0x1,
				0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0, 0x0,
			},
		},
		"signed": {
			in: &Message{
				AuthID: 1,
				Op:     OpOpen,
				Handle: 1,
				TID:    1,
				RID:    1,
				Sig:    "signed",
			},
			out: []byte{
				0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0, 0x6, 0x0, 0x0, 0x0, 0x1,
				0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0, 0x1,
				0x0, 0x0, 0x0, 0x0, 0x73, 0x69, 0x67, 0x6e, 0x65, 0x64,
			},
		},
		"with msg": {
			in: &Message{
				forSigning: true,
				AuthID:     1,
				Op:         OpOpen,
				Handle:     1,
				TID:        1,
				RID:        1,
				Msg: MessageMap{
					"type": []byte("host"),
				},
			},
			out: []byte{
				0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0, 0x1,
				0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0, 0x1, 0x0, 0x4, 0x74, 0x79,
				0x70, 0x65, 0x0, 0x0, 0x0, 0x4, 0x68, 0x6f, 0x73, 0x74, 0x0,
				0x0, 0x0, 0x0,
			},
		},
		"with obj": {
			in: &Message{
				forSigning: true,
				AuthID:     1,
				Op:         OpOpen,
				Handle:     1,
				TID:        1,
				RID:        1,
				Msg:        MessageMap{},
				Obj: MessageMap{
					"ip": []byte{0x31, 0x30, 0x2e, 0x30, 0x2e, 0x30, 0x2e, 0x31},
				},
			},
			out: []byte{
				0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0, 0x1,
				0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0, 0x2,
				0x69, 0x70, 0x0, 0x0, 0x0, 0x8, 0x31, 0x30, 0x2e, 0x30, 0x2e,
				0x30, 0x2e, 0x31, 0x0, 0x0,
			},
		},
		"with msg and obj": {
			in: &Message{
				forSigning: true,
				AuthID:     1,
				Op:         OpOpen,
				Handle:     1,
				TID:        1,
				RID:        1,
				Msg: MessageMap{
					"type": []byte("host"),
				},
				Obj: MessageMap{
					"ip": []byte{0x31, 0x30, 0x2e, 0x30, 0x2e, 0x30, 0x2e, 0x31},
				},
			},
			out: []byte{
				0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0,
				0x1, 0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0, 0x1, 0x0, 0x4,
				0x74, 0x79, 0x70, 0x65, 0x0, 0x0, 0x0, 0x4, 0x68, 0x6f,
				0x73, 0x74, 0x0, 0x0, 0x0, 0x2, 0x69, 0x70, 0x0, 0x0,
				0x0, 0x8, 0x31, 0x30, 0x2e, 0x30, 0x2e, 0x30, 0x2e,
				0x31, 0x0, 0x0,
			},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			result, err := tc.in.MarshalBinary()
			if err != nil {
				t.Fatal(err)
			}

			assert.Equal(t, tc.out, result)
		})
	}
}

func TestMessageUnmarshalBinary(t *testing.T) {
	testcases := map[string]struct {
		in  []byte
		out *Message
		err error
	}{
		"empty": {
			in:  []byte{},
			err: io.EOF,
		},
		"response": {
			in: []byte{
				0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x01,
				0x2b, 0xf5, 0xb8, 0x83, 0x0d, 0xbf, 0x33, 0xa7, 0x00, 0x00, 0x00, 0x04, 0x6e, 0x61, 0x6d, 0x65,
				0x00, 0x00, 0x00, 0x09, 0x6f, 0x6d, 0x61, 0x70, 0x69, 0x5f, 0x6b, 0x65, 0x79, 0x00, 0x09, 0x61,
				0x6c, 0x67, 0x6f, 0x72, 0x69, 0x74, 0x68, 0x6d, 0x00, 0x00, 0x00, 0x19, 0x48, 0x4d, 0x41, 0x43,
				0x2d, 0x4d, 0x44, 0x35, 0x2e, 0x53, 0x49, 0x47, 0x2d, 0x41, 0x4c, 0x47, 0x2e, 0x52, 0x45, 0x47,
				0x2e, 0x49, 0x4e, 0x54, 0x2e, 0x00, 0x00,
			},
			out: &Message{
				forSigning: true,
				AuthID:     0,
				Op:         OpUpdate,
				Handle:     1,
				TID:        737523843,
				RID:        230634407,
				Msg:        MessageMap{},
				Obj: MessageMap{
					"algorithm": []byte("HMAC-MD5.SIG-ALG.REG.INT."),
					"name":      []byte("omapi_key"),
				},
			},
		},
		"too short": {
			in: []byte{
				0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00,
			},
			err: io.ErrUnexpectedEOF,
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			m := NewMessage(true)

			err := m.UnmarshalBinary(tc.in)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, *tc.out, *m)
		})
	}
}

func TestMessageString(t *testing.T) {
	msg := &Message{
		AuthID: 1,
		Op:     OpOpen,
		Handle: 1,
		TID:    1,
		RID:    1,
	}

	assert.Equal(t, msg.String(), "Omapi Message: Op OPEN TID 1 RID 1")
}

func TestMessageGenerateTID(t *testing.T) {
	msg := &Message{}

	msg.GenerateTID()

	assert.Less(t, int(msg.TID), 1<<32)
}
