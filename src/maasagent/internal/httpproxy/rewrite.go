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
