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
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestHMACSHA256AuthenticatorSign(t *testing.T) {
	secret := "a2V5" // "key" in base64
	key, err := base64.StdEncoding.DecodeString(secret)
	assert.NoError(t, err)

	testcases := map[string]struct {
		in []byte
	}{
		"empty": {
			in: []byte{},
		},
		"nil": {},
		"message": {
			in: []byte{
				// hello world
				0x68, 0x65, 0x6c, 0x6c, 0x6f, 0x20, 0x77, 0x6f, 0x72, 0x6c, 0x64,
			},
		},
	}

	expectedSignature := func(data []byte) []byte {
		hasher := hmac.New(sha256.New, key)
		hasher.Write(data)

		return hasher.Sum(nil)
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			auth := NewHMACSHA256Authenticator("test", secret)

			assert.Equal(t, expectedSignature(tc.in), auth.Sign(tc.in))
		})
	}
}

func TestHMACSHA256AuthenticatorAlgorithmTSIG(t *testing.T) {
	auth := NewHMACSHA256Authenticator("test", "a2V5")

	assert.Equal(t, uint32(sha256.Size), auth.AuthLen())
	assert.Equal(t, []byte("hmac-sha256.SIG-ALG.REG.INT."), auth.Object()["algorithm"])
}
