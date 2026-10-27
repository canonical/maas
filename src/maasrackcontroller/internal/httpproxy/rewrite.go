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
	"net/url"
	"path"
	"regexp"
)

type RewriteRule struct {
	*regexp.Regexp
	target string
}

func NewRewriteRule(pattern *regexp.Regexp, to string) *RewriteRule {
	return &RewriteRule{pattern, to}
}

func (r *RewriteRule) Rewrite(req *http.Request) bool {
	origPath := req.URL.Path

	if !r.MatchString(origPath) {
		return false
	}

	target := path.Clean(r.Replace(req.URL))

	u, err := url.Parse(target)
	if err != nil {
		// XXX: this is something that should not happen. panic() for now,
		// but maybe we should return an error instead.
		panic(err)
	}

	req.Header.Set("X-Original-URI", req.URL.RequestURI())

	req.URL.Path = u.Path
	req.URL.RawPath = u.RawPath

	if u.RawQuery != "" {
		req.URL.RawQuery = u.RawQuery
	}

	return true
}

func (r *RewriteRule) Replace(u *url.URL) string {
	uri := u.RequestURI()
	match := r.FindStringSubmatchIndex(uri)

	result := []byte{}
	result = r.ExpandString(result, r.target, uri, match)

	return string(result)
}

type Rewriter struct {
	rules []*RewriteRule
}

func NewRewriter(rules []*RewriteRule) *Rewriter {
	return &Rewriter{rules: rules}
}
