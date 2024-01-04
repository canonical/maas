package workflow

import (
	"context"
	"errors"
	"net"
	"os"
	"path"

	"go.temporal.io/sdk/activity"

	"maas.io/core/src/maasagent/internal/httpproxy"
)

const (
	nginxActive       = true
	defaultSocketPath = "/var/lib/maas/http_proxy.sock"
)

var (
	// ErrNotIP is an error for when the received config is not an IP
	ErrNotIP = errors.New("the given address is not an IP")
)

type configureHTTPProxyParam struct {
	Endpoints []struct {
		Endpoint string
		Subnet   string
	}
}

// HTTPProxyConfigurator provides the Configurator interface
// for the agent's HTTP proxy, configuring the proxy with the
// appropriate info from the region
type HTTPProxyConfigurator struct {
	ready   chan struct{}
	Proxies *httpproxy.ProxyGroup
}

// NewHTTPProxyConfigurator returns a new HTTPProxy Configurator
func NewHTTPProxyConfigurator() *HTTPProxyConfigurator {
	return &HTTPProxyConfigurator{
		ready: make(chan struct{}),
	}
}

// Ready returns a channel for waiting for the proxy to be ready
func (p *HTTPProxyConfigurator) Ready() <-chan struct{} {
	return p.ready
}

// ConfigureHTTPProxy is a Temporal activity to configure the HTTP proxy
func (p *HTTPProxyConfigurator) ConfigureHTTPProxy(ctx context.Context, param configureHTTPProxyParam) error {
	log := activity.GetLogger(ctx)

	var (
		originOpts []httpproxy.ProxyOption
		groupOpts  []httpproxy.ProxyGroupOption
	)

	ifaces, err := net.Interfaces()
	if err != nil {
		return err
	}

	for _, iface := range ifaces {
		if iface.Flags&net.FlagUp == 0 || iface.Flags&net.FlagLoopback != 0 {
			continue
		}

		var (
			addrs, multicastAddrs []net.Addr
		)

		addrs, err = iface.Addrs()
		if err != nil {
			return err
		}

		multicastAddrs, err = iface.MulticastAddrs()
		if err != nil {
			return err
		}

		for _, addr := range append(addrs, multicastAddrs...) {
			var ip net.IP

			switch addrCast := addr.(type) {
			case *net.IPAddr:
				ip = addrCast.IP
			case *net.IPNet:
				ip = addrCast.IP
			default:
				return ErrNotIP
			}

			for _, endpoint := range param.Endpoints {
				var subnet *net.IPNet

				_, subnet, err = net.ParseCIDR(endpoint.Subnet)
				if err != nil {
					return err
				}

				if subnet.Contains(ip) {
					originOpts = append(originOpts, httpproxy.WithOrigin(ctx, endpoint.Endpoint))
				}
			}
		}
	}

	if nginxActive {
		log.Debug("Creating Unix Socket HTTP Proxy")

		socketOpts := []httpproxy.ProxyOption{
			httpproxy.WithBindAddr(
				path.Join(
					os.Getenv("SNAP_DATA"),
					defaultSocketPath,
				),
			),
		}
		socketOpts = append(socketOpts, originOpts...)
		groupOpts = append(
			groupOpts,
			httpproxy.WithSocket(socketOpts...),
		)
	} else {
		// TODO fetch TLS config
		log.Debug("Creating IPv4 HTTP Proxy")

		ipv4Opts := []httpproxy.ProxyOption{
			httpproxy.WithBindAddr("0.0.0.0"),
			httpproxy.WithPort(5258),
		}
		ipv4Opts = append(ipv4Opts, originOpts...)

		log.Debug("Creating IPv6 HTTP Proxy")

		ipv6Opts := []httpproxy.ProxyOption{
			httpproxy.WithBindAddr("::"),
			httpproxy.WithPort(5258),
		}
		ipv6Opts = append(ipv6Opts, originOpts...)
		groupOpts = append(
			groupOpts,
			httpproxy.WithIPv4(ipv4Opts...),
			httpproxy.WithIPv6(ipv6Opts...),
		)
	}

	p.Proxies, err = httpproxy.NewProxyGroup(groupOpts...)
	if err != nil {
		log.Error(err.Error())
	}

	p.ready <- struct{}{}

	return err
}

// CreateConfigActivity provides Configurator behaviour for the HTTP proxy
func (p *HTTPProxyConfigurator) CreateConfigActivity() interface{} {
	return p.ConfigureHTTPProxy
}
