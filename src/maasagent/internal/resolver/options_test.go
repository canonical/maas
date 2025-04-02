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
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestWithConnPoolSize(t *testing.T) {
	testcases := map[string]struct {
		in  int
		out int
	}{
		"value provided": {
			in:  100,
			out: 100,
		},
		"zero uses default value": {
			in:  0,
			out: defaultConnPoolSize,
		},
	}

	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			handler := NewRecursiveHandler(noopCache{}, WithConnPoolSize(tc.in))

			assert.Equal(t, tc.out, handler.connPoolSize)
		})
	}
}
