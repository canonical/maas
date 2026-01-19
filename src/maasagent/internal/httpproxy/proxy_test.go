// Copyright (c) 2023-2025 Canonical Ltd
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
	"bytes"
	"context"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"regexp"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"maas.io/core/src/maasagent/internal/cache"
)

func TestProxy(t *testing.T) {
	type in struct {
		uri      string
		upstream *httptest.Server
		headers  map[string]string
		rewriter *Rewriter
		cacher   *Cacher
	}

	type out struct {
		code    int
		headers map[string]string
		body    []byte
	}

	testcases := map[string]struct {
		in  in
		out []out
	}{
		"return upstream data if there is no rewrite or caching rules": {
			in: in{
				uri: "http://example.com/file",
				upstream: httptest.NewServer(http.HandlerFunc(
					func(w http.ResponseWriter, _ *http.Request) {
						w.Write([]byte("hello world"))
					})),
			},
			out: []out{
				{
					code: http.StatusOK,
					body: []byte("hello world"),
				},
			},
		},
		"return upstream data if no data in cache": {
			in: in{
				uri: "http://example.com/file",
				upstream: httptest.NewServer(http.HandlerFunc(
					func(w http.ResponseWriter, _ *http.Request) {
						w.Write([]byte("hello world"))
					})),
				cacher: NewCacher([]*CacheRule{
					NewCacheRule(regexp.MustCompile("/(.*)"), "$1"),
				},
					cache.NewFakeFileCache()),
			},
			out: []out{
				{
					code:    http.StatusOK,
					headers: map[string]string{"x-cache": "MISS"},
					body:    []byte("hello world"),
				},
			},
		},
		"return cached data if found": {
			in: in{
				uri: "http://example.com/file",
				upstream: httptest.NewServer(http.HandlerFunc(
					func(w http.ResponseWriter, _ *http.Request) {
					})),
				cacher: NewCacher([]*CacheRule{
					NewCacheRule(regexp.MustCompile("/(.*)"), "$1"),
				},
					func() *cache.FakeFileCache {
						cache := cache.NewFakeFileCache()
						body := bytes.NewReader([]byte("hello world"))
						cache.Set("file", body, int64(body.Len()))
						return cache
					}()),
			},
			out: []out{
				{
					code:    http.StatusOK,
					headers: map[string]string{"x-cache": "HIT"},
					body:    []byte("hello world"),
				},
			},
		},
		"return cached data if sha matches": {
			in: in{
				uri: "http://example.com/boot-resources/3c025ab/ubuntu/amd64/ga-22.04/jammy/stable/boot-kernel",
				upstream: httptest.NewServer(http.HandlerFunc(
					func(w http.ResponseWriter, _ *http.Request) {
					})),
				cacher: NewCacher([]*CacheRule{
					NewCacheRule(regexp.MustCompile("boot-resources/([0-9a-fA-F]+)/"), "$1"),
				},
					func() *cache.FakeFileCache {
						cache := cache.NewFakeFileCache()
						body := bytes.NewReader([]byte("hello world"))
						cache.Set("3c025ab", body, int64(body.Len()))
						return cache
					}()),
			},
			out: []out{
				{
					code:    http.StatusOK,
					headers: map[string]string{"x-cache": "HIT"},
					body:    []byte("hello world"),
				},
			},
		},
		"cache upstream if HTTP 200 returned": {
			in: in{
				uri: "http://example.com/file",
				upstream: httptest.NewServer(http.HandlerFunc(
					func(w http.ResponseWriter, _ *http.Request) {
						w.Write([]byte("hello world"))
					})),
				cacher: NewCacher([]*CacheRule{
					NewCacheRule(regexp.MustCompile("/(.*)"), "$1"),
				},
					cache.NewFakeFileCache()),
			},
			out: []out{
				{
					code:    http.StatusOK,
					headers: map[string]string{"x-cache": "MISS"},
					body:    []byte("hello world"),
				},
				{
					code:    http.StatusOK,
					headers: map[string]string{"x-cache": "HIT"},
					body:    []byte("hello world"),
				},
			},
		},
		"cached response should support HTTP 206 Partial Content": {
			in: in{
				uri: "http://example.com/file",
				upstream: httptest.NewServer(http.HandlerFunc(
					func(w http.ResponseWriter, _ *http.Request) {
					})),
				cacher: NewCacher([]*CacheRule{
					NewCacheRule(regexp.MustCompile("/(.*)"), "$1"),
				},
					func() *cache.FakeFileCache {
						cache := cache.NewFakeFileCache()
						body := bytes.NewReader([]byte("hello world"))
						cache.Set("file", body, int64(body.Len()))
						return cache
					}()),
				headers: map[string]string{"Range": "bytes=0-4"},
			},
			out: []out{
				{
					code:    http.StatusPartialContent,
					headers: map[string]string{"x-cache": "HIT"},
					body:    []byte("hello"),
				},
			},
		},
		"do not cache upstream response HTTP 206 Partial Content": {
			in: in{
				uri: "http://example.com/file",
				upstream: httptest.NewServer(http.HandlerFunc(
					func(w http.ResponseWriter, r *http.Request) {
						reader := bytes.NewReader([]byte("hello world"))
						http.ServeContent(w, r, "", time.Now().UTC(), reader)
					})),
				cacher: NewCacher([]*CacheRule{
					NewCacheRule(regexp.MustCompile("/(.*)"), "$1"),
				},
					cache.NewFakeFileCache()),
				headers: map[string]string{"Range": "bytes=0-4"},
			},
			out: []out{
				{
					code:    http.StatusPartialContent,
					headers: map[string]string{"x-cache": "MISS"},
					body:    []byte("hello"),
				},
				{
					code:    http.StatusPartialContent,
					headers: map[string]string{"x-cache": "MISS"},
					body:    []byte("hello"),
				},
			},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			target, err := url.Parse(tc.in.upstream.URL)
			assert.NoError(t, err)

			proxy, err := NewProxy([]*url.URL{target},
				WithRewriter(tc.in.rewriter),
				WithCacher(tc.in.cacher),
			)
			assert.NoError(t, err)

			for _, out := range tc.out {
				req := httptest.NewRequest(http.MethodGet, tc.in.uri, nil)
				for hk, hv := range tc.in.headers {
					req.Header.Set(hk, hv)
				}

				w := httptest.NewRecorder()
				proxy.ServeHTTP(w, req)

				assert.Equal(t, out.code, w.Code)

				for hk, hv := range out.headers {
					assert.Equal(t, hv, w.Result().Header.Get(hk))
				}

				assert.Equal(t, out.body, w.Body.Bytes())
			}
		})
	}
}

