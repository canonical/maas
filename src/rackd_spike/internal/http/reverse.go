package http

import (
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"sync"

	"github.com/rs/zerolog"

	machinehelpers "rackd/internal/machine_helpers"
	"rackd/internal/service"
)

var (
	ErrNoUpstreams = errors.New("no upstreams available to proxy")
)

type RevProxyService interface {
	service.Service
	Configure(context.Context, []string) error
}

type ReverseProxy struct {
	sync.Mutex
	Proxy
	upstreamRegions []*net.TCPAddr
	resourcePath    string
}

func NewReverseProxy(ctx context.Context, machineResourcePath, bindAddr string, port int) (*ReverseProxy, error) {
	return NewReverseProxyWithTLS(ctx, machineResourcePath, bindAddr, port, nil)
}

func NewReverseProxyWithTLS(ctx context.Context, machineResourcePath, bindAddr string, port int, tlsCfg *tls.Config) (*ReverseProxy, error) {
	addr := net.JoinHostPort(bindAddr, strconv.Itoa(port))
	return NewReverseProxyWithOptions(ctx, machineResourcePath, ProxyOptions{
		FrontendAddr:   addr,
		FrontendTLSCfg: tlsCfg,
	})
}

func NewReverseProxyWithOptions(ctx context.Context, machineResourcePath string, opts ProxyOptions) (*ReverseProxy, error) {
	p, err := NewProxyWithOptions(ctx, opts)
	if err != nil {
		return nil, err
	}
	r := &ReverseProxy{
		Proxy: *p,
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/MAAS/", r.ServeMAAS)
	mux.Handle("/machine-resources/", http.FileServer(http.FS(os.DirFS(machineResourcePath))))
	mux.HandleFunc("/images/", r.ServeImages)
	mux.HandleFunc("/log", r.ServeLog)
	mux.HandleFunc("/", r.ServeBoot)
	r.Proxy.srvr.Handler = mux
	return r, nil
}

func (r *ReverseProxy) Name() string {
	return "http_reverse_proxy"
}

func (p *ReverseProxy) pickRegionHost() (*net.TCPAddr, error) {
	p.Lock()
	defer p.Unlock()
	if len(p.upstreamRegions) == 0 {
		return nil, ErrNoUpstreams
	}
	region := p.upstreamRegions[0]
	if len(p.upstreamRegions) > 1 {
		p.upstreamRegions = append(p.upstreamRegions[1:], region) // place the selected at end of list for round robin-ing
	}
	return region, nil
}

func (p *ReverseProxy) proxyPass(ctx context.Context, fwdURL string, w http.ResponseWriter, r *http.Request) {
	logger := zerolog.Ctx(ctx)
	req, err := http.NewRequestWithContext(ctx, r.Method, fwdURL, r.Body)
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	req.Header = r.Header.Clone()
	p.setForwardingHeaders(req.Header, r)
	resp, err := p.client.Do(req)
	if err != nil {
		p.handleResponseError(ctx, r, resp, w, err)
		return
	}
	if resp.StatusCode >= 400 {
		p.handleResponseError(ctx, r, resp, w, nil)
		return
	}
	p.PassResponseHeaders(w, resp)
	w.WriteHeader(resp.StatusCode)
	_, err = io.Copy(w, resp.Body)
	if err != nil {
		logger.Err(err).Msgf("writing body to %s", r.RemoteAddr)
	}
}

func (p *ReverseProxy) ServeMAAS(w http.ResponseWriter, r *http.Request) {
	ctx := p.getCtx()
	defer r.Body.Close()
	regionAddr, err := p.pickRegionHost()
	if err != nil {
		w.WriteHeader(http.StatusBadGateway)
		return
	}
	fwdURL := "http://" + regionAddr.String() + r.URL.RequestURI()
	p.proxyPass(ctx, fwdURL, w, r)
}

func (p *ReverseProxy) ServeImages(w http.ResponseWriter, r *http.Request) {
	ctx := p.getCtx()
	authReq, err := http.NewRequestWithContext(ctx, "GET", fmt.Sprintf("http://"+p.opts.FrontendAddr+"/log"), http.NoBody)
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	resp, err := p.client.Do(authReq)
	if err != nil {
		p.handleResponseError(ctx, r, resp, w, err)
		return
	}
	if resp.StatusCode >= 400 {
		p.handleResponseError(ctx, r, resp, w, nil)
		return
	}
	resource := filepath.Join(p.resourcePath, r.URL.Path)
	f, err := os.Open(resource)
	if err != nil {
		if err == os.ErrNotExist {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		if err == os.ErrPermission {
			w.WriteHeader(http.StatusForbidden)
			return
		}
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	defer f.Close()
	w.WriteHeader(http.StatusOK)
	_, err = io.Copy(w, f)
	if err != nil {
		logger := zerolog.Ctx(ctx)
		logger.Err(err).Msgf("writing body to %s", r.RemoteAddr)
	}
}

func (p *ReverseProxy) ServeLog(w http.ResponseWriter, r *http.Request) {
	ctx := p.getCtx()
	defer r.Body.Close()
	err := p.checkIsInternal(r)
	if err != nil {
		w.WriteHeader(http.StatusForbidden)
		return
	}
	region, err := p.pickRegionHost()
	if err != nil {
		w.WriteHeader(http.StatusBadGateway)
		return
	}
	regionLogURL := "http://" + net.JoinHostPort(region.IP.String(), "5249") + r.URL.RequestURI()
	req, err := http.NewRequestWithContext(ctx, r.Method, regionLogURL, r.Body)
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	req.Header = r.Header.Clone()
	req.Header.Set("X-Original-URI", r.URL.String())
	req.Header.Set("X-Original-Remote-IP", r.RemoteAddr)
	resp, err := p.client.Do(req)
	if err != nil {
		p.handleResponseError(ctx, r, resp, w, err)
		return
	}
	if resp.StatusCode >= 400 {
		p.handleResponseError(ctx, r, resp, w, nil)
		return
	}
	p.PassResponseHeaders(w, resp)
	w.WriteHeader(resp.StatusCode)
	_, err = io.Copy(w, r.Body)
	if err != nil {
		logger := zerolog.Ctx(ctx)
		logger.Err(err).Msgf("writing body to %s", r.RemoteAddr)
	}
}

func (p *ReverseProxy) ServeBoot(w http.ResponseWriter, r *http.Request) {
	ctx := p.getCtx()
	region, err := p.pickRegionHost()
	if err != nil {
		w.WriteHeader(http.StatusBadGateway)
		return
	}
	fwdURL := "http://" + net.JoinHostPort(region.IP.String(), "5249") + r.URL.RequestURI()
	p.proxyPass(ctx, fwdURL, w, r)
}

func (p *ReverseProxy) Configure(ctx context.Context, regions []string) (err error) {
	p.resourcePath, err = machinehelpers.GetResourcesBinPath()
	if err != nil {
		return err
	}
	p.upstreamRegions = make([]*net.TCPAddr, len(regions))
	for i, region := range regions {
		if regionURL, err := url.Parse(region); err == nil {
			p.upstreamRegions[i], err = net.ResolveTCPAddr("tcp", regionURL.Host)
			if err != nil {
				return err
			}
		} else if _, _, err := net.SplitHostPort(region); err == nil {
			p.upstreamRegions[i], err = net.ResolveTCPAddr("tcp", region)
			if err != nil {
				return err
			}
		} else { // if not url, try as host or IP
			p.upstreamRegions[i], err = net.ResolveTCPAddr("tcp", net.JoinHostPort(region, "5240"))
			if err != nil {
				return err
			}
		}
	}
	return p.Restart(ctx)
}
