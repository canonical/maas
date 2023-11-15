package workflow

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestFmtPowerOpts(t *testing.T) {
	testcases := map[string]struct {
		in  map[string]interface{}
		out []string
	}{
		"single numeric argument": {
			in:  map[string]interface{}{"key1": 1},
			out: []string{"--key1", "1"},
		},
		"single string argument": {
			in:  map[string]interface{}{"key1": "value1"},
			out: []string{"--key1", "value1"},
		},
		"multiple string arguments": {
			in:  map[string]interface{}{"key1": "value1", "key2": "value2"},
			out: []string{"--key1", "value1", "--key2", "value2"},
		},
		"multi choice string argument": {
			in:  map[string]interface{}{"key1": []string{"value1", "value2"}},
			out: []string{"--key1", "value1", "--key1", "value2"},
		},
		"argument value with line breaks": {
			in:  map[string]interface{}{"key1": "multi\nline\nstring"},
			out: []string{"--key1", "multi\nline\nstring"},
		},
		"ignore system_id": {
			in:  map[string]interface{}{"system_id": "value1"},
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