func TestErrorHandler_RetriesUntilSuccess(t *testing.T) {
	// failing server
	failCount := 0

	failSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		failCount++

		http.Error(w, "boom", http.StatusInternalServerError)
	}))
	defer failSrv.Close()

	// successful server
	okSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("X-Upstream", "ok")
		_, _ = w.Write([]byte("success"))
	}))
	defer okSrv.Close()

	failURL, _ := url.Parse(failSrv.URL)
	okURL, _ := url.Parse(okSrv.URL)

	proxy, err := NewProxy(
		[]*url.URL{failURL, okURL},
		WithRewriter(NewRewriter(nil)),
	)
	assert.NoError(t, err)

	req := httptest.NewRequest(http.MethodGet, "http://example.com/file", nil)
	req = req.WithContext(context.WithValue(req.Context(), targetURLKey, failURL))

	rr := httptest.NewRecorder()

	handler := proxy.errorHandler()
	handler(rr, req, errors.New("dial error"))

	assert.Equal(t, http.StatusOK, rr.Code)
	assert.Equal(t, "success", rr.Body.String())

	// failing server is not retried
	assert.Equal(t, 0, failCount)

	// both URLs remain reliable
	assert.Equal(t, 2, len(proxy.urlTracker.reliable))
}

func TestErrorHandler_RetriesUntilSuccessMovesToUnreliable(t *testing.T) {
	// failing server
	failCount := 0

	failSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		failCount++

		http.Error(w, "boom", http.StatusInternalServerError)
	}))
	defer failSrv.Close()

	// successful server
	okSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("X-Upstream", "ok")
		_, _ = w.Write([]byte("success"))
	}))
	defer okSrv.Close()

	failURL, _ := url.Parse(failSrv.URL)
	okURL, _ := url.Parse(okSrv.URL)

	proxy, err := NewProxy(
		[]*url.URL{failURL, okURL},
		WithRewriter(NewRewriter(nil)),
	)
	assert.NoError(t, err)

	// simulate that failURL already failed enough times to be marked unreliable at the next failure
	for i := 0; i < maxConsecutiveFailures-1; i++ {
		proxy.urlTracker.RecordFailure(failURL)
	}

	req := httptest.NewRequest(http.MethodGet, "http://example.com/file", nil)
	req = req.WithContext(context.WithValue(req.Context(), targetURLKey, failURL))

	rr := httptest.NewRecorder()

	handler := proxy.errorHandler()
	handler(rr, req, errors.New("dial error"))

	assert.Equal(t, http.StatusOK, rr.Code)
	assert.Equal(t, "success", rr.Body.String())

	assert.Equal(t, 1, len(proxy.urlTracker.reliable))
	assert.Equal(t, 1, len(proxy.urlTracker.unreliable))
}

