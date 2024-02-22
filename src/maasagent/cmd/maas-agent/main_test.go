package main

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestGetSocketDir(t *testing.T) {
	testcases := map[string]struct {
		in  func(t *testing.T)
		out string
	}{
		"snap": {
			in: func(t *testing.T) {
				t.Setenv("SNAP_INSTANCE_NAME", "maas")
			},
			out: "/run/snap.maas",
		},
		"deb": {
			in: func(t *testing.T) {
				t.Setenv("SNAP_INSTANCE_NAME", "")
			}, out: "/run/maas/agent",
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			tc.in(t)
			res := getSocketDir()
			assert.Equal(t, tc.out, res)
		})
	}
}
