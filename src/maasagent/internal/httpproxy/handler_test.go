package httpproxy

import (
	"io"
	"net/http"
	"net/url"
	"strconv"
	"testing"

	"github.com/stretchr/testify/assert"
)

type MockResponseWriter struct {
	header http.Header
	Status int
	Body   []byte
}

func (m *MockResponseWriter) Write(b []byte) (int, error) {
	m.Status = http.StatusOK
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
		"404_NOT_FOUND": {
			In: &http.Request{
				Method:     http.MethodGet,
				RemoteAddr: "127.0.0.1",
				URL:        invalidURL,
			},
			OutStatusCode: http.StatusNotFound,
		},
		"405_METHOD_NOT_ALLOWED": {
			In: &http.Request{
				Method:     http.MethodPost,
				RemoteAddr: "127.0.0.1",
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