func TestErrorHandler_SingleTargetFailsReturns503(t *testing.T) {
	failSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		http.Error(w, "fail", http.StatusInternalServerError)
	}))
	defer failSrv.Close()

	failURL, _ := url.Parse(failSrv.URL)

	proxy, err := NewProxy(
		[]*url.URL{failURL},
		WithRewriter(NewRewriter(nil)),
	)
	assert.NoError(t, err)

	req := httptest.NewRequest(http.MethodGet, "http://example.com/file", nil)
	req = req.WithContext(context.WithValue(req.Context(), targetURLKey, failURL))

	rr := httptest.NewRecorder()

	handler := proxy.errorHandler()
	handler(rr, req, errors.New("network error"))

	assert.Equal(t, http.StatusServiceUnavailable, rr.Code)
}

func TestErrorHandler_AllTargetsTried_ReturnsLastStatusCode(t *testing.T) {
	callCounts := map[string]int{}

	firstFailSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		http.Error(w, "fail", http.StatusInternalServerError)
	}))
	defer firstFailSrv.Close()

	firstFailURL, _ := url.Parse(firstFailSrv.URL)

	// Keep all the other servers in another structure so that we can check that the retry logic actually called all of them.
	failServers := []*httptest.Server{}
	failURLs := []*url.URL{}

	for i := 0; i < 3; i++ {
		var srv *httptest.Server

		srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
			callCounts[srv.URL]++

			http.Error(w, "fail", http.StatusInternalServerError)
		}))

		defer srv.Close()

		failServers = append(failServers, srv)

		u, err := url.Parse(srv.URL)
		assert.NoError(t, err)

		failURLs = append(failURLs, u)
	}

	proxy, err := NewProxy(failURLs, WithRewriter(NewRewriter(nil)))
	assert.NoError(t, err)

	req := httptest.NewRequest(http.MethodGet, "http://example.com/file", nil)
	req = req.WithContext(context.WithValue(req.Context(), targetURLKey, firstFailURL))

	rr := httptest.NewRecorder()
	handler := proxy.errorHandler()
	handler(rr, req, errors.New("network error"))

	assert.Equal(t, http.StatusInternalServerError, rr.Code)

	// Assert each server called exactly once
	for _, srv := range failServers {
		count := callCounts[srv.URL]
		assert.Equal(t, 1, count, "server %s should be called exactly once", srv.URL)
	}
}

func TestErrorHandler_Non2xxResponseIsRetried(t *testing.T) {
	badSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusBadGateway)
	}))
	defer badSrv.Close()

	okSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = io.WriteString(w, "ok")
	}))
	defer okSrv.Close()

	badURL, _ := url.Parse(badSrv.URL)
	okURL, _ := url.Parse(okSrv.URL)

	proxy, err := NewProxy(
		[]*url.URL{badURL, okURL},
		WithRewriter(NewRewriter(nil)),
	)
	assert.NoError(t, err)

	req := httptest.NewRequest(http.MethodGet, "http://example.com/test", nil)
	req = req.WithContext(context.WithValue(req.Context(), targetURLKey, badURL))

	rr := httptest.NewRecorder()

	handler := proxy.errorHandler()
	handler(rr, req, errors.New("upstream failure"))

	assert.Equal(t, http.StatusOK, rr.Code)
	assert.Equal(t, "ok", rr.Body.String())
}

func TestErrorHandler_RecordsFailureOnRetryError(t *testing.T) {
	failSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		http.Error(w, "fail", http.StatusInternalServerError)
	}))
	defer failSrv.Close()

	failURL, _ := url.Parse(failSrv.URL)

	proxy, err := NewProxy(
		[]*url.URL{failURL},
		WithRewriter(NewRewriter(nil)),
	)
	assert.NoError(t, err)

	req := httptest.NewRequest(http.MethodGet, "http://example.com/file", nil)
	req = req.WithContext(context.WithValue(req.Context(), targetURLKey, failURL))

	rr := httptest.NewRecorder()

	handler := proxy.errorHandler()
	handler(rr, req, errors.New("retry error"))

	// Only guaranteed behavior
	assert.Equal(t, http.StatusServiceUnavailable, rr.Code)
}

func TestErrorHandler_404IsNotRetried(t *testing.T) {
	firstFailSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		http.Error(w, "fail", http.StatusInternalServerError)
	}))
	defer firstFailSrv.Close()

	firstFailURL, _ := url.Parse(firstFailSrv.URL)

	failSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		http.Error(w, "fail", http.StatusNotFound)
	}))
	defer failSrv.Close()

	failURL, _ := url.Parse(failSrv.URL)

	proxy, err := NewProxy(
		[]*url.URL{failURL},
		WithRewriter(NewRewriter(nil)),
	)
	assert.NoError(t, err)

	req := httptest.NewRequest(http.MethodGet, "http://example.com/file", nil)
	req = req.WithContext(context.WithValue(req.Context(), targetURLKey, firstFailURL))

	rr := httptest.NewRecorder()

	handler := proxy.errorHandler()
	handler(rr, req, errors.New("retry error"))

	assert.Equal(t, http.StatusNotFound, rr.Code)
}
