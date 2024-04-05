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

package httpproxy

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"regexp"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestRewriteHandler(t *testing.T) {
	type in struct {
		url   string
		rules []*RewriteRule
	}

	testcases := map[string]struct {
		in  in
		out string
		err error
	}{
		"do not rewrite if no match": {
			in: in{
				url: "http://example.com/foo",
				rules: []*RewriteRule{
					NewRewriteRule(regexp.MustCompile("/bar(.*)"), "/foo/bar$1"),
				},
			},
			out: "/foo",
		},
		"join single path": {
			in: in{
				url: "http://example.com/foobar",
				rules: []*RewriteRule{
					NewRewriteRule(regexp.MustCompile("/foo(.*)"), "/bar$1"),
				},
			},
			out: "/barbar",
		},
		"query parameters must stay": {
			in: in{
				url: "http://example.com/foo?hello=world",
				rules: []*RewriteRule{
					NewRewriteRule(regexp.MustCompile("/(.*)"), "/$1"),
				},
			},
			out: "/foo?hello=world",
		},
		"rewrite images to boot-resources": {
			in: in{
				url: "http://example.com/images/hash/ubuntu/amd64/ga-22.04/jammy/stable/boot-kernel",
				rules: []*RewriteRule{
					NewRewriteRule(regexp.MustCompile("/images/(.*)"), "/boot-resources/$1"),
				},
			},
			out: "/boot-resources/hash/ubuntu/amd64/ga-22.04/jammy/stable/boot-kernel",
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			target, err := url.Parse(tc.out)
			assert.NoError(t, err)

			r := httptest.NewRequest(http.MethodGet, tc.in.url, nil)

			rewriter := NewRewriter(tc.in.rules)

			for _, rule := range rewriter.rules {
				ok := rule.Rewrite(r)
				if ok {
					break
				}
			}

			assert.Equal(t, target.Path, r.URL.Path)
			assert.Equal(t, target.RawPath, r.URL.RawPath)
			assert.Equal(t, target.RawQuery, r.URL.RawQuery)
		})
	}
}
