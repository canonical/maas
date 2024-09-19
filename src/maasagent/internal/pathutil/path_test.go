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

package pathutil

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestGetDataPath(t *testing.T) {
	testcases := map[string]struct {
		in  func(t *testing.T)
		out string
	}{
		"snap": {
			in: func(t *testing.T) {
				t.Setenv("SNAP_DATA", "/var/snap/maas/x1")
			},
			out: "/var/snap/maas/x1/foo",
		},
		"deb": {
			in: func(t *testing.T) {
				t.Setenv("SNAP_DATA", "")
			}, out: "/var/lib/maas/foo",
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			tc.in(t)

			res := GetDataPath("foo")
			assert.Equal(t, tc.out, res)
		})
	}
}
