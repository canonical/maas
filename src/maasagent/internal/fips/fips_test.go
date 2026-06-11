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
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestReadFIPSEnabledTrue(t *testing.T) {
	f, err := os.CreateTemp(".", "fips_enabled_*")
	assert.NoError(t, err)

	defer os.Remove(f.Name())

	_, err = f.WriteString("1\n")
	assert.NoError(t, err)
	assert.NoError(t, f.Close())

	orig := fipsEnabledPath
	fipsEnabledPath = f.Name()

	defer func() { fipsEnabledPath = orig }()

	assert.True(t, readFIPSEnabled())
}

func TestReadFIPSEnabledFalse(t *testing.T) {
	f, err := os.CreateTemp(".", "fips_enabled_*")
	assert.NoError(t, err)

	defer os.Remove(f.Name())

	_, err = f.WriteString("0\n")
	assert.NoError(t, err)
	assert.NoError(t, f.Close())

	orig := fipsEnabledPath
	fipsEnabledPath = f.Name()

	defer func() { fipsEnabledPath = orig }()

	assert.False(t, readFIPSEnabled())
}

func TestReadFIPSEnabledMissingFile(t *testing.T) {
	orig := fipsEnabledPath
	fipsEnabledPath = "./nonexistent_fips_enabled_test_12345"

	defer func() { fipsEnabledPath = orig }()

	assert.False(t, readFIPSEnabled())
}
