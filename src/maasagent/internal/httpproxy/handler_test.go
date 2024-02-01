package httpproxy

import (
	"io"
	"net/http"
	"net/url"
	"strconv"
	"testing"

	"github.com/stretchr/testify/assert"
	"maas.io/core/src/maasagent/internal/imagecache"
)

type MockResponseWriter struct {
	header http.Header
	Status int
	Body   []byte
}

func (m *MockResponseWriter) Write(b []byte) (int, error) {
	if m.Status == 0 {
		m.WriteHeader(http.StatusOK)
	}

	m.Body = b

	return len(b), nil
}

func (m *MockResponseWriter) WriteHeader(status int) {
	m.Status = status
	m.header.Set("status", strconv.Itoa(status))
}

func (m *MockResponseWriter) Header() http.Header {
	return m.header
}

type MockResponseBody struct {
	body []byte
}

func (m MockResponseBody) Read(b []byte) (int, error) {
	copy(b, m.body)
	return len(m.body), io.EOF
}

func (m MockResponseBody) Close() error {
	return nil
}

type MockRoundTripper struct {
	routes map[string][]byte
}

func (m MockRoundTripper) RoundTrip(r *http.Request) (*http.Response, error) {
	body, ok := m.routes[r.URL.Path]
	if !ok {
		return &http.Response{
			Status:     "404 Not Found",
			StatusCode: http.StatusNotFound,
			Request:    r,
		}, nil
	}

	if _, ok := r.Header["Range"]; ok {
		// If it's a partial request, make sure the status is correct at least
		// We could return the right contents as well, but then we'd need to
		// parts the Range header.
		return &http.Response{
			Status:     "206 Partial Content",
			StatusCode: http.StatusPartialContent,
			Request:    r,
			Body:       MockResponseBody{body: body},
		}, nil
	}

	return &http.Response{
		Status:     "200 OK",
		StatusCode: http.StatusOK,
		Request:    r,
		Body:       MockResponseBody{body: body},
	}, nil
}

type MockProxy struct {
	Proxy
	origin string
}

func (m MockProxy) GetOrigin() (*url.URL, error) {
	return url.Parse(m.origin)
}

func (m MockProxy) GetClient() *http.Client {
	return &http.Client{
		Transport: MockRoundTripper{
			routes: map[string][]byte{
				"/exists": []byte("hello, world!"),
			},
		},
	}
}

func (m MockProxy) GetAliases() map[string]string {
	return make(map[string]string)
}

func (m MockProxy) GetBootloaderRegistry() *imagecache.BootloaderRegistry {
	return nil
}

func (m MockProxy) GetImageCache() imagecache.Cache {
	return nil
}

func TestServeHTTP(t *testing.T) {
	validURL, _ := url.Parse("http://127.0.0.1:5248/exists")
	invalidURL, _ := url.Parse("http://127.0.0.1:5248/notexist")
	testcases := map[string]struct {
		In            *http.Request
		OutStatusCode int
		OutHeaders    http.Header
		OutBody       []byte
	}{
		"200_OK": {
			In: &http.Request{
				Method:     http.MethodGet,
				RemoteAddr: "127.0.0.1",
				URL:        validURL,
			},
			OutStatusCode: http.StatusOK,
			OutBody:       []byte("hello, world!"),
		},
		"200_OK_HEAD": {
			In: &http.Request{
				Method:     http.MethodHead,
				RemoteAddr: "127.0.0.1",
				URL:        validURL,
			},
			OutStatusCode: http.StatusOK,
		},
		"206_PARTIAL": {
			In: &http.Request{
				Method:     http.MethodGet,
				RemoteAddr: "127.0.0.1",
				URL:        validURL,
				Header: http.Header{
					"Range": {"0-"},
				},
			},
			OutBody:       []byte("hello, world!"),
			OutStatusCode: http.StatusPartialContent,
		},
		"404_NOT_FOUND": {
			In: &http.Request{
				Method:     http.MethodGet,
				RemoteAddr: "127.0.0.1",
				URL:        invalidURL,
			},
			OutStatusCode: http.StatusNotFound,
		},
		"404_NOT_FOUND_HEAD": {
			In: &http.Request{
				Method:     http.MethodHead,
				RemoteAddr: "127.0.0.1",
				URL:        invalidURL,
			},
			OutStatusCode: http.StatusNotFound,
		},
		"405_METHOD_NOT_ALLOWED": {
			In: &http.Request{
				Method:     http.MethodOptions,
				RemoteAddr: "127.0.0.1",
				URL:        validURL,
			},
			OutStatusCode: http.StatusMethodNotAllowed,
		},
	}

	handler := DefaultHandler(MockProxy{origin: "http://127.0.0.1:5240"})

	for caseName, caseParams := range testcases {
		t.Run(caseName, func(tt *testing.T) {
			resp := &MockResponseWriter{
				header: make(http.Header),
			}

			handler.ServeHTTP(resp, caseParams.In)

			for k, values := range caseParams.OutHeaders {
				for i, value := range values {
					actual := resp.Header().Values(k)[i]

					assert.Equal(tt, value, actual)
				}
			}

			assert.Equal(tt, caseParams.OutStatusCode, resp.Status)
			assert.Equal(tt, caseParams.OutBody, resp.Body)
		})
	}
}

func TestIsBootResourceRequest(t *testing.T) {
	table := map[string]struct {
		In  string
		Out bool
	}{
		"is_boot_resource": {
			In:  "http://localhost:5248/images/ubuntu/amd64/ga-22.04/jammy/stable/boot-kernel",
			Out: true,
		},
		"is_not_boot_resource": {
			In:  "http://localhost:5248/MAAS/metadata/status/abcdef",
			Out: false,
		},
	}

	for tname, tcase := range table {
		client := &proxyClient{}

		t.Run(tname, func(tt *testing.T) {
			testURL, err := url.Parse(tcase.In)
			if err != nil {
				tt.Fatal(err)
			}

			result := client.isBootResourceRequest(testURL)

			assert.Equal(tt, tcase.Out, result)
		})
	}
}
