package http

import (
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"io"
	stdlibLog "log"
	"net"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/rs/zerolog"

	"rackd/internal/service"
)

var (
	ErrCircularRequest    = errors.New("error circular request")
	ErrNotInternalAddress = errors.New("received external request on internal endpoint")
	ErrClientNotAllowed   = errors.New("client not found in allowed CIDRs")
)

type ProxyService interface {
	service.Service
	Configure(ctx context.Context, enabled, preferV4 bool, port int16, allowedCidrs []*net.IPNet) error
}

type Proxy struct {
	sync.Mutex
	srvr         *http.Server
	client       *http.Client
	opts         *ProxyOptions
	selfAddr     *net.TCPAddr
	enabled      bool
	allowedCidrs []*net.IPNet
	getCtx       func() context.Context
}

func NewProxy(ctx context.Context, bindAddr string, port int) (*Proxy, error) {
	return NewProxyWithTLS(ctx, bindAddr, port, nil)
}

func NewProxyWithTLS(ctx context.Context, bindAddr string, port int, tlsCfg *tls.Config) (*Proxy, error) {
	addr := net.JoinHostPort(bindAddr, strconv.Itoa(port))
	return NewProxyWithOptions(ctx, ProxyOptions{
		FrontendAddr:   addr,
		FrontendTLSCfg: tlsCfg,
	})
}

type ProxyOptions struct {
	MaxHeaderSize            int
	HTTP2Enabled             bool
	FrontendTLSCfg           *tls.Config
	ConnectTimeout           time.Duration
	ReadTimeout              time.Duration
	HdrRdTimeout             time.Duration
	WriteTimeout             time.Duration
	IdleTimeout              time.Duration
	UpstreamTLSTimeout       time.Duration
	UpstreamMaxIdleConns     int
	UpstreamMaxConnsPerHost  int
	WriteBufSize             int
	ReadBufSize              int
	FrontendAddr             string
	BackendAddr              string
	IgnoreUpstreamHostVerify bool
	NoKeepAlive              bool
	NoCompression            bool
}

func NewProxyWithOptions(ctx context.Context, opts ProxyOptions) (*Proxy, error) {
	logger := zerolog.Ctx(ctx)
	errorLogger := stdlibLog.New(logger, "http-proxy", stdlibLog.LstdFlags|stdlibLog.LUTC) // wrap the existing logger in the stdlib log for http.Server
	var clientTLSCfg *tls.Config
	if opts.IgnoreUpstreamHostVerify {
		clientTLSCfg = &tls.Config{
			InsecureSkipVerify: opts.IgnoreUpstreamHostVerify,
		}
	}
	if len(opts.BackendAddr) == 0 {
		opts.BackendAddr = "0.0.0.0"
	}
	backendAddr, err := net.ResolveTCPAddr("tcp", net.JoinHostPort(opts.BackendAddr, "0"))
	if err != nil {
		return nil, err
	}
	frontendAddr, err := net.ResolveTCPAddr("tcp", opts.FrontendAddr)
	if err != nil {
		return nil, err
	}
	httpDialer := &net.Dialer{
		Timeout:   opts.ConnectTimeout,
		LocalAddr: backendAddr,
		Cancel:    ctx.Done(),
	}
	if opts.NoKeepAlive {
		httpDialer.KeepAlive = -1
	}
	httpsDialer := &tls.Dialer{
		NetDialer: httpDialer,
		Config:    clientTLSCfg,
	}
	if opts.HTTP2Enabled {
		opts.FrontendTLSCfg.NextProtos = []string{"h2"}
	}
	p := &Proxy{
		srvr: &http.Server{
			Addr:              opts.FrontendAddr,
			TLSConfig:         opts.FrontendTLSCfg,
			ReadTimeout:       opts.ReadTimeout,
			ReadHeaderTimeout: opts.HdrRdTimeout,
			WriteTimeout:      opts.WriteTimeout,
			IdleTimeout:       opts.IdleTimeout,
			ErrorLog:          errorLogger,
			BaseContext: func(_ net.Listener) context.Context {
				return ctx
			},
		},
		client: &http.Client{
			Transport: &http.Transport{
				Proxy:                  nil,
				DialContext:            httpDialer.DialContext,
				DialTLSContext:         httpsDialer.DialContext,
				TLSClientConfig:        clientTLSCfg,
				TLSHandshakeTimeout:    opts.UpstreamTLSTimeout,
				DisableKeepAlives:      opts.NoKeepAlive,
				DisableCompression:     opts.NoCompression,
				MaxIdleConns:           opts.UpstreamMaxIdleConns,
				MaxConnsPerHost:        opts.UpstreamMaxConnsPerHost,
				IdleConnTimeout:        opts.IdleTimeout,
				ResponseHeaderTimeout:  opts.HdrRdTimeout,
				MaxResponseHeaderBytes: int64(opts.MaxHeaderSize),
				WriteBufferSize:        opts.WriteBufSize,
				ReadBufferSize:         opts.ReadBufSize,
				ForceAttemptHTTP2:      opts.HTTP2Enabled,
			},
		},
		opts:     &opts,
		selfAddr: frontendAddr,
	}
	p.srvr.Handler = p
	return p, nil
}

