// Copyright (c) 2025 Canonical Ltd
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

package dhcp

import (
	"math"
	"net/netip"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestIPv4ToInt(t *testing.T) {
	testcases := map[string]struct {
		input    netip.Addr
		expected uint32
	}{
		"private":   {netip.AddrFrom4([4]byte{192, 168, 0, 1}), 3232235521},
		"localhost": {netip.AddrFrom4([4]byte{127, 0, 0, 1}), 2130706433}, // 127 * (2**24) + 1
		"max":       {netip.AddrFrom4([4]byte{255, 255, 255, 255}), math.MaxUint32},
	}

	for name, testcase := range testcases {
		t.Run(name, func(t *testing.T) {
			a, err := IPv4ToInt(testcase.input)
			assert.Equal(t, a, testcase.expected)
			assert.NoError(t, err)
		})
	}

	errorTestcases := map[string]struct {
		input netip.Addr
	}{
		"v6zero": {netip.AddrFrom16([16]byte{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0})},
		"empty":  {netip.Addr{}},
	}

	for name, errorTestcase := range errorTestcases {
		t.Run(name, func(t *testing.T) {
			_, err := IPv4ToInt(errorTestcase.input)
			assert.Error(t, err)
		})
	}
}

func TestIntToIPv4(t *testing.T) {
	testcases := map[string]struct {
		input    uint32
		expected netip.Addr
	}{
		"zero":      {0, netip.AddrFrom4([4]byte{0, 0, 0, 0})},
		"private":   {3232235521, netip.AddrFrom4([4]byte{192, 168, 0, 1})},
		"localhost": {2130706433, netip.AddrFrom4([4]byte{127, 0, 0, 1})}, // 127 * (2**24) + 1
		"max":       {math.MaxUint32, netip.AddrFrom4([4]byte{255, 255, 255, 255})},
	}

	for name, testcase := range testcases {
		t.Run(name, func(t *testing.T) {
			assert.Equal(t, IntToIPv4(testcase.input), testcase.expected)
		})
	}
}

func TestUint64ToUint128(t *testing.T) {
	testcases := map[string]struct {
		input    [2]uint64
		expected Uint128
	}{
		"zero":        {[2]uint64{0, 0}, Uint128{[16]byte{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0}}},
		"one-and-one": {[2]uint64{1, 1}, Uint128{[16]byte{0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1}}},
		"256-and-257": {[2]uint64{256, 257}, Uint128{[16]byte{0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 1}}},
	}

	for name, testcase := range testcases {
		t.Run(name, func(t *testing.T) {
			assert.Equal(t, Uint64sToUint128(testcase.input[0], testcase.input[1]), testcase.expected)
		})
	}
}

func TestUint128ToUint64(t *testing.T) {
	testcases := map[string]struct {
		input    Uint128
		expected [2]uint64
	}{
		"zero":        {Uint128{[16]byte{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0}}, [2]uint64{0, 0}},
		"one-and-one": {Uint128{[16]byte{0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1}}, [2]uint64{1, 1}},
		"256-and-257": {Uint128{[16]byte{0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 1}}, [2]uint64{256, 257}},
	}

	for name, testcase := range testcases {
		t.Run(name, func(t *testing.T) {
			a, b := Uint128ToUint64s(testcase.input)
			assert.Equal(t, [2]uint64{a, b}, testcase.expected)
		})
	}
}

func TestIPv6ToInt(t *testing.T) {
	testcases := map[string]struct {
		input    netip.Addr
		expected Uint128
	}{
		"zero":    {netip.AddrFrom16([16]byte{}), Uint64sToUint128(0, 0)},
		"example": {netip.AddrFrom16([16]byte{200, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 192, 168, 0, 1}), Uint64sToUint128(14411518807585587200, 3232235521)},
	}

	for name, testcase := range testcases {
		t.Run(name, func(t *testing.T) {
			a, err := IPv6ToInt(testcase.input)
			assert.Equal(t, a, testcase.expected)
			assert.NoError(t, err)
		})
	}

	errorTestcases := map[string]struct {
		input netip.Addr
	}{
		"v4zero": {netip.AddrFrom4([4]byte{0, 0, 0, 0})},
		"empty":  {netip.Addr{}},
	}

	for name, errorTestcase := range errorTestcases {
		t.Run(name, func(t *testing.T) {
			_, err := IPv6ToInt(errorTestcase.input)
			assert.Error(t, err)
		})
	}
}

func TestIntToIPv6(t *testing.T) {
	testcases := map[string]struct {
		input    Uint128
		expected netip.Addr
	}{
		"zero":    {Uint64sToUint128(0, 0), netip.AddrFrom16([16]byte{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0})},
		"example": {Uint64sToUint128(14411518807585587200, 3232235521), netip.AddrFrom16([16]byte{200, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 192, 168, 0, 1})},
	}

	for name, testcase := range testcases {
		t.Run(name, func(t *testing.T) {
			assert.Equal(t, IntToIPv6(testcase.input), testcase.expected)
		})
	}
}
