package httpproxy

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
)

var (
	// ErrInvalidSocketPath is an error for when an invalid path to a socket is given
	ErrInvalidSocketPath = errors.New("invalid unix socket path")
)

type socket struct {
	proxyCommon
}

// NewSocketProxy creates a Proxy for a Unix socket
func NewSocketProxy(opts ...ProxyOption) (Proxy, error) {
	var p socket

	for _, opt := range opts {
		err := opt(&p)
		if err != nil {
			return nil, err
		}
	}

	p.port = -1

	return &p, nil
}

// AddOriginURL adds a given URL to the Proxy's origins
func (p *socket) AddOriginURL(ctx context.Context, urlStr string) error {
	parsedURL, err := url.Parse(urlStr)
	if err != nil {
		return err
	}

	if len(parsedURL.Host) == 0 {
		return ErrInvalidOriginURL
	}

	p.origins = append(p.origins, parsedURL)

	return nil
}

// ValidateAddr validates the given path to a socket
func (p *socket) ValidateAddr(addr string) error {
	_, f := filepath.Split(addr)
	if len(f) == 0 {
		return ErrInvalidSocketPath
	}

	return nil
}

// SetBindAddr sets the path to a socket to bind to
func (p *socket) SetBindAddr(addr string) error {
	if err := p.ValidateAddr(addr); err != nil {
		return err
	}

	p.addr = addr

	return nil
}

// SetPort is not supported for the Socket Proxy
func (p *socket) SetPort(port int) error {
	return fmt.Errorf("%w: WithPort", ErrUnsupportedProxyOption)
}

func (p *socket) setupUnixSocket() error {
	_, err := os.Stat(p.addr)
	if err != nil {
		if os.IsNotExist(err) {
			dir, _ := filepath.Split(p.addr)

			err = os.MkdirAll(dir, 0750)
			if err != nil {
				return err
			}

			var f *os.File

			f, err = os.OpenFile(p.addr, os.O_CREATE, 0600)
			if err != nil {
				return err
			}

			defer func() {
				err = f.Close()
			}()

			return nil
		}

		return err
	}

	return nil
}

// Listen creates a socket and listens on it
func (p *socket) Listen(ctx context.Context) error {
	if p.server == nil {
		err := p.setupUnixSocket()
		if err != nil {
			return err
		}
	}

	return p.proxyCommon.Listen(ctx, p, "unix")
}

func (p *socket) cleanUnixSocket() error {
	err := os.Remove(p.addr)
	if os.IsNotExist(err) {
		return nil
	}

	return err
}

// Teardown stops the proxy and removes the socket
func (p *socket) Teardown(ctx context.Context) (err error) {
	defer func() {
		err = p.cleanUnixSocket()
	}()

	return p.proxyCommon.Teardown(ctx)
}
