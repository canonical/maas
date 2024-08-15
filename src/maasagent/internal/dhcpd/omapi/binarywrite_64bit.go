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

//go:build amd64 || arm64 || loong64 || mips64le || ppc64le || riscv64 || mips64 || ppc64 || s390x

package omapi

import (
	"bytes"
	"encoding/binary"
)

func binaryWrite(v any) ([]byte, error) {
	b := &bytes.Buffer{}

	var value any

	// check for non-fixed size integers, on 64bit archs, these should be int64/uint64
	switch val := v.(type) {
	case int:
		value = int64(val)
	case uint:
		value = uint64(val)
	default:
		value = val
	}

	err := binary.Write(b, binary.BigEndian, value)
	if err != nil {
		return nil, err
	}

	return b.Bytes(), nil
}
