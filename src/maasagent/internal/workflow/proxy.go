package workflow

import (
	"context"
	"errors"
	"fmt"
	"net"
	"os"
	"path"

	zlog "github.com/rs/zerolog"
	"go.temporal.io/sdk/activity"
	temporallog "go.temporal.io/sdk/log"

	"maas.io/core/src/maasagent/internal/httpproxy"
	"maas.io/core/src/maasagent/internal/imagecache"
	maaslog "maas.io/core/src/maasagent/internal/workflow/log"
)

const (
	nginxActive    = true
	socketFileName = "agent-http-proxy.sock"
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
	Proxies             *httpproxy.ProxyGroup
	ready               chan struct{}
	imageCacheLocation  string
	proxySocketLocation string
	imageCacheSize      int64
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

func (p *HTTPProxyConfigurator) SetCacheSize(s int64) {
	p.imageCacheSize = s
}

// ConfigureHTTPProxy is a Temporal activity to configure the HTTP proxy
func (p *HTTPProxyConfigurator) ConfigureHTTPProxy(ctx context.Context, param configureHTTPProxyParam) error {
	var log temporallog.Logger

	if activity.IsActivity(ctx) {
		log = activity.GetLogger(ctx)
	} else {
		log = maaslog.NewZerologAdapter(zlog.Nop())
	}

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

	bootloaderRegistry := imagecache.NewBootloaderRegistry(nil, "")

	err = bootloaderRegistry.LinkAll()
	if err != nil {
		return err
	}

	cache, err := imagecache.NewFSCache(p.imageCacheSize, p.imageCacheLocation)
	if err != nil {
		return err
	}

	if nginxActive {
		log.Debug("Creating Unix Socket HTTP Proxy")

		var sockPath string
		if p.proxySocketLocation != "" {
			sockPath = p.proxySocketLocation
		} else {
			sockPath = getSocketFilePath()
		}

		socketOpts := []httpproxy.ProxyOption{
			httpproxy.WithBindAddr(sockPath),
			httpproxy.WithBootloaderRegistry(bootloaderRegistry),
			httpproxy.WithImageCache(cache),
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
			httpproxy.WithBootloaderRegistry(bootloaderRegistry),
			httpproxy.WithImageCache(cache),
		}
		ipv4Opts = append(ipv4Opts, originOpts...)

		log.Debug("Creating IPv6 HTTP Proxy")

		ipv6Opts := []httpproxy.ProxyOption{
			httpproxy.WithBindAddr("::"),
			httpproxy.WithPort(5258),
			httpproxy.WithBootloaderRegistry(bootloaderRegistry),
			httpproxy.WithImageCache(cache),
		}
		ipv6Opts = append(ipv6Opts, originOpts...)
		groupOpts = append(
			groupOpts,
			httpproxy.WithIPv4(ipv4Opts...),
			httpproxy.WithIPv6(ipv6Opts...),
		)
	}

	if p.Proxies != nil && p.Proxies.Size() > 0 {
		err = p.Proxies.Teardown(ctx)
		if err != nil {
			log.Error(err.Error())
		}
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

func getSocketFilePath() string {
	if os.Getenv("SNAP") == "" {
		return fmt.Sprintf("/var/lib/maas/%s", socketFileName)
	}

	return path.Join(
		os.Getenv("SNAP_DATA"),
		socketFileName,
	)
}
