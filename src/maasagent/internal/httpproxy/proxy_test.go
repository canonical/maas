package httpproxy

import (
	"bytes"
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
