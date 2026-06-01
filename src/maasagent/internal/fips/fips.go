// Copyright (c) 2026 Canonical Ltd
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

package fips

import (
	"os"
	"strings"
	"sync"
)

// fipsEnabledPath is the path to the FIPS mode indicator file.
// It is a variable (not const) to allow override in tests.
var fipsEnabledPath = "/proc/sys/crypto/fips_enabled"

var (
	once    sync.Once
	enabled bool
)

// IsEnabled returns true if FIPS mode is active on this host.
// The result is cached after the first call.
func IsEnabled() bool {
	once.Do(func() {
		enabled = readFIPSEnabled()
	})

	return enabled
}

func readFIPSEnabled() bool {
	data, err := os.ReadFile(fipsEnabledPath)
	if err != nil {
		return false
	}

	return strings.TrimSpace(string(data)) == "1"
}
