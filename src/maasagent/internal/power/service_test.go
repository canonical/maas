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

package power

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestFmtPowerOpts(t *testing.T) {
	testcases := map[string]struct {
		in  map[string]any
		out []string
	}{
		"single numeric argument": {
			in:  map[string]any{"key1": 1},
			out: []string{"--key1", "1"},
		},
		"single string argument": {
			in:  map[string]any{"key1": "value1"},
			out: []string{"--key1", "value1"},
		},
		"multiple string arguments": {
			in:  map[string]any{"key1": "value1", "key2": "value2"},
			out: []string{"--key1", "value1", "--key2", "value2"},
		},
		"multi choice string argument": {
			in:  map[string]any{"key1": []string{"value1", "value2"}},
			out: []string{"--key1", "value1", "--key1", "value2"},
		},
		"argument value with line breaks": {
			in:  map[string]any{"key1": "multi\nline\nstring"},
			out: []string{"--key1", "multi\nline\nstring"},
		},
		"ignore system_id": {
			in:  map[string]any{"system_id": "value1"},
			out: []string{},
		},
		"ignore null": {
			in:  map[string]any{"key1": nil},
			out: []string{},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			res := fmtPowerOpts(tc.in)
			assert.ElementsMatch(t, tc.out, res)
		})
	}
}
