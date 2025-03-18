// Copyright (c) 2025 Canonical Ltd
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

package resolver

import (
	"encoding/binary"
	"net"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestSession_String(t *testing.T) {
	testcases := map[string]struct {
		in  net.Addr
		out string
	}{
		"nil": {
			in:  nil,
			out: "",
		},
		"tcp ipv4 and port": {
			in: &net.TCPAddr{
				IP:   net.ParseIP("10.0.0.1"),
				Port: 53,
			},
			out: "tcp://10.0.0.1:53",
		},
		"udp ipv4 and port": {
			in: &net.UDPAddr{
				IP:   net.ParseIP("10.0.0.1"),
				Port: 53,
			},
			out: "udp://10.0.0.1:53",
		},
		"tcp ipv6 and port": {
			in: &net.TCPAddr{
				IP:   net.ParseIP("fe80::44dc:db32:3649:23f7"),
				Port: 53,
			},
			out: "tcp://[fe80::44dc:db32:3649:23f7]:53",
		},
		"udp ipv6 and port": {
			in: &net.UDPAddr{
				IP:   net.ParseIP("fe80::44dc:db32:3649:23f7"),
				Port: 53,
			},
			out: "udp://[fe80::44dc:db32:3649:23f7]:53",
		},
		"tcp ipv6 with zone and port": {
			in: &net.TCPAddr{
				IP:   net.ParseIP("fe80::26ce:47cf:437e:d1b1"),
				Port: 53,
				Zone: "enp0s6",
			},
			out: "tcp://[fe80::26ce:47cf:437e:d1b1%enp0s6]:53",
		},
		"udp ipv6 with zone and port": {
			in: &net.UDPAddr{
				IP:   net.ParseIP("fe80::26ce:47cf:437e:d1b1"),
				Port: 53,
				Zone: "enp0s6",
			},
			out: "udp://[fe80::26ce:47cf:437e:d1b1%enp0s6]:53",
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			s := newSession(tc.in)

			assert.Equal(t, s.String(), tc.out)
		})
	}
}

func TestSession_StoreName(t *testing.T) {
	testcases := map[string]struct {
		in struct {
			generateChain func() []byte
			name          string
		}
		out func() []byte // generate expected chain
	}{
		"nil chain": {
			in: struct {
				generateChain func() []byte
				name          string
			}{
				generateChain: func() []byte {
					return nil
				},
				name: "example.com",
			},
			out: func() []byte {
				return []byte{
					0x07, 'e', 'x', 'a', 'm', 'p', 'l', 'e', 0x03, 'c', 'o', 'm', 0x00,
				}
			},
		},
		"no repeats": {
			in: struct {
				generateChain func() []byte
				name          string
			}{
				generateChain: func() []byte {
					return []byte{
						0x07, 'e', 'x', 'a', 'm', 'p', 'l', 'e', 0x03, 'c', 'o', 'm', 0x00,
					}
				},
				name: "other.org.",
			},
			out: func() []byte {
				return []byte{
					0x07, 'e', 'x', 'a', 'm', 'p', 'l', 'e', 0x03, 'c', 'o', 'm', 0x00,
					0x05, 'o', 't', 'h', 'e', 'r', 0x03, 'o', 'r', 'g', 0x00,
				}
			},
		},
		"prefix repeat": {
			in: struct {
				generateChain func() []byte
				name          string
			}{
				generateChain: func() []byte {
					return []byte{
						0x03, 'f', 'o', 'o',
						0x07, 'e', 'x', 'a', 'm', 'p', 'l', 'e',
						0x03, 'c', 'o', 'm', 0x00,
					}
				},
				name: "foo.other.org",
			},
			out: func() []byte {
				chain := []byte{
					0x03, 'f', 'o', 'o', 0x07, 'e', 'x', 'a', 'm', 'p', 'l', 'e', 0x03, 'c', 'o', 'm', 0x00,
					0x00, 0x00, // 2 empty for fooIdx
				}

				fooIdx := uint16(0 ^ labelPointerShift)
				binary.BigEndian.PutUint16(chain[len(chain)-2:], fooIdx)

				return append(chain, 0x05, 'o', 't', 'h', 'e', 'r', 0x03, 'o', 'r', 'g', 0x00)
			},
		},
		"suffix repeat": {
			in: struct {
				generateChain func() []byte
				name          string
			}{
				generateChain: func() []byte {
					return []byte{
						0x07, 'e', 'x', 'a', 'm', 'p', 'l', 'e', 0x03, 'c', 'o', 'm', 0x00,
					}
				},
				name: "other.com",
			},
			out: func() []byte {
				chain := []byte{
					0x07, 'e', 'x', 'a', 'm', 'p', 'l', 'e', 0x03, 'c', 'o', 'm', 0x00,
					0x05, 'o', 't', 'h', 'e', 'r', 0x00, 0x00, // 2 empty bytes for index
				}

				binary.BigEndian.PutUint16(chain[len(chain)-2:], uint16(8^labelPointerShift))

				return append(chain, 0x00) // end of fqdn
			},
		},
		"prefix and suffix repeat": {
			in: struct {
				generateChain func() []byte
				name          string
			}{
				generateChain: func() []byte {
					return []byte{
						0x03, 'f', 'o', 'o',
						0x07, 'e', 'x', 'a', 'm', 'p', 'l', 'e',
						0x03, 'c', 'o', 'm', 0x00,
					}
				},
				name: "foo.other.com.",
			},
			out: func() []byte {
				chain := []byte{
					0x03, 'f', 'o', 'o', 0x07, 'e', 'x', 'a', 'm', 'p', 'l', 'e', 0x03, 'c', 'o', 'm', 0x00,
					0x00, 0x00,
				}

				binary.BigEndian.PutUint16(chain[len(chain)-2:], uint16(0^labelPointerShift))

				chain = append(chain, 0x05, 'o', 't', 'h', 'e', 'r', 0x00, 0x00)

				binary.BigEndian.PutUint16(chain[len(chain)-2:], uint16(12^labelPointerShift))

				return append(chain, 0x00)
			},
		},
		"multiple repeats": {
			in: struct {
				generateChain func() []byte
				name          string
			}{
				generateChain: func() []byte {
					chain := []byte{
						0x03, 'f', 'o', 'o', 0x07, 'e', 'x', 'a', 'm', 'p', 'l', 'e', 0x03, 'c', 'o', 'm', 0x00,
						0x03, 'b', 'a', 'r', 0x00, 0x00,
					}

					binary.BigEndian.PutUint16(chain[len(chain)-2:], uint16(4^labelPointerShift))

					chain = append(chain, 0x00, 0x00)

					binary.BigEndian.PutUint16(chain[len(chain)-2:], uint16(12^labelPointerShift))

					return chain
				},
				name: "baz.example.com",
			},
			out: func() []byte {
				chain := []byte{
					0x03, 'f', 'o', 'o', 0x07, 'e', 'x', 'a', 'm', 'p', 'l', 'e', 0x03, 'c', 'o', 'm', 0x00,
					0x03, 'b', 'a', 'r', 0x00, 0x00,
				}

				binary.BigEndian.PutUint16(chain[len(chain)-2:], uint16(4^labelPointerShift))

				chain = append(chain, 0x00, 0x00)

				binary.BigEndian.PutUint16(chain[len(chain)-2:], uint16(12^labelPointerShift))

				chain = append(chain, 0x03, 'b', 'a', 'z', 0x00, 0x00)

				binary.BigEndian.PutUint16(chain[len(chain)-2:], uint16(4^labelPointerShift))

				chain = append(chain, 0x00, 0x00)

				binary.BigEndian.PutUint16(chain[len(chain)-2:], uint16(12^labelPointerShift))

				return append(chain, 0x00)
			},
		},
		"name already exists": {
			in: struct {
				generateChain func() []byte
				name          string
			}{
				generateChain: func() []byte {
					return []byte{
						0x07, 'e', 'x', 'a', 'm', 'p', 'l', 'e', 0x03, 'c', 'o', 'm', 0x00,
					}
				},
				name: "example.com",
			},
			out: func() []byte {
				return []byte{
					0x07, 'e', 'x', 'a', 'm', 'p', 'l', 'e', 0x03, 'c', 'o', 'm', 0x00,
				}
			},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			s := newSession(&net.UDPAddr{IP: net.ParseIP("10.0.0.1"), Port: 53})

			s.currentChain = tc.in.generateChain()

			err := s.StoreName(tc.in.name)
			if err != nil {
				t.Fatal(err)
			}

			assert.Equal(t, tc.out(), s.currentChain)
		})
	}
}

