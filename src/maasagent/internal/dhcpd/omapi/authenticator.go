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
	"encoding/base64"

	//nolint:gosec // gosec flags MD5 as weak crypto, but it is required for omapi
	"crypto/md5"
	"hash"
)

type HMACMD5Authenticator struct {
	hasher hash.Hash
	object map[string][]byte
	authID uint32
}

func NewHMACMD5Authenticator(name string, secret string) HMACMD5Authenticator {
	object := make(map[string][]byte)

	object["algorithm"] = []byte("hmac-md5.SIG-ALG.REG.INT.")
	object["name"] = []byte(name)

	key, err := base64.StdEncoding.DecodeString(secret)
	if err != nil {
		panic(err)
	}

	return HMACMD5Authenticator{
		object: object,
		hasher: hmac.New(md5.New, key),
	}
}

func (h *HMACMD5Authenticator) AuthLen() uint32 {
	return 16
}

func (h *HMACMD5Authenticator) Sign(data []byte) []byte {
	h.hasher.Write(data)
	signature := h.hasher.Sum(nil)
	defer h.hasher.Reset()

	return signature
}

func (h *HMACMD5Authenticator) Object() map[string][]byte {
	return h.object
}

func (h *HMACMD5Authenticator) AuthID() uint32 {
	return h.authID
}

func (h *HMACMD5Authenticator) SetAuthID(i uint32) {
	h.authID = i
}
