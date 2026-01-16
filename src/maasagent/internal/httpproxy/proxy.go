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
	"context"
	"errors"
	"io"
	"io/fs"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/rs/zerolog/log"
)

type contextKey string

const (
	targetURLKey contextKey = "targetURL"
)

// Proxy is a caching reverse HTTP proxy that sends request to a target.
type Proxy struct {
	revproxy   *httputil.ReverseProxy
	rewriter   *Rewriter
	cacher     *Cacher
	urlTracker *URLTracker
	// Client for making requests in error handler retries
	httpClient *http.Client
	targets    []*url.URL
}

// NewProxy returns a new caching reverse HTTP proxy, that caches all
// HTTP 200 responses from the random pick target.
func NewProxy(targets []*url.URL, options ...ProxyOption) (*Proxy, error) {
	if len(targets) == 0 {
		return nil, errors.New("targets cannot be empty")
	}
	// Initialize using single target, but then pick a random one in Rewrite.
	revproxy := httputil.NewSingleHostReverseProxy(targets[0])

	tracker, err := NewURLTracker(targets)
	if err != nil {
		return nil, err
	}

	p := Proxy{
		revproxy:   revproxy,
		targets:    targets,
		urlTracker: tracker,
		httpClient: &http.Client{},
	}

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
		p.revproxy.ErrorHandler = p.errorHandler()
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
// response while it is being read by the client. It also records successful
// requests for URL reliability tracking.
func (p *Proxy) modifyResponse() func(*http.Response) error {
	return func(resp *http.Response) error {
		// Record success for the target URL if we got a 2xx status code
		if target, ok := resp.Request.Context().Value(targetURLKey).(*url.URL); ok {
			if isSuccess(resp.StatusCode) {
				p.urlTracker.RecordSuccess(target)
			}
		}

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
				if err != nil {
					log.Warn().Err(err).Msg("Failed to discard io.Pipe")
				}
			}
		}()

		tee := io.TeeReader(resp.Body, pw)

		resp.Body = &closer{tee, pw}

		return nil
	}
}

// rewriteRequest is a modified version of stdlib implementation taken from
// https://go.dev/src/net/http/httputil/reverseproxy.go
// The main difference here is that we pick a target URL using the URL tracker
// which considers reliability, and we store the target in the request context
// for tracking purposes.
func (p *Proxy) rewriteRequest() func(pr *httputil.ProxyRequest) {
	return func(pr *httputil.ProxyRequest) {
		target := p.urlTracker.SelectURL(nil)

		// Store the selected target in the request context for tracking
		ctx := context.WithValue(pr.Out.Context(), targetURLKey, target)
		*pr.Out = *pr.Out.WithContext(ctx)

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

// errorHandler handles errors from the reverse proxy and keeps retrying until all available URLs have been tried.
func (p *Proxy) errorHandler() func(http.ResponseWriter, *http.Request, error) {
	writeResponse := func(w http.ResponseWriter, resp *http.Response) {
		// Copy headers
		for key, values := range resp.Header {
			for _, value := range values {
				w.Header().Add(key, value)
			}
		}

		w.WriteHeader(resp.StatusCode)

		if _, err := io.Copy(w, resp.Body); err != nil {
			log.Warn().Err(err).Msg("Error copying response body")
		}

		if err := resp.Body.Close(); err != nil {
			log.Warn().Err(err).Msg("Error closing response body")
		}
	}

	return func(w http.ResponseWriter, r *http.Request, err error) {
		// Get the target that failed from context
		failedTarget, ok := r.Context().Value(targetURLKey).(*url.URL)
		if ok && failedTarget != nil {
			p.urlTracker.RecordFailure(failedTarget)
			log.Warn().
				Err(err).
				Str("target", failedTarget.String()).
				Str("path", r.URL.Path).
				Msg("Request to target failed")
		}

		// Keep track of tried URLs
		triedURLs := make([]string, 0)
		if ok && failedTarget != nil {
			triedURLs = append(triedURLs, failedTarget.String())
		}

		// Last status code to return if all retries fail. This might not be very accurate as there might be network errors.
		lastStatusCode := http.StatusServiceUnavailable

		for {
			// Select a new target URL that hasn't been tried yet
			newTarget := p.urlTracker.SelectURL(triedURLs)
			if newTarget == nil {
				log.Warn().Msg("No more target URLs available for retry. Failing request.")

				http.Error(w, http.StatusText(http.StatusServiceUnavailable), lastStatusCode)

				return
			}

			// Mark as tried
			triedURLs = append(triedURLs, newTarget.String())

			// Create a new request with the alternative target.
			proxyReq := r.Clone(r.Context())
			proxyReq.URL.Scheme = newTarget.Scheme
			proxyReq.URL.Host = newTarget.Host

			proxyReq.RequestURI = ""

			// Store the new target in context
			ctx := context.WithValue(proxyReq.Context(), targetURLKey, newTarget)
			proxyReq = proxyReq.WithContext(ctx)

			log.Info().
				Str("target", newTarget.String()).
				Str("path", r.URL.Path).
				Msg("Retrying request with alternative target")

			resp, retryErr := p.httpClient.Do(proxyReq)
			if retryErr == nil {
				// Check if response is successful (2xx status code)
				if isSuccess(resp.StatusCode) {
					p.urlTracker.RecordSuccess(newTarget)
					log.Info().
						Str("target", newTarget.String()).
						Str("path", r.URL.Path).
						Int("status", resp.StatusCode).
						Msg("Request succeeded with alternative target")

					writeResponse(w, resp)

					return
				} else if resp.StatusCode == http.StatusNotFound {
					log.Debug().
						Str("target", newTarget.String()).
						Str("path", r.URL.Path).
						Int("status", resp.StatusCode).
						Msg("Received 404 from target, not retrying")

					writeResponse(w, resp)

					return
				}

				lastStatusCode = resp.StatusCode
			}
			// Network error and non-2xx status codes are treated as failures. Will try with another target in the next iteration.
			p.urlTracker.RecordFailure(newTarget)
			log.Warn().
				Err(retryErr).
				Str("target", newTarget.String()).
				Str("path", r.URL.Path).
				Msg("Retry with alternative target failed")
		}
	}
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

// isSuccess checks if the HTTP status code represents a successful response (2xx)
func isSuccess(code int) bool {
	return code >= 200 && code < 300
}
