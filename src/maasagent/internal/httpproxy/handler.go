package httpproxy

import (
	"context"
	"fmt"
	"io"
	"io/fs"
	"net/http"
	"net/url"
	"os"
	"path"
	"regexp"
	"strconv"
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
	cache       imagecache.Cache
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

func (p *proxyClient) cacheResponse(hash string) (*http.Response, bool, error) {
	result, ok, err := p.cache.Get(hash)
	if err != nil {
		return nil, false, err
	}

	if !ok {
		return nil, ok, nil
	}

	return &http.Response{
		Status:     "200 OK",
		StatusCode: http.StatusOK,
		Body:       result,
	}, true, nil
}

func (p *proxyClient) bootResourceRequest(orig *http.Request) (*http.Response, context.CancelFunc, error) {
	urlSlice := strings.Split(orig.URL.Path, "/")

	fileHash := urlSlice[2]

	var (
		resp   *http.Response
		cancel context.CancelFunc
		err    error
		ok     bool
	)

	if p.bootloaders.IsBootloader(urlSlice[len(urlSlice)-1]) {
		var f *os.File

		f, ok, err = p.bootloaders.Find(urlSlice[len(urlSlice)-1])
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

		var remotePath string

		remotePath, err = p.bootloaders.FindRemoteURL(urlSlice[len(urlSlice)-1])
		if err != nil {
			return nil, nil, err
		}

		orig.URL.Path = remotePath

		return p.req(orig, nil)
	}

	resp, ok, err = p.cacheResponse(fileHash)
	if err != nil {
		return nil, nil, err
	}

	if !ok {
		orig.URL.Path = path.Join("/boot-resources/", fileHash)

		resp, cancel, err = p.req(orig, nil)
		if err != nil {
			return nil, cancel, err
		}

		if resp.StatusCode == http.StatusOK {
			var contentLength int64

			contentLength, err = strconv.ParseInt(resp.Header.Get("content-length"), 10, 64)
			if err != nil {
				return nil, cancel, err
			}

			origBody := resp.Body

			defer func() {
				err = origBody.Close()
			}()

			resp.Body, err = p.cache.Set(fileHash, origBody, contentLength, false)
			if err != nil {
				return nil, cancel, err
			}
		}
	}

	return resp, cancel, err
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
		cache:       p.proxy.GetImageCache(),
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
	log.Err(err).Send()

	w.WriteHeader(http.StatusInternalServerError)

	_, err = w.Write([]byte(err.Error()))
	if err != nil {
		log.Err(err).Send()
	}
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
	case http.MethodHead:
		resp, cancel, err = client.Get(r)
	default:
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	if cancel != nil {
		defer cancel()
	}

	p.log(r, resp, origPath, err)

	if err != nil {
		p.handleErr(w, err)
		return
	}

	if resp.StatusCode >= 400 {
		w.WriteHeader(resp.StatusCode)
		return
	}

	defer func() {
		err = resp.Body.Close()
		if err != nil {
			p.handleErr(w, err)
		}
	}()

	// When serving from cache, we need to take care of setting all the headers properly.
	// When passed through these should be set from the origin. resp.Body is only ever
	// of type *os.File coming from the cache regardless of whether it's added or existing
	if f, ok := resp.Body.(*os.File); ok {
		var info fs.FileInfo

		info, err = f.Stat()
		if err != nil {
			p.handleErr(w, err)
			return
		}
		// Explicity set the content type, so ServeContent doesn't have to guess.
		w.Header().Set("content-type", "application/octet-stream")
		// ServeContent is used, since we need to support range requests.
		http.ServeContent(w, r, "", info.ModTime(), f)
	} else {
		copyHeaders(resp.Header, w.Header())

		if r.Method != http.MethodHead {
			w.WriteHeader(resp.StatusCode)
			_, err = io.Copy(w, resp.Body)
			if err != nil {
				p.handleErr(w, err)
				return
			}
		} else {
			w.WriteHeader(http.StatusOK)
		}
	}
}
