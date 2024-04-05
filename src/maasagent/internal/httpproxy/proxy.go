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
	"errors"
	"io"
	"io/fs"
	"math/rand"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/rs/zerolog/log"
)

// Proxy is a caching reverse HTTP proxy that sends request to a target.
type Proxy struct {
	revproxy *httputil.ReverseProxy
	rewriter *Rewriter
	cacher   *Cacher
	targets  []*url.URL
}

// NewProxy returns a new caching reverse HTTP proxy, that caches all
// HTTP 200 responses from the random pick target.
func NewProxy(targets []*url.URL, options ...ProxyOption) (*Proxy, error) {
	if len(targets) == 0 {
		return nil, errors.New("targets cannot be empty")
	}
	// Initialize using single target, but then pick a random one in Rewrite.
	revproxy := httputil.NewSingleHostReverseProxy(targets[0])

	p := Proxy{revproxy: revproxy, targets: targets}

	for _, opt := range options {
		opt(&p)
	}

	return &p, nil
}

// ProxyOption allows to set additional options for the proxy
type ProxyOption func(*Proxy)

// WithRewriter allows to set URL rewriter middleware
func WithRewriter(r *Rewriter) ProxyOption {
	return func(p *Proxy) {
		p.rewriter = r
		// At most one of Rewrite or Director may be set. Set Director to nil.
		p.revproxy.Director = nil
		p.revproxy.Rewrite = p.rewriteRequest()
		p.revproxy.ModifyResponse = p.modifyResponse()
	}
}

// WithCacher allows to set caching middleware
func WithCacher(c *Cacher) ProxyOption {
	return func(p *Proxy) {
		p.cacher = c
	}
}

func (p *Proxy) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if p.rewriter != nil {
		for _, rule := range p.rewriter.rules {
			ok := rule.Rewrite(r)
			if ok {
				break
			}
		}
	}

	if p.cacher != nil {
		ok := p.getFromCache(w, r)
		if ok {
			return
		}
	}

	p.revproxy.ServeHTTP(w, r)
}

func (p *Proxy) getFromCache(w http.ResponseWriter, r *http.Request) bool {
	var key string

	ok := true
	for _, rule := range p.cacher.rules {
		key, ok = rule.getKey(r)
		if ok {
			break
		}
	}

	if !ok {
		return false
	}

	w.Header().Set("x-cache", "MISS")

	var err error

	var reader io.ReadSeekCloser

	reader, err = p.cacher.cache.Get(key)
	if err != nil {
		return false
	}

	modtime := time.Now().UTC()
	// reader is only ever of type *os.File coming from the cache regardless of
	// whether it's added or existing.
	if f, ok := reader.(*os.File); ok {
		var info fs.FileInfo

		info, err = f.Stat()
		if err != nil {
			log.Err(err).Send()
			return false
		}

		modtime = info.ModTime()
	}

	w.Header().Set("x-cache", "HIT")
	// Explicity set the content type, so ServeContent doesn't have to guess.
	w.Header().Set("content-type", "application/octet-stream")
	http.ServeContent(w, r, "", modtime, reader)

	return true
}

// modifyResponse is a function called by the underlying revproxy before response
// is returned to the client. It is using io.Pipe and io.TeeReader to cache
// response while it is being read by the client.
func (p *Proxy) modifyResponse() func(*http.Response) error {
	return func(resp *http.Response) error {
		if p.cacher == nil {
			return nil
		}

		if resp.StatusCode != http.StatusOK {
			return nil
		}

		var key string

		ok := true
		for _, rule := range p.cacher.rules {
			key, ok = rule.getKey(resp.Request)
			if ok {
				break
			}
		}

		if !ok {
			return nil
		}

		pr, pw := io.Pipe()

		go func() {
			// If there is a pending Set() for the same key, we return an error
			// so clients are not waiting for a cache write lock and fetch resource
			// from the upstream.
			err := p.cacher.cache.Set(key, pr, resp.ContentLength)
			if err != nil {
				log.Warn().Err(err).Msg("Failed to cache value")
				// XXX: can we do anything with this error?
				_, err := io.Copy(io.Discard, pr)
				log.Warn().Err(err).Msg("Failed to discard io.Pipe")
			}
		}()

		tee := io.TeeReader(resp.Body, pw)

		resp.Body = &closer{tee, pw}

		return nil
	}
}

// rewriteRequest is a modified version of stdlib implementation taken from
// https://go.dev/src/net/http/httputil/reverseproxy.go
// The main difference here is that we pick a random target URL where
// we want to dispatch our request and apply certain rewrite rules.
func (p *Proxy) rewriteRequest() func(pr *httputil.ProxyRequest) {
	return func(pr *httputil.ProxyRequest) {
		rand.Seed(time.Now().Unix())
		//nolint:gosec // usage of math/rand is ok here
		target := p.targets[rand.Intn(len(p.targets))]

		targetQuery := target.RawQuery
		pr.Out.URL.Scheme = target.Scheme
		pr.Out.URL.Host = target.Host
		pr.Out.URL.Path, pr.Out.URL.RawPath = joinURLPath(target, pr.In.URL)

		if targetQuery == "" || pr.In.URL.RawQuery == "" {
			pr.Out.URL.RawQuery = targetQuery + pr.In.URL.RawQuery
		} else {
			pr.Out.URL.RawQuery = targetQuery + "&" + pr.In.URL.RawQuery
		}
	}
}

// singleJoiningSlash is a modified version of stdlib implementation taken from
// https://go.dev/src/net/http/httputil/reverseproxy.go
func singleJoiningSlash(a, b string) string {
	aslash := strings.HasSuffix(a, "/")
	bslash := strings.HasPrefix(b, "/")

	switch {
	case aslash && bslash:
		return a + b[1:]
	case !aslash && !bslash:
		return a + "/" + b
	}

	return a + b
}

// joinURLPath is a modified version of stdlib implementation taken from
// https://go.dev/src/net/http/httputil/reverseproxy.go
//
//nolint:nonamedreturns // this is from the standard library
func joinURLPath(a, b *url.URL) (path, rawpath string) {
	if a.RawPath == "" && b.RawPath == "" {
		return singleJoiningSlash(a.Path, b.Path), ""
	}
	// Same as singleJoiningSlash, but uses EscapedPath to determine
	// whether a slash should be added
	apath := a.EscapedPath()
	bpath := b.EscapedPath()

	aslash := strings.HasSuffix(apath, "/")
	bslash := strings.HasPrefix(bpath, "/")

	switch {
	case aslash && bslash:
		return a.Path + b.Path[1:], apath + bpath[1:]
	case !aslash && !bslash:
		return a.Path + "/" + b.Path, apath + "/" + bpath
	}

	return a.Path + b.Path, apath + bpath
}

type closer struct {
	reader io.Reader
	closer io.Closer
}

func (c *closer) Read(data []byte) (int, error) {
	return c.reader.Read(data)
}

func (c *closer) Close() error {
	return c.closer.Close()
}