func TestSession_NameAlreadyQueried(t *testing.T) {
	testcases := map[string]struct {
		in struct {
			storeCount int
			name       string
		}
		out bool
	}{
		"no chain": {
			in: struct {
				storeCount int
				name       string
			}{
				storeCount: 0,
				name:       "example.com",
			},
			out: false,
		},
		"once": {
			in: struct {
				storeCount int
				name       string
			}{
				storeCount: 1,
				name:       "example.com",
			},
			out: true,
		},
		"twice": {
			in: struct {
				storeCount int
				name       string
			}{
				storeCount: 2,
				name:       "example.com",
			},
			out: true,
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			s := newSession(&net.UDPAddr{IP: net.ParseIP("10.0.0.1"), Port: 53})

			for i := 0; i < tc.in.storeCount; i++ {
				s.StoreName(tc.in.name)
			}

			queried, err := s.NameAlreadyQueried(tc.in.name)
			if err != nil {
				t.Fatal(err)
			}

			assert.Equal(t, queried, tc.out)
		})
	}
}

func TestSession_Expired(t *testing.T) {
	testcases := map[string]struct {
		in struct {
			createdAt  time.Time
			timePassed time.Duration
		}
		out bool
	}{
		"still valid": {
			in: struct {
				createdAt  time.Time
				timePassed time.Duration
			}{
				createdAt:  time.Date(2025, time.January, 1, 1, 1, 1, 1, time.UTC),
				timePassed: time.Second,
			},
			out: false,
		},
		"expired": {
			in: struct {
				createdAt  time.Time
				timePassed time.Duration
			}{
				createdAt:  time.Date(2025, time.January, 1, 1, 1, 1, 1, time.UTC),
				timePassed: time.Minute,
			},
			out: true,
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			s := newSession(&net.UDPAddr{IP: net.ParseIP("10.0.0.1"), Port: 53})
			s.createdAt = tc.in.createdAt

			timePassed := tc.in.createdAt.Add(tc.in.timePassed)

			assert.Equal(t, tc.out, s.Expired(timePassed))
		})
	}
}