func (p *Proxy) Name() string {
	return "http_proxy"
}

func (p *Proxy) Type() int {
	return service.SvcPROXY
}

func (p *Proxy) PID() int {
	return os.Getpid()
}

func (p *Proxy) Start(ctx context.Context) (err error) {
	if !p.enabled {
		return nil
	}
	var listener net.Listener
	if p.opts.FrontendTLSCfg != nil {
		listener, err = tls.Listen("tcp", p.opts.FrontendAddr, p.opts.FrontendTLSCfg)
	} else {
		listener, err = net.Listen("tcp", p.opts.FrontendAddr)
	}
	if err != nil {
		return err
	}
	p.getCtx = func() context.Context {
		return ctx
	}
	go p.srvr.Serve(listener)
	return nil
}

func (p *Proxy) Stop(ctx context.Context) error {
	return p.srvr.Shutdown(ctx)
}

func (p *Proxy) checkForCircularReq(r *http.Request) (err error) {
	port := r.URL.Port()
	if len(port) == 0 {
		if r.URL.Scheme == "https" {
			port = "443"
		} else {
			port = "80"
		}
	}
	var ips []net.IP
	ip := net.ParseIP(r.URL.Hostname())
	if ip == nil {
		ips, err = net.DefaultResolver.LookupIP(p.getCtx(), "ip", r.URL.Hostname())
		if err != nil {
			return err
		}
	} else {
		ips = []net.IP{ip}
	}
	for _, iaddr := range ips {
		remoteAddr, err := net.ResolveTCPAddr("tcp", net.JoinHostPort(iaddr.String(), port))
		if err != nil {
			return err
		}
		if remoteAddr.String() == p.selfAddr.String() {
			return ErrCircularRequest
		}
	}
	return nil
}

func (p *Proxy) setForwardingHeaders(h http.Header, req *http.Request) {
	h.Set("X-Forwarded-For", req.RemoteAddr)
	h.Set("X-Forwarded-Host", req.Host)
	h.Set("Host", req.Host)
	h.Set("Forwarded", fmt.Sprintf("by=%s", p.selfAddr.String()))
	h.Add("Forwarded", fmt.Sprintf("for=%s", req.RemoteAddr))
	h.Add("Forwarded", fmt.Sprintf("host=%s", req.Host))
	h.Add("Forwarded", fmt.Sprintf("proto=%s", req.URL.Scheme))
	h.Set("Origin", fmt.Sprintf("%s://%s", req.URL.Scheme, req.URL.Host))
}

func (p *Proxy) handleNetError(ctx context.Context, req *http.Request, w http.ResponseWriter, err error) {
	if err == net.ErrClosed || err == syscall.ECONNREFUSED {
		w.WriteHeader(http.StatusServiceUnavailable)
		return
	}
	if err == syscall.ECONNRESET || err == syscall.EHOSTUNREACH || err == syscall.EIO || err == syscall.EPIPE {
		w.WriteHeader(http.StatusBadGateway)
		return
	}
	if timeout, ok := err.(net.Error); (ok && timeout.Timeout()) || err == syscall.ETIMEDOUT {
		w.WriteHeader(http.StatusGatewayTimeout)
		return
	}
	w.WriteHeader(http.StatusInternalServerError)
}

