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

func TestDataPath(t *testing.T) {
	testcases := map[string]struct {
		setup func(t *testing.T)
		in    string
		out   string
	}{
		"snap": {
			setup: func(t *testing.T) {
				t.Setenv("SNAP_COMMON", "/var/snap/maas/common")
			},
			in:  "foo",
			out: "/var/snap/maas/common/var/lib/maas/foo",
		},
		"deb": {
			setup: func(t *testing.T) {
				t.Setenv("SNAP_COMMON", "")
			},
			in:  "foo",
			out: "/var/lib/maas/foo",
		},
		"clean input path": {
			setup: func(t *testing.T) {
				t.Setenv("SNAP_COMMON", "")
			},
			in:  "bar/../baz",
			out: "/var/lib/maas/baz",
		},
	}

	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			tc.setup(t)
			assert.Equal(t, tc.out, DataPath(tc.in))
		})
	}
}

func TestDataDir(t *testing.T) {
	t.Run("snap", func(t *testing.T) {
		t.Setenv("SNAP_COMMON", "/var/snap/maas/common")
		assert.Equal(t, "/var/snap/maas/common/var/lib/maas", DataDir())
	})

	t.Run("deb", func(t *testing.T) {
		t.Setenv("SNAP_COMMON", "")
		assert.Equal(t, "/var/lib/maas", DataDir())
	})
}

func TestConfigPath(t *testing.T) {
	testcases := map[string]struct {
		setup func(t *testing.T)
		in    string
		out   string
	}{
		"snap": {
			setup: func(t *testing.T) { t.Setenv("SNAP_COMMON", "/var/snap/maas/common") },
			in:    "conf",
			out:   "/var/snap/maas/common/etc/maas/conf",
		},
		"deb": {
			setup: func(t *testing.T) { t.Setenv("SNAP_COMMON", "") },
			in:    "conf",
			out:   "/etc/maas/conf",
		},
	}

	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			tc.setup(t)
			assert.Equal(t, tc.out, ConfigPath(tc.in))
		})
	}
}

func TestConfigDir(t *testing.T) {
	t.Run("snap", func(t *testing.T) {
		t.Setenv("SNAP_COMMON", "/var/snap/maas/common")
		assert.Equal(t, "/var/snap/maas/common/etc/maas", ConfigDir())
	})

	t.Run("deb", func(t *testing.T) {
		t.Setenv("SNAP_COMMON", "")
		assert.Equal(t, "/etc/maas", ConfigDir())
	})
}

func TestRunDir(t *testing.T) {
	testcases := map[string]struct {
		setup func(t *testing.T)
		out   string
	}{
		"snap": {
			setup: func(t *testing.T) {
				t.Setenv("SNAP_INSTANCE_NAME", "maas")
			},
			out: "/run/snap.maas",
		},
		"deb": {
			setup: func(t *testing.T) {
				t.Setenv("SNAP_INSTANCE_NAME", "")
			},
			out: "/run/maas",
		},
	}

	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			tc.setup(t)
			assert.Equal(t, tc.out, RunDir())
		})
	}
}

func TestCachePath(t *testing.T) {
	testcases := map[string]struct {
		setup func(t *testing.T)
		in    string
		out   string
	}{
		"snap": {
			setup: func(t *testing.T) { t.Setenv("SNAP_COMMON", "/var/snap/maas/common") },
			in:    "cachefile",
			out:   "/var/snap/maas/common/var/cache/maas/cachefile",
		},
		"deb": {
			setup: func(t *testing.T) { t.Setenv("SNAP_COMMON", "") },
			in:    "cachefile",
			out:   "/var/cache/maas/cachefile",
		},
	}

	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			tc.setup(t)
			assert.Equal(t, tc.out, CachePath(tc.in))
		})
	}
}

func TestCacheDir(t *testing.T) {
	t.Run("snap", func(t *testing.T) {
		t.Setenv("SNAP_COMMON", "/var/snap/maas/common")
		assert.Equal(t, "/var/snap/maas/common/var/cache/maas", CacheDir())
	})

	t.Run("deb", func(t *testing.T) {
		t.Setenv("SNAP_COMMON", "")
		assert.Equal(t, "/var/cache/maas", CacheDir())
	})
}

func TestMAASDataPath(t *testing.T) {
	testcases := map[string]struct {
		setup func(t *testing.T)
		in    string
		out   string
	}{
		"env set": {
			setup: func(t *testing.T) {
				t.Setenv("MAAS_DATA", "/custom/maas")
			},
			in:  "foo",
			out: "/custom/maas/foo",
		},
		"env empty": {
			setup: func(t *testing.T) {
				t.Setenv("MAAS_DATA", "")
			},
			in:  "foo",
			out: "/var/lib/maas/foo",
		},
	}

	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			tc.setup(t)
			assert.Equal(t, tc.out, MAASDataPath(tc.in))
		})
	}
}
