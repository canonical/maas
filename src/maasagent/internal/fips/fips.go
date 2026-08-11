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

// Package fips provides FIPS mode detection for the MAAS agent.
package fips

import (
	"log/slog"
	"os"
	"strings"
	"sync"
)

// procPath is the kernel FIPS state file. Overridable in tests.
var procPath = "/proc/sys/crypto/fips_enabled"

var (
	once    sync.Once
	enabled bool
)

// IsEnabled reports whether the host kernel has FIPS mode enabled.
// The result is determined once and cached for the process lifetime.
func IsEnabled(l *slog.Logger) bool {
	once.Do(func() {
		enabled = detect(l, procPath)
	})

	return enabled
}

// detect reads the FIPS state from path and emits a structured log entry.
func detect(l *slog.Logger, path string) bool {
	if l == nil {
		l = slog.Default()
	}

	//nolint:gosec // path is a hardcoded procfs file, not user input.
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			l.Info("fips_mode_detected",
				slog.Bool("fips_mode", false),
				slog.String("source", "file_missing"))

			return false
		}

		l.Warn("fips_mode_unreadable",
			slog.Any("error", err),
			slog.Bool("fips_mode", false))

		return false
	}

	active := strings.TrimSpace(string(data)) == "1"

	l.Info("fips_mode_detected",
		slog.Bool("fips_mode", active),
		slog.String("source", path))

	return active
}
