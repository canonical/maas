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

//go:build 386 || arm || mips || mipsle

package omapi

import (
	"bytes"
	"encoding/binary"
)

func binaryWrite(v any) ([]byte, error) {
	b := &bytes.Buffer{}

	var value any

	// check for unfixed size integers, these should be int32/uint32 on 32bit archs
	switch val := v.(type) {
	case int:
		value = int32(val)
	case uint:
		value = uint32(val)
	default:
		value = val
	}

	err := binary.Write(b, binary.BigEndian, value)
	if err != nil {
		return nil, err
	}

	return b.Bytes(), nil
}
