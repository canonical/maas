package httpproxy

import (
	"context"
	"crypto/tls"
	"errors"
	"net/http"
	"net/url"
	"time"

	"golang.org/x/sync/errgroup"
)

var (
	// ErrInvalidBindAddr is an error for when the configured address for a proxy to bind to
	// is invalid
	ErrInvalidBindAddr = errors.New("the provided proxy address to bind to is invalid")
	// ErrProxyAlreadyListening is an error for when the Proxy has already been started and is listening
	ErrProxyAlreadyListening = errors.New("the proxy is already listening")
	// ErrProxyNotRunning is an error for when something for a running Proxy is accessed on a non-running
	// Proxy
	ErrProxyNotRunning = errors.New("the proxy is not currently running")
	// ErrUnsupportedProxyOption is an error for an option being set on a Proxy that isn't supported
	ErrUnsupportedProxyOption = errors.New("an unsupported proxy option was given")
	// ErrInvalidOriginURL is an error for when an invalid origin is provided
	ErrInvalidOriginURL = errors.New("the given origin URL is invalid")
)

// ProxyGroupOption is a type for options that apply to ProxyGroups
type ProxyGroupOption func(ProxyGroup) error

// ProxyOption is a type for options that apply to Proxies
type ProxyOption func(Proxy) error

// proxyConstructor is a type for functions that instantiate Proxies
type proxyConstructor func(...ProxyOption) (Proxy, error)

// ProxyListener is an interface defining methods for Proxy listening
// behaviour
type ProxyListener interface {
	Listen(context.Context) error
	Teardown(context.Context) error
}

// ProxyClient is an interface defining methods for Proxy client
// behaviour
type ProxyClient interface {
	GetOrigin() (*url.URL, error)
	GetClient() *http.Client
}

// Proxy is an interface defining behaviour for proxying images
type Proxy interface {
	ProxyClient
	ProxyListener
	AddOriginURL(context.Context, string) error
	SetBindAddr(string) error
	ValidateAddr(string) error
	SetKeepalive(time.Duration)
	SetPort(int) error
	SetServerTLSConfig(*tls.Config)
	SetUpstreamTLSConfig(*tls.Config)
	SetHandlerOverride(http.Handler)
}

// ProxyGroup is a group of Proxies, this may consist of IPv4, IPv6 and
// Unix socket proxies
type ProxyGroup []Proxy

// Listen calls each Proxy's Listen() in an errgroup
func (pg ProxyGroup) Listen(ctx context.Context) error {
	errGroup, ctx := errgroup.WithContext(ctx)

	for _, p := range pg {
		errGroup.Go(func(proxy Proxy) func() error {
			return func() error {
				return proxy.Listen(ctx)
			}
		}(p))
	}

	return errGroup.Wait()
}

// Teardown tears down each Proxy in an errgroup
func (pg ProxyGroup) Teardown(ctx context.Context) error {
	errGroup, ctx := errgroup.WithContext(ctx)

	for _, p := range pg {
		errGroup.Go(func(proxy Proxy) func() error {
			return func() error {
				return proxy.Teardown(ctx)
			}
		}(p))
	}

	return errGroup.Wait()
}

// WithOrigin adds an origin URL to a given Proxy
func WithOrigin(ctx context.Context, url string) ProxyOption {
	return func(p Proxy) error {
		return p.AddOriginURL(ctx, url)
	}
}

// WithBindAddr sets the address for a Proxy to bind to
func WithBindAddr(addr string) ProxyOption {
	return func(p Proxy) error {
		return p.SetBindAddr(addr)
	}
}

// WithPort sets the port for a Proxy to listen on
func WithPort(port int) ProxyOption {
	return func(p Proxy) error {
		return p.SetPort(port)
	}
}

// WithServerTLS creates a *tls.Config with the given cert and key
// for the Proxy to serve
func WithServerTLS(certPath, keyPath string) ProxyOption {
	return func(p Proxy) error {
		keyPair, err := tls.LoadX509KeyPair(certPath, keyPath)
		if err != nil {
			return err
		}

		config := &tls.Config{
			Certificates: []tls.Certificate{keyPair},
			MinVersion:   tls.VersionTLS13,
		}

		p.SetServerTLSConfig(config)

		return nil
	}
}

// WithClientTLS creates a *tls.Config with the given cert and key (empty string will disable mutual TLS auth)
// and set skipping host verification
func WithClientTLS(certPath, keyPath string, skipVerify bool) ProxyOption {
	return func(p Proxy) error {
		keyPair, err := tls.LoadX509KeyPair(certPath, keyPath)
		if err != nil {
			return err
		}

		config := &tls.Config{
			Certificates: []tls.Certificate{keyPair},
			//nolint:gosec // gosec does not allow skipping host verification
			InsecureSkipVerify: skipVerify,
			MinVersion:         tls.VersionTLS13,
		}

		p.SetUpstreamTLSConfig(config)

		return nil
	}
}

// WithHandler will override the default handler of a Proxy
func WithHandler(h http.Handler) ProxyOption {
	return func(p Proxy) error {
		p.SetHandlerOverride(h)

		return nil
	}
}

func withProxy(newProxy proxyConstructor, opts ...ProxyOption) ProxyGroupOption {
	return func(pg ProxyGroup) error {
		proxy, err := newProxy(opts...)
		if err != nil {
			return err
		}

		//nolint:staticcheck // SA4006 pg marked unused however it is being modified
		pg = append(pg, proxy)

		return nil
	}
}

// WithIPv4 adds an IPv4 Proxy to the ProxyGroup
func WithIPv4(opts ...ProxyOption) ProxyGroupOption {
	return withProxy(NewIPv4Proxy, opts...)
}

// WithIPv6 adds an IPv6 Proxy to the ProxyGroup
func WithIPv6(opts ...ProxyOption) ProxyGroupOption {
	return withProxy(NewIPv6Proxy, opts...)
}

// WithSocket adds an Unix socket Proxy to the ProxyGroup
func WithSocket(opts ...ProxyOption) ProxyGroupOption {
	return withProxy(NewSocketProxy, opts...)
}

// NewProxyGroup creates a ProxyGroup with the given set of options
func NewProxyGroup(opts ...ProxyGroupOption) (ProxyGroup, error) {
	var pg ProxyGroup

	for _, opt := range opts {
		err := opt(pg)
		if err != nil {
			return nil, err
		}
	}

	return pg, nil
}