func (p *Proxy) handleResponseError(ctx context.Context, req *http.Request, resp *http.Response, w http.ResponseWriter, err error) {
	logger := zerolog.Ctx(ctx)
	if resp == nil {
		logger.Err(err).Msgf("no response received")
		p.handleNetError(ctx, req, w, err)
		return
	}
	logger.Err(err).Msgf("forward error to: %s, status %d", req.URL.RequestURI(), resp.StatusCode)
	switch resp.StatusCode {
	case 500, 400, 401, 402, 403, 404, 406, 409, 410, 411, 412, 413, 414, 415, 416, 417, 422, 423, 424, 425, 428, 431, 451, 501, 507, 510, 511:
		w.WriteHeader(resp.StatusCode)
		return
	case 502, 503, 504, 505, 506:
		w.WriteHeader(http.StatusBadGateway)
		return
	default:
		p.handleNetError(ctx, req, w, err)
	}
}

func (p *Proxy) PassResponseHeaders(w http.ResponseWriter, resp *http.Response) {
	for k, v := range resp.Header {
		w.Header().Set(k, v[0])
		if len(v) > 1 {
			for _, val := range v[1:] {
				w.Header().Add(k, val)
			}
		}
	}
}

func (p *Proxy) checkIsInternal(r *http.Request) error {
	hostPortSlice := strings.Split(r.RemoteAddr, ":")
	remoteHost, _ := hostPortSlice[0], hostPortSlice[1]
	for _, internalHost := range []string{"localhost", "127.0.0.1", "::1"} {
		if remoteHost == internalHost {
			return nil
		}
	}
	return ErrNotInternalAddress
}

func (p *Proxy) checkIPAllowed(remoteAddr string) error {
	remoteHost, _, err := net.SplitHostPort(remoteAddr)
	if err != nil {
		return err
	}
	remoteIP := net.ParseIP(remoteHost)
	_, localNet, err := net.ParseCIDR("127.0.0.0/8")
	if err != nil {
		return err
	}
	for _, allowed := range append(p.allowedCidrs, localNet) {
		if !allowed.Contains(remoteIP) {
			return ErrClientNotAllowed
		}
	}
	return nil
}

func (p *Proxy) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	logger := zerolog.Ctx(p.getCtx())
	defer r.Body.Close()
	err := p.checkIPAllowed(r.RemoteAddr)
	if err != nil {
		w.WriteHeader(http.StatusForbidden)
		return
	}
	fwdURL := r.URL.String()
	if len(r.URL.Scheme) == 0 {
		if r.URL.Port() == "443" {
			fwdURL = "https:" + fwdURL
		} else {
			fwdURL = "http:" + fwdURL
		}
	}
	logger.Debug().Msgf("%s requesting %s %s", r.RemoteAddr, r.Method, fwdURL)
	err = p.checkForCircularReq(r)
	if err != nil {
		w.WriteHeader(http.StatusLoopDetected)
		return
	}
	fwdReq, err := http.NewRequestWithContext(p.getCtx(), r.Method, fwdURL, r.Body)
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	fwdReq.Header = r.Header.Clone()
	p.setForwardingHeaders(fwdReq.Header, r)
	resp, err := p.client.Do(fwdReq)
	if err != nil {
		p.handleResponseError(p.getCtx(), r, resp, w, err)
		return
	}
	defer logger.Debug().Msgf("%s responding to %s, %s", fwdURL, r.RemoteAddr, resp.Status)
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		p.handleResponseError(p.getCtx(), r, resp, w, nil)
		return
	}
	p.PassResponseHeaders(w, resp)
	w.WriteHeader(resp.StatusCode)
	_, err = io.Copy(w, resp.Body)
	if err != nil {
		logger := zerolog.Ctx(p.getCtx())
		logger.Err(err).Msgf("writing body to %s", r.RemoteAddr)
	}
}

func (p *Proxy) Restart(ctx context.Context) error {
	err := p.Stop(ctx)
	if err != nil {
		return err
	}
	return p.Start(ctx)
}

func (p *Proxy) Status(_ context.Context) error {
	return nil
}

func (p *Proxy) Configure(ctx context.Context, enabled, preferV4 bool, port int16, allowedCidrs []*net.IPNet) (err error) {
	p.Lock()
	defer p.Unlock()
	p.enabled = enabled
	// TODO resolve DNS for IPv4 first if preferV4

	p.opts.FrontendAddr = net.JoinHostPort(p.selfAddr.IP.String(), strconv.Itoa(int(port)))
	p.selfAddr, err = net.ResolveTCPAddr("tcp", p.opts.FrontendAddr)
	if err != nil {
		return err
	}
	p.allowedCidrs = allowedCidrs
	return p.Restart(ctx)
}
