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

package resolver

import (
	"testing"

	"github.com/miekg/dns"
	"github.com/stretchr/testify/assert"
)

func TestNextLabel(t *testing.T) {
	testcases := map[string]struct {
		in  string
		out []string
	}{
		"root": {
			in:  ".",
			out: []string{"."},
		},
		"single label": {
			in:  "maas.",
			out: []string{".", "maas."},
		},
		"basic fqdn": {
			in:  "example.com.",
			out: []string{".", "com.", "example.com."},
		},
	}

	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			qstate := newQueryState(tc.in)

			for i, expected := range tc.out {
				next, ok := qstate.NextLabel()

				if i == len(tc.out)-1 {
					assert.False(t, ok)
				}

				assert.Equal(t, expected, next)
			}
		})
	}
}

func TestSetLastResponse(t *testing.T) {
	testcases := map[string]struct {
		in    dns.RR
		check func(*queryState) bool
	}{
		"A": {
			in: &dns.A{
				Hdr: dns.RR_Header{
					Name: "a.record",
				},
			},
			check: func(q *queryState) bool {
				lastResp := q.lastResponse.Header().Name == "a.record"
				ns := q.mostSpecificNS == nil

				return lastResp && ns
			},
		},
		"NS": {
			in: &dns.NS{
				Hdr: dns.RR_Header{
					Name: "ns.record",
				},
			},
			check: func(q *queryState) bool {
				lastResp := q.lastResponse.Header().Name == "ns.record"
				ns := q.mostSpecificNS.Header().Name == "ns.record"

				return lastResp && ns
			},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			q := newQueryState("")

			q.SetLastResponse(tc.in)

			assert.True(t, tc.check(q))
		})
	}
}

func TestUseSearch(t *testing.T) {
	testcases := map[string]struct {
		in  string
		out bool
	}{
		"use search": {
			in:  "example.",
			out: true,
		},
		"root": {
			in:  ".",
			out: false,
		},
		"no search": {
			in:  "example.com.",
			out: false,
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			q := newQueryState(tc.in)

			assert.Equal(t, tc.out, q.UseSearch())
		})
	}
}

func TestCanContinue(t *testing.T) {
	testcases := map[string]struct {
		in  int
		out bool
	}{
		"zero": {
			in:  0,
			out: true,
		},
		"less than max recursion": {
			in:  1,
			out: true,
		},
		"max recursion": {
			in:  maxRecursionDepth,
			out: false,
		},
	}

	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			q := newQueryState("")

			q.recursionDepth = tc.in

			assert.Equal(t, tc.out, q.CanContinue())
		})
	}
}
