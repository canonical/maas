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
	"bytes"
	"encoding/binary"
	"errors"
	"net"
	"strings"
	"time"

	"github.com/miekg/dns"
)

const (
	labelPointerShift = 0xC000
	sessionTTL        = time.Minute
)

var (
	ErrLabelTooLong = errors.New("label too long")
	ErrCNAMELoop    = errors.New("a loop in CNAME resolution was detected")
)

type session struct {
	createdAt  time.Time
	remoteAddr net.Addr
	// chains can be extremely long and still valid,
	// we rely on label compression to reuse space
	// where labels in a name repeats
	currentChain []byte
}

func newSession(remoteAddr net.Addr) *session {
	return &session{
		remoteAddr:   remoteAddr,
		currentChain: []byte{},
		createdAt:    time.Now(),
	}
}

func sessionKeyFromRemoteAddr(a net.Addr) string {
	return a.Network() + "://" + a.String()
}

func (s *session) String() string {
	if s.remoteAddr == nil {
		return ""
	}

	return sessionKeyFromRemoteAddr(s.remoteAddr)
}

func (s *session) StoreName(name string) error {
	var nameBytes, uncompressed []byte

	name = dns.Fqdn(name)
	labels := strings.Split(name, ".")

	for _, label := range labels {
		wire, err := s.labelToWire(label)
		if err != nil {
			return err
		}

		uncompressed = append(uncompressed, wire...)

		if label != "" { // end of fqdn
			compressed, ok := s.compress(nameBytes, wire)
			if ok {
				nameBytes = compressed

				continue
			}
		}

		nameBytes = append(nameBytes, wire...)
	}

	if !s.contains(nameBytes, uncompressed) {
		s.currentChain = append(s.currentChain, nameBytes...)
	}

	return nil
}

func (s *session) NameAlreadyQueried(name string) (bool, error) {
	if len(s.currentChain) == 0 {
		return false, nil
	}

	name = dns.Fqdn(name)

	var (
		nameBytes    []byte
		uncompressed []byte
	)

	labels := strings.Split(name, ".")

	for _, label := range labels {
		wire, err := s.labelToWire(label)
		if err != nil {
			return false, err
		}

		uncompressed = append(uncompressed, wire...)

		if label != "" {
			compressed, ok := s.compress(nameBytes, wire)
			if ok {
				nameBytes = compressed

				continue
			}
		}

		nameBytes = append(nameBytes, wire...)
	}

	return s.contains(nameBytes, uncompressed), nil
}

func (s *session) Reset() {
	s.currentChain = nil
}

func (s *session) Expired(ts time.Time) bool {
	return ts.Sub(s.createdAt) >= sessionTTL
}

func (s *session) contains(compressed []byte, uncompressed []byte) bool {
	compressedIdx := bytes.Index(s.currentChain, compressed)
	uncompressedIdx := bytes.Index(s.currentChain, uncompressed)
	compressedMatch := bytes.Contains(
		s.currentChain, append([]byte{0x00}, compressed...), // 0 byte of previous name to ensure exact match
	)
	uncompressedMatch := bytes.Contains(
		s.currentChain, append([]byte{0x00}, uncompressed...), // 0 byte of previous name to ensure exact match
	)

	return compressedIdx == 0 || uncompressedIdx == 0 || compressedMatch || uncompressedMatch
}

func (s *session) compress(buf []byte, label []byte) ([]byte, bool) {
	idx := bytes.Index(s.currentChain, label)
	if idx == -1 {
		return buf, false
	}

	b := make([]byte, len(buf)+2)
	copy(b, buf)
	//nolint:gosec // compression requires uint16. https://datatracker.ietf.org/doc/html/rfc1035
	binary.BigEndian.PutUint16(b[len(buf):], uint16(idx^labelPointerShift))

	return b, true
}

func (s *session) labelToWire(label string) ([]byte, error) {
	bytesLabel := []byte(label)

	labelLen := len(bytesLabel)
	if labelLen > 63 {
		return nil, ErrLabelTooLong
	}

	length := uint8(labelLen)

	return append([]byte{length}, bytesLabel...), nil
}
