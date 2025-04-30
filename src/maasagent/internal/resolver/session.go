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
	"errors"
	"net"
	"sync"
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
	chain []byte
}

// newSession creates a *session to track query chains for
// a given remote address
func newSession(remoteAddr net.Addr) *session {
	return &session{
		remoteAddr: remoteAddr,
		chain:      []byte{},
		createdAt:  time.Now(),
	}
}

// sessionKeyFromRemoteAddr creates the key to create or fetch
// a session on. Scheme is used as tcp or udp from the same IP
// should be considered separate sessions
func sessionKeyFromRemoteAddr(a net.Addr) string {
	return a.Network() + "://" + a.String()
}

// String returns the key of a session
func (s *session) String() string {
	if s.remoteAddr == nil {
		return ""
	}

	return sessionKeyFromRemoteAddr(s.remoteAddr)
}

type name struct {
	compressed, uncompressed []byte
}

// add stores a name just queried in the query chain
func (s *session) add(name name) {
	if !s.contains(name) {
		s.chain = append(s.chain, name.compressed...)
	}
}

// reset clears the current query chain.
// This should happen whenever a non-CNAME and non-DNAME is returned
func (s *session) reset() {
	s.chain = nil
}

// expired calculates if a session has expired
func (s *session) expired(ts time.Time) bool {
	return ts.Sub(s.createdAt) >= sessionTTL
}

// contains checks if either a compressed or uncompressed version of a given name
// is present in the current query chain
func (s *session) contains(name name) bool {
	n := len(s.chain)
	if n == 0 {
		return false
	}

	cLen := len(name.compressed)
	uLen := len(name.uncompressed)

	// Check if we have name at the start of the chain.
	// We need to check both compressed and uncompressed variants.
	if cLen <= n && bytes.Equal(s.chain[:cLen], name.compressed) {
		return true
	}

	if uLen <= n && bytes.Equal(s.chain[:uLen], name.uncompressed) {
		return true
	}

	// Multiple names in the chain are separated by 0x00 byte (denotes the end of
	// the previous name) hence we also check occurrence after each 0x00
	for i := range n {
		if s.chain[i] != 0x00 {
			continue
		}

		if cLen+i <= n && bytes.Equal(s.chain[i:i+cLen], name.compressed) {
			return true
		}

		if uLen+i <= n && bytes.Equal(s.chain[i:i+uLen], name.uncompressed) {
			return true
		}
	}

	return false
}

// compress compressed a given name using the current query chain as a buffer
func (s *session) compress(compressed *[]byte, label []byte) bool {
	idx := bytes.Index(s.chain, label)
	if idx == -1 {
		return false
	}

	compressedCap := cap(*compressed)
	compressedLen := len(*compressed)

	// Ensure compressed has enough capacity to append 2 bytes
	if compressedCap >= compressedLen+2 {
		// Reuse the existing capacity
		*compressed = (*compressed)[:compressedLen+2]
	} else {
		// Allocate a new slice with extra space and copy the data
		buf := make([]byte, compressedLen+2, compressedCap+2)
		copy(buf, *compressed)
		*compressed = buf
	}

	//nolint:gosec // G115 compression as in RFC1035
	v := uint16(idx ^ labelPointerShift)
	(*compressed)[compressedLen] = byte(v >> 8)
	(*compressed)[compressedLen+1] = byte(v)

	return true
}

// format returns a name that has compressed and uncompressed format
// It can return ErrLabelTooLong if label length > 63.
func (s *session) format(nameStr string) (name, error) {
	nameStr = dns.Fqdn(nameStr)
	nameStrLen := len(nameStr)

	compressed := make([]byte, 0, 256)
	uncompressed := make([]byte, 0, 256)

	start := 0
	wire := make([]byte, 1+63) // max label length is 63 bytes.

	// Iterate over name (www.example.com.) and execute logic for each label.
	for i := 0; i <= nameStrLen; i++ {
		// strings.Split() could be more readable here, but it brings an allocation.
		if i == nameStrLen || nameStr[i] == '.' {
			label := nameStr[start:i]
			labelLen := len(label)
			start = i + 1

			if len(label) > 63 {
				return name{}, ErrLabelTooLong
			}

			wire[0] = byte(labelLen)
			copy(wire[1:], label)
			uncompressed = append(uncompressed, wire[:1+labelLen]...)

			if len(label) > 0 {
				if ok := s.compress(&compressed, wire[:1+labelLen]); ok {
					continue
				}
			}

			compressed = append(compressed, wire[:1+labelLen]...)
		}
	}

	return name{compressed: compressed, uncompressed: uncompressed}, nil
}

type sessions struct {
	m    map[string]*session
	lock sync.RWMutex
}

// Load loads an existing session
func (s *sessions) Load(key string) *session {
	s.lock.RLock()
	defer s.lock.RUnlock()

	return s.m[key]
}

// Store stores a session
func (s *sessions) Store(key string, sess *session) {
	s.lock.Lock()
	defer s.lock.Unlock()

	s.m[key] = sess
}

// Delete deletes a session
func (s *sessions) Delete(key string) {
	s.lock.Lock()
	defer s.lock.Unlock()

	delete(s.m, key)
}

// ClearExpired removes all expired sessions
func (s *sessions) ClearExpired() {
	now := time.Now()

	s.lock.Lock()
	defer s.lock.Unlock()

	for k, v := range s.m {
		if v.expired(now) {
			delete(s.m, k)
		}
	}
}
