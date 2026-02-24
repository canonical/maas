// Copyright (c) 2023-2026 Canonical Ltd
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
	"fmt"
	"os"
	"path/filepath"
)

const (
	defaultDataDir   = "/var/lib/maas"
	defaultConfigDir = "/etc/maas"
	defaultCacheDir  = "/var/cache/maas"
	defaultRunDir    = "/run/maas"
)

// DataPath returns the MAAS data path (snap or deb) with the given relative path appended.
func DataPath(path string) string {
	base := defaultDataDir
	if dataDir := os.Getenv("SNAP_COMMON"); dataDir != "" {
		base = filepath.Join(filepath.Clean(dataDir), defaultDataDir)
	}

	return filepath.Join(base, path)
}

// DataDir returns the root MAAS data directory (snap or deb).
func DataDir() string {
	return DataPath("")
}

// ConfigPath returns the MAAS config path (snap or deb) with the given relative path appended.
func ConfigPath(path string) string {
	path = filepath.Clean(path)

	base := defaultConfigDir
	if dataDir := os.Getenv("SNAP_COMMON"); dataDir != "" {
		base = filepath.Join(filepath.Clean(dataDir), defaultConfigDir)
	}

	return filepath.Join(base, path)
}

// ConfigDir returns the root MAAS config directory (snap or deb).
func ConfigDir() string {
	return ConfigPath("")
}

// RunDir returns the MAAS runtime directory (snap or deb).
func RunDir() string {
	if name := os.Getenv("SNAP_INSTANCE_NAME"); name != "" {
		return fmt.Sprintf("/run/snap.%s", name)
	}

	return defaultRunDir
}

// CachePath returns the MAAS cache path (snap or deb) with the given relative path appended.
func CachePath(path string) string {
	path = filepath.Clean(path)

	base := defaultCacheDir
	if dataDir := os.Getenv("SNAP_COMMON"); dataDir != "" {
		base = filepath.Join(filepath.Clean(dataDir), defaultCacheDir)
	}

	return filepath.Join(base, path)
}

// CacheDir returns the root MAAS cache directory (snap or deb).
func CacheDir() string {
	return CachePath("")
}

// MAASDataPath returns MAAS_DATA (if set) or the default MAAS data path.
//
// Deprecated: Use DataPath instead.
func MAASDataPath(path string) string {
	path = filepath.Clean(path)

	if maasDir := os.Getenv("MAAS_DATA"); maasDir != "" {
		return filepath.Join(filepath.Clean(maasDir), path)
	}

	return filepath.Join(defaultDataDir, path)
}
