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
	"path/filepath"
	"sync"
	"testing"

	"github.com/stretchr/testify/assert"
)

// resetOnce replaces the package-level Once so IsEnabled() can be retested.
func resetOnce() {
	once = sync.Once{}
	enabled = false
}

func writeFIPSFile(t *testing.T, value string) string {
	t.Helper()

	dir := t.TempDir()
	p := filepath.Join(dir, "fips_enabled")

	if err := os.WriteFile(p, []byte(value), 0o644); err != nil {
		t.Fatalf("write fips file: %v", err)
	}

	return p
}

func TestDetect_FileMissing(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "fips_enabled")
	result := detect(path)

	assert.False(t, result)
}

func TestDetect_FileZero(t *testing.T) {
	path := writeFIPSFile(t, "0\n")
	result := detect(path)

	assert.False(t, result)
}

func TestDetect_FileOne(t *testing.T) {
	path := writeFIPSFile(t, "1\n")
	result := detect(path)

	assert.True(t, result)
}

func TestDetect_FileOneNoNewline(t *testing.T) {
	path := writeFIPSFile(t, "1")
	result := detect(path)

	assert.True(t, result)
}

func TestDetect_PermissionError(t *testing.T) {
	path := writeFIPSFile(t, "1")

	if err := os.Chmod(path, 0o000); err != nil {
		t.Skip("cannot set unreadable permissions")
	}

	t.Cleanup(func() { _ = os.Chmod(path, 0o644) })

	result := detect(path)

	assert.False(t, result)
}

func TestIsEnabled_CachesResult(t *testing.T) {
	resetOnce()
	t.Cleanup(resetOnce)

	procPath = writeFIPSFile(t, "1")

	first := IsEnabled()
	second := IsEnabled()

	assert.True(t, first)
	assert.Equal(t, first, second)
}

func TestIsEnabled_NonFIPS(t *testing.T) {
	resetOnce()
	t.Cleanup(resetOnce)

	dir := t.TempDir()
	procPath = filepath.Join(dir, "missing")

	assert.False(t, IsEnabled())
}
