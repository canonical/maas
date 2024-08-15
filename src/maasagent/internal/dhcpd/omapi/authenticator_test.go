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
	testSecret := "5k7gI3x06DDQHi+bXRHNQaEV/cfwO67L/f0rRzZf6OOq0lBl4DAB2fpxTkHoQYbw0modTIwsxmtbrMzlb4BouA=="

	table := map[string]struct {
		In  []byte
		Out string
	}{
		"empty": {
			In:  []byte{},
			Out: "\xddmOj\x9d\xbea\xc2Ϳ\xb5\x02\xf4\x10v\x7f",
		},
		"nil": {
			Out: "\xddmOj\x9d\xbea\xc2Ϳ\xb5\x02\xf4\x10v\x7f",
		},
		"message": {
			In: []byte{
				0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0,
				0x1, 0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0, 0x1, 0x0, 0x4,
				0x74, 0x79, 0x70, 0x65, 0x0, 0x0, 0x0, 0x4, 0x68, 0x6f,
				0x73, 0x74, 0x0, 0x0, 0x0, 0x2, 0x69, 0x70, 0x0, 0x0,
				0x0, 0x8, 0x31, 0x30, 0x2e, 0x30, 0x2e, 0x30, 0x2e,
				0x31, 0x0, 0x0,
			},
			Out: "\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x04type\x00\x00\x00\x04host\x00\x00\x00\x02ip\x00\x00\x00\b10.0.0.1\x00\x00\xddmOj\x9d\xbea\xc2Ϳ\xb5\x02\xf4\x10v\x7f",
		},
	}

	for tname, tcase := range table {
		t.Run(tname, func(tt *testing.T) {
			auth := NewHMACMD5Authenticator("test", testSecret)

			sig, err := auth.Sign(tcase.In)
			if err != nil {
				tt.Fatal(err)
			}

			assert.Equal(tt, sig, tcase.Out)
		})
	}
}
