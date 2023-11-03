package httpproxy

import (
	"context"
	"crypto/rand"
	"crypto/tls"
	"math/big"
	"net"
	"net/http"
	"net/url"
	"strconv"
	"time"
)

const (
	defaultReadHeaderTimeout = 30 * time.Second
)

// proxyCommon is a struct intended to be embedded into
// proxy structs for common functionality
type proxyCommon struct {
	handlerOverride http.Handler
	listener        net.Listener
	serverTLS       *tls.Config
	clientTLS       *tls.Config
	server          *http.Server
	addr            string
	origins         []*url.URL
	port            int
	keepalive       time.Duration
}

// ValidateDNSName uses a given resolver to verify a configured name is a valid DNS record
func (p proxyCommon) ValidateDNSName(ctx context.Context, resolver *net.Resolver, network, name string) error {
	_, err := resolver.LookupIP(ctx, network, name)
	return err
}

// SetKeepalive sets the server-side keepalive time
func (p *proxyCommon) SetKeepalive(d time.Duration) {
	p.keepalive = d
}

// SetServerTLSConfig sets the given *tls.Config to be used for serving the proxy
func (p *proxyCommon) SetServerTLSConfig(cfg *tls.Config) {
	p.serverTLS = cfg
}

// SetUpstreamTLSConfig sets the given *tls.Config to be used for communicating
// with origins
func (p *proxyCommon) SetUpstreamTLSConfig(cfg *tls.Config) {
	p.clientTLS = cfg
}

// SetHandlerOverride allows the caller to override the default HTTP handler
// behaviour
func (p *proxyCommon) SetHandlerOverride(h http.Handler) {
	p.handlerOverride = h
}

// SetPort sets the port of the listener for the proxy
func (p *proxyCommon) SetPort(port int) error {
	p.port = port
	return nil
}

// Listen creates a net.Listener and begins serving HTTP on it
func (p *proxyCommon) Listen(ctx context.Context, proxy Proxy, network string) error {
	if p.server != nil {
		return ErrProxyAlreadyListening
	}

	var handler http.Handler
	if p.handlerOverride != nil {
		handler = p.handlerOverride
	} else {
		handler = DefaultHandler(proxy)
	}

	addr := p.addr

	// not unix socket
	if p.port > -1 {
		portStr := strconv.Itoa(p.port)
		addr = net.JoinHostPort(p.addr, portStr)
	}

	var err error

	p.listener, err = net.Listen(network, addr)
	if err != nil {
		return err
	}

	if p.serverTLS != nil {
		p.listener = tls.NewListener(p.listener, p.serverTLS)
	}

	p.server = &http.Server{
		Addr:                         addr,
		Handler:                      handler,
		DisableGeneralOptionsHandler: true,
		IdleTimeout:                  p.keepalive,
		ReadHeaderTimeout:            defaultReadHeaderTimeout,
	}

	if p.keepalive > 0 {
		p.server.SetKeepAlivesEnabled(true)
	}

	return p.server.Serve(p.listener)
}

// Teardown stops the proxy
func (p *proxyCommon) Teardown(ctx context.Context) error {
	if p.server == nil {
		return ErrProxyNotRunning
	}

	err := p.server.Shutdown(ctx)
	if err != nil {
		return err
	}

	p.server = nil

	return nil
}

// GetOrigin returns a random origin URL
func (p proxyCommon) GetOrigin() (*url.URL, error) {
	idx, err := rand.Int(rand.Reader, big.NewInt(int64(len(p.origins))))
	if err != nil {
		return nil, err
	}

	return p.origins[int(idx.Int64())], nil
}

// GetClient returns a properly configured HTTP client
func (p proxyCommon) GetClient() *http.Client {
	transport := http.DefaultTransport

	if p.clientTLS != nil {
		transport = &http.Transport{
			TLSClientConfig: p.clientTLS,
		}
	}

	return &http.Client{
		Transport: transport,
	}
}
