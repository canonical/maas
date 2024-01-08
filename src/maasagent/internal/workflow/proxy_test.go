package workflow

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestGetSocketPath(t *testing.T) {
	testcases := map[string]struct {
		in  func(t *testing.T)
		out string
	}{
		"snap": {
			in: func(t *testing.T) {
				t.Setenv("SNAP", "/snap/maas/x1")
				t.Setenv("SNAP_DATA", "/var/snap/maas/x1")
			},
			out: "/var/snap/maas/x1/agent-http-proxy.sock",
		},
		"deb": {
			in: func(t *testing.T) {
				t.Setenv("SNAP", "")
			}, out: "/var/lib/maas/agent-http-proxy.sock",
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			tc.in(t)
			res := getSocketFilePath()
			assert.Equal(t, tc.out, res)
		})
	}
}
