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
	"crypto/hmac"
	//nolint:gosec // gosec flags MD5 as weak crypto, but it is required for omapi
	"crypto/md5"
	"errors"
	"hash"
)

var (
	ErrInvalidAuthType = errors.New("invalid authentication type")
	ErrNoAuth          = errors.New("the given message is not authenticated properly")
)

var (
	authenticatorFactory func(string) Authenticator
)

type Authenticator interface {
	Sign(msg []byte) (string, error)
	Obj() MessageMap
}

func NewAuthenticator(secret string) Authenticator {
	if authenticatorFactory != nil {
		return authenticatorFactory(secret)
	}

	return NewHMACMD5Authenticator("omapi_key", secret)
}

type NoopAuthenticator struct{}

func (n *NoopAuthenticator) Sign(msg []byte) (string, error) {
	return "", nil
}

func (n *NoopAuthenticator) Obj() MessageMap {
	return make(MessageMap)
}

func NewNoopAuthenticator(secret string) Authenticator {
	return &NoopAuthenticator{}
}

type HMACMD5Authenticator struct {
	obj    MessageMap
	hasher hash.Hash
	secret string
}

func NewHMACMD5Authenticator(name string, secret string) Authenticator {
	obj := make(MessageMap)

	//nolint:errcheck,gosec //these strings will always succeed, no need to complicate constructor with error handling
	obj.SetValue("algorithm", "HMAC-MD5.SIG-ALG.REG.INT.")
	//nolint:errcheck,gosec //these strings will always succeed, no need to complicate constructor with error handling
	obj.SetValue("name", name)

	hasher := hmac.New(md5.New, []byte(secret))

	return &HMACMD5Authenticator{
		secret: secret,
		obj:    obj,
		hasher: hasher,
	}
}

func (h *HMACMD5Authenticator) Sign(msg []byte) (string, error) {
	b := h.hasher.Sum(msg)
	return string(b), nil
}

func (h *HMACMD5Authenticator) Obj() MessageMap {
	return h.obj
}
