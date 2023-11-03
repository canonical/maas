package httpproxy

import (
	"context"
	"net"
	"net/netip"
	"net/url"
)

// ipv6 implements the Proxy interface for IPv6
type ipv6 struct {
	proxyCommon
}

// NewIPv6Proxy instantiates a new Proxy for IPv6
func NewIPv6Proxy(opts ...ProxyOption) (Proxy, error) {
	var p ipv6

	for _, opt := range opts {
		err := opt(&p)
		if err != nil {
			return nil, err
		}
	}

	return &p, nil
}

func (p *ipv6) validateDNSName(ctx context.Context, name string) error {
	return p.proxyCommon.ValidateDNSName(ctx, net.DefaultResolver, "ip6", name)
}

// SetBindAddr validates that the given address is a valid IPv6
// address and sets it to be bound to upon calling Listen()
func (p *ipv6) SetBindAddr(addr string) error {
	if err := p.ValidateAddr(addr); err != nil {
		return err
	}

	p.addr = addr

	return nil
}

// AddOriginURL validates the given url and adds it to be used as an
// origin for the proxy
func (p *ipv6) AddOriginURL(ctx context.Context, urlStr string) error {
	parsedURL, err := url.Parse(urlStr)
	if err != nil {
		return err
	}

	// Check if valid IP
	if _, err := netip.ParseAddr(parsedURL.Host); err != nil {
		// if IP is invalid, check if valid name
		err := p.validateDNSName(ctx, parsedURL.Host)
		if err != nil {
			return err
		}
	}

	p.origins = append(p.origins, parsedURL)

	return nil
}

// ValidateAddr asserts that the given address is a valid IPv6 address
func (p *ipv6) ValidateAddr(addr string) error {
	a, err := netip.ParseAddr(addr)
	if err != nil {
		return err
	}

	if !a.Is6() {
		return ErrInvalidBindAddr
	}

	return nil
}

// Listen creates an IPv6 net.Listener and starts serving HTTP
func (p *ipv6) Listen(ctx context.Context) error {
	return p.proxyCommon.Listen(ctx, p, "tcp6")
}
