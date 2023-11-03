package httpproxy

import (
	"context"
	"net"
	"net/netip"
	"net/url"
)

// ipv4 implements the Proxy interface for IPv4
type ipv4 struct {
	proxyCommon
}

// NewIPv4Proxy instantiates and returns an IPv4 Proxy
func NewIPv4Proxy(opts ...ProxyOption) (Proxy, error) {
	var p ipv4

	for _, opt := range opts {
		err := opt(&p)
		if err != nil {
			return nil, err
		}
	}

	return &p, nil
}

func (p *ipv4) validateDNSName(ctx context.Context, name string) error {
	return p.proxyCommon.ValidateDNSName(ctx, net.DefaultResolver, "ip4", name)
}

// SetBindAddr validates the given address is IPv4 and sets it
// to be bound to upon a call to Listen()
func (p *ipv4) SetBindAddr(addr string) error {
	if err := p.ValidateAddr(addr); err != nil {
		return err
	}

	p.addr = addr

	return nil
}

// AddOriginURL validates the URL is valid and sets it for use as an origin
// in the proxy
func (p *ipv4) AddOriginURL(ctx context.Context, urlStr string) error {
	parsedURL, err := url.Parse(urlStr)
	if err != nil {
		return err
	}

	// Check if valid IP
	if _, err := netip.ParseAddr(parsedURL.Host); err != nil {
		// if IP is invalid, check if valid name
		if err := p.validateDNSName(ctx, parsedURL.Host); err != nil {
			return err
		}
	}

	p.origins = append(p.origins, parsedURL)

	return nil
}

// ValidateAddr asserts that the given address is a valid
// IPv4 address
func (p *ipv4) ValidateAddr(addr string) error {
	a, err := netip.ParseAddr(addr)
	if err != nil {
		return err
	}

	if !a.Is4() {
		return ErrInvalidBindAddr
	}

	return nil
}

// Listen creates an IPv4 net.Listener and begins serving HTTP
func (p *ipv4) Listen(ctx context.Context) error {
	return p.proxyCommon.Listen(ctx, p, "tcp4")
}
