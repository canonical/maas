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
	"crypto/sha256"
	"encoding/base64"
	"hash"
)

type HMACSHA256Authenticator struct {
	hasher hash.Hash
	object map[string][]byte
	authID uint32
}

func NewHMACSHA256Authenticator(name string, secret string) HMACSHA256Authenticator {
	object := make(map[string][]byte)

	object["algorithm"] = []byte("hmac-sha256.SIG-ALG.REG.INT.")
	object["name"] = []byte(name)

	key, err := base64.StdEncoding.DecodeString(secret)
	if err != nil {
		panic(err)
	}

	return HMACSHA256Authenticator{
		object: object,
		hasher: hmac.New(sha256.New, key),
	}
}

func (h *HMACSHA256Authenticator) AuthLen() uint32 {
	return 32
}

func (h *HMACSHA256Authenticator) Sign(data []byte) []byte {
	h.hasher.Write(data)
	signature := h.hasher.Sum(nil)
	defer h.hasher.Reset()

	return signature
}

func (h *HMACSHA256Authenticator) Object() map[string][]byte {
	return h.object
}

func (h *HMACSHA256Authenticator) AuthID() uint32 {
	return h.authID
}

func (h *HMACSHA256Authenticator) SetAuthID(i uint32) {
	h.authID = i
}
