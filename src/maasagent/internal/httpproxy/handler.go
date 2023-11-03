package httpproxy

import (
	"context"
	"io"
	"net/http"
	"net/url"
	"time"
)

const (
	defaultOriginTimeout = 10 * time.Minute
)

var (
	// DefaultFileAliases is a map of requested names and their
	// corresponding BootResource hash
	DefaultFileAliases = map[string]string{
		"TODO": "some_value",
	}
)

type proxyClient struct {
	origin *url.URL
	c      *http.Client
}

// Get sends a GET request to a configured origin for the requested file
func (p *proxyClient) Get(orig *http.Request) (*http.Response, error) {
	newURL := p.origin.JoinPath(orig.URL.Path)

	ctx, cancel := context.WithTimeout(context.Background(), defaultOriginTimeout)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, newURL.String(), nil)
	if err != nil {
		return nil, err
	}

	for k, values := range orig.Header {
		for _, val := range values {
			req.Header.Add(k, val)
		}
	}

	forwardedFor := orig.Header.Get("x-forwarded-for")
	if len(forwardedFor) == 0 {
		forwardedFor = orig.RemoteAddr
	} else {
		forwardedFor = forwardedFor + ", " + orig.RemoteAddr
	}

	req.Header.Set("x-forwarded-for", forwardedFor)

	forwardedHost := orig.Header.Get("x-forwarded-host")
	if len(forwardedHost) == 0 {
		forwardedHost = orig.RemoteAddr
	}

	req.Header.Set("x-forwarded-host", forwardedHost)

	return p.c.Do(req)
}

type proxyHandler struct {
	proxy   Proxy
	aliases map[string]string
}

// DefaultHandler is the default HTTP handler for the image
// proxy
func DefaultHandler(p Proxy) http.Handler {
	return &proxyHandler{
		proxy:   p,
		aliases: DefaultFileAliases,
	}
}

// GetClient returns a proxy client for a single origin
func (p *proxyHandler) GetClient() (*proxyClient, error) {
	origin, err := p.proxy.GetOrigin()
	if err != nil {
		return nil, err
	}

	return &proxyClient{
		origin: origin,
		c:      p.proxy.GetClient(),
	}, nil
}

func (p *proxyHandler) handleErr(w http.ResponseWriter, err error) {
	// TODO handle non-origin errors
}

// ServeHTTP implements the http.Handler interface and proxies requests to a
// chosen origin
func (p *proxyHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	// TODO alias lookup
	// TODO cache lookup

	client, err := p.GetClient()
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)

		p.handleErr(w, err)

		return
	}

	resp, err := client.Get(r)
	if err != nil {
		p.handleErr(w, err)
		return
	}

	if resp.StatusCode >= 400 {
		w.WriteHeader(resp.StatusCode)
		return
	}

	// TODO set proxy headers
	defer func() {
		err = resp.Body.Close()
		if err != nil {
			p.handleErr(w, err)
		}
	}()

	_, err = io.Copy(w, resp.Body)
	if err != nil {
		p.handleErr(w, err)
	}
}
