package httpproxy

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"path"
	"regexp"
	"strings"
	"time"

	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"

	"maas.io/core/src/maasagent/internal/imagecache"
)

const (
	defaultOriginTimeout = 3 * time.Minute
)

var (
	bootResourceRegexp = regexp.MustCompile(`(^\/images.*)|(^\/boot\/.*)|(.*\.efi)|(.*\.c32)|(.*bootppc64.bin)|(.*lpxelinux.0)`)
)

func copyHeaders(origHeaders, newHeaders http.Header) {
	for k, values := range origHeaders {
		for _, val := range values {
			if k == "Server" {
				newHeaders.Add(k, "maas-agent")
				continue
			}

			newHeaders.Add(k, val)
		}
	}
}

func getProtoScheme(req *http.Request) string {
	if req.TLS != nil {
		return "https"
	}

	return "http"
}

type proxyClient struct {
	origin      *url.URL
	c           *http.Client
	bootloaders *imagecache.BootloaderRegistry
}

func (p *proxyClient) setForwardedForHeaders(orig, req *http.Request) {
	req.Header.Set(
		"Forwarded",
		fmt.Sprintf(
			"by=%s;for=%s;host=%s;proto=%s",
			orig.URL.Host,
			orig.RemoteAddr,
			orig.Header.Get("Host"),
			getProtoScheme(orig),
		),
	)

	forwardedFor := orig.Header.Get("x-forwarded-for")
	if len(forwardedFor) == 0 {
		forwardedFor = orig.RemoteAddr
	} else {
		forwardedFor = forwardedFor + ", " + orig.RemoteAddr
	}

	req.Header.Set("x-forwarded-for", forwardedFor)
}

func (p *proxyClient) req(orig *http.Request, body io.ReadCloser) (*http.Response, context.CancelFunc, error) {
	newURL := p.origin.JoinPath(orig.URL.Path)

	ctx, cancel := context.WithTimeout(context.Background(), defaultOriginTimeout)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, newURL.String(), body)
	if err != nil {
		return nil, cancel, err
	}

	copyHeaders(orig.Header, req.Header)

	p.setForwardedForHeaders(orig, req)

	resp, err := p.c.Do(req)

	return resp, cancel, err
}

func (p *proxyClient) isBootResourceRequest(requestURL *url.URL) bool {
	return bootResourceRegexp.MatchString(requestURL.Path)
}

func (p *proxyClient) bootResourceRequest(orig *http.Request) (*http.Response, context.CancelFunc, error) {
	urlSlice := strings.Split(orig.URL.Path, "/")

	fileHash := urlSlice[2]

	orig.URL.Path = path.Join("/boot-resources/", fileHash)

	if p.bootloaders.IsBootloader(urlSlice[len(urlSlice)-1]) {
		f, ok, err := p.bootloaders.Find(urlSlice[len(urlSlice)-1])
		if err != nil {
			return nil, nil, err
		}

		if ok {
			return &http.Response{
				Body:       f,
				StatusCode: http.StatusOK,
				Status:     "200 OK",
			}, nil, nil
		}

		remotePath, err := p.bootloaders.FindRemoteURL(urlSlice[len(urlSlice)-1])
		if err != nil {
			return nil, nil, err
		}

		orig.URL.Path = remotePath
	}

	// TODO check cache and write to it
	return p.req(orig, nil)
}

// Get sends a GET request to a configured origin for the requested file
func (p *proxyClient) Get(orig *http.Request) (*http.Response, context.CancelFunc, error) {
	if p.isBootResourceRequest(orig.URL) {
		return p.bootResourceRequest(orig)
	}

	return p.req(orig, nil)
}

func (p *proxyClient) Post(orig *http.Request) (*http.Response, context.CancelFunc, error) {
	defer func() {
		err := orig.Body.Close()
		if err != nil {
			log.Err(err).Send()
		}
	}()

	return p.req(orig, orig.Body)
}

func (p *proxyClient) Put(orig *http.Request) (*http.Response, context.CancelFunc, error) {
	defer func() {
		err := orig.Body.Close()
		if err != nil {
			log.Err(err).Send()
		}
	}()

	return p.req(orig, orig.Body)
}

func (p *proxyClient) Delete(orig *http.Request) (*http.Response, context.CancelFunc, error) {
	defer func() {
		err := orig.Body.Close()
		if err != nil {
			log.Err(err).Send()
		}
	}()

	return p.req(orig, orig.Body)
}

type proxyHandler struct {
	proxy Proxy
}

// DefaultHandler is the default HTTP handler for the image
// proxy
func DefaultHandler(p Proxy) http.Handler {
	return &proxyHandler{
		proxy: p,
	}
}

// GetClient returns a proxy client for a single origin
func (p *proxyHandler) GetClient() (*proxyClient, error) {
	origin, err := p.proxy.GetOrigin()
	if err != nil {
		return nil, err
	}

	return &proxyClient{
		origin:      origin,
		c:           p.proxy.GetClient(),
		bootloaders: p.proxy.GetBootloaderRegistry(),
	}, nil
}

func (p *proxyHandler) log(req *http.Request, resp *http.Response, origPath string, err error) {
	var (
		ev     *zerolog.Event
		status int
	)

	if resp != nil {
		status = resp.StatusCode
	}

	if err != nil {
		ev = log.Err(err)

		if status == 0 {
			status = 500
		}
	} else {
		//nolint:zerologlint // dispatched at line 220 instead of inline
		ev = log.Debug()
	}

	ev.Msgf("%s %s->%s %d", req.Method, origPath, req.URL.Path, status)
}

func (p *proxyHandler) handleErr(w http.ResponseWriter, err error) {
	// TODO handle non-origin errors
}

// ServeHTTP implements the http.Handler interface and proxies requests to a
// chosen origin
func (p *proxyHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	client, err := p.GetClient()
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)

		p.handleErr(w, err)

		return
	}

	var (
		resp   *http.Response
		cancel context.CancelFunc
	)

	origPath := r.URL.Path

	switch r.Method {
	case http.MethodGet:
		resp, cancel, err = client.Get(r)
	case http.MethodPost:
		resp, cancel, err = client.Post(r)
	case http.MethodPut:
		resp, cancel, err = client.Put(r)
	case http.MethodDelete:
		resp, cancel, err = client.Delete(r)
	default:
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	defer cancel()

	p.log(r, resp, origPath, err)

	if err != nil {
		p.handleErr(w, err)
		return
	}

	if resp.StatusCode >= 400 {
		w.WriteHeader(resp.StatusCode)
		return
	}

	copyHeaders(resp.Header, w.Header())

	defer func() {
		err = resp.Body.Close()
		if err != nil {
			p.handleErr(w, err)
		}
	}()

	_, err = io.Copy(w, resp.Body)
	if err != nil {
		p.handleErr(w, err)
		return
	}
}
