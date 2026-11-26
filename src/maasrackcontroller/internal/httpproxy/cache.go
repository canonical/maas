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
	"io"
	"net/http"
	"net/url"
	"path"
	"regexp"
)

type CacheRule struct {
	*regexp.Regexp
	key string
}

func NewCacheRule(pattern *regexp.Regexp, key string) *CacheRule {
	return &CacheRule{pattern, key}
}

func (r *CacheRule) getKey(req *http.Request) (string, bool) {
	origPath := req.URL.Path

	if !r.MatchString(origPath) {
		return "", false
	}

	target := path.Clean(origPath)

	u, err := url.Parse(target)
	if err != nil {
		// XXX: this is something that should not happen. panic() for now,
		// but maybe we should return an error instead.
		panic(err)
	}

	uri := u.RequestURI()
	match := r.FindStringSubmatchIndex(uri)

	result := []byte{}
	result = r.ExpandString(result, r.key, uri, match)

	return string(result), true
}

type Cache interface {
	Set(key string, value io.Reader, valueSize int64) error
	Get(key string) (io.ReadSeekCloser, error)
}

type Cacher struct {
	cache Cache
	rules []*CacheRule
}

func NewCacher(rules []*CacheRule, cache Cache) *Cacher {
	c := Cacher{}

	c.rules = rules
	c.cache = cache

	return &c
}
