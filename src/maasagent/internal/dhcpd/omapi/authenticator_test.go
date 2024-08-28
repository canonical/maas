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

func TestHMACMD5AuthenticatorSign(t *testing.T) {
	secret := "a2V5" // "key" in base64

	testcases := map[string]struct {
		in  []byte
		out []byte
	}{
		"empty": {
			in: []byte{},
			out: []byte{
				0x63, 0x53, 0x04, 0x68, 0xa0, 0x4e, 0x38, 0x64,
				0x59, 0x85, 0x5d, 0xa0, 0x06, 0x3b, 0x65, 0x96,
			},
		},
		"nil": {
			out: []byte{
				0x63, 0x53, 0x04, 0x68, 0xa0, 0x4e, 0x38, 0x64,
				0x59, 0x85, 0x5d, 0xa0, 0x06, 0x3b, 0x65, 0x96,
			},
		},
		"message": {
			in: []byte{
				// hello world
				0x68, 0x65, 0x6c, 0x6c, 0x6f, 0x20, 0x77, 0x6f, 0x72, 0x6c, 0x64,
			},
			out: []byte{
				0xae, 0x92, 0xcf, 0x51, 0xad, 0xf9, 0x11, 0x30,
				0x13, 0x0a, 0xef, 0xc2, 0xb3, 0x9a, 0x75, 0x95,
			},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			auth := NewHMACMD5Authenticator("test", secret)

			sig := auth.Sign(tc.in)
			assert.Equal(t, sig, tc.out)
		})
	}
}
