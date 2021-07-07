package authenticate

import (
	"bytes"
	"context"
	"fmt"

	"rackd/internal/metrics"
	"rackd/internal/transport"
	"rackd/pkg/rpc"
)

type AuthCreds struct {
	Salt   []byte
	Digest []byte
}

func (c *AuthCreds) localDigest(secret, message []byte) []byte {
	// TODO
	return nil
}

func (c *AuthCreds) Verify(secret, message []byte) bool {
	return bytes.Compare(c.Digest, c.localDigest(secret, message)) == 0
}

type Authenticator interface {
	transport.RPCClient
	Authenticate(context.Context, string, []byte, []byte) (*AuthCreds, error)
}

type CapnpAuthenticator struct {
	clients map[string]*rpc.Authenticator
}

func NewCapnpAuthenticator() Authenticator {
	// Perhaps we should initialize this with the shared secret already loaded either
	// from the config manager or load from the FS on instantiation?
	return &CapnpAuthenticator{
		clients: make(map[string]*rpc.Authenticator),
	}
}

func (c *CapnpAuthenticator) Name() string {
	return "authenticator"
}

func (c *CapnpAuthenticator) RegisterMetrics(registry *metrics.Registry) error {
	// TODO
	return nil
}

func (c *CapnpAuthenticator) SetupClient(ctx context.Context, conn *transport.ConnWrapper) {
	c.clients[conn.Conn.RemoteAddr().String()] = &rpc.Authenticator{Client: conn.Capnp().Bootstrap(ctx)}
}

func (c *CapnpAuthenticator) Authenticate(ctx context.Context, region string, secret, message []byte) (*AuthCreds, error) {
	regionClient, ok := c.clients[region]
	if !ok {
		return nil, fmt.Errorf("%w: %s", transport.ErrRPCClientNotFound, region)
	}
	result, release := regionClient.Authenticate(ctx, func(params rpc.Authenticator_authenticate_Params) error {
		return params.SetMsg(message)
	})
	defer release()
	resp, err := result.Struct()
	if err != nil {
		return nil, err
	}
	creds, err := resp.Resp()
	if err != nil {
		return nil, err
	}
	salt, err := creds.Salt()
	if err != nil {
		return nil, err
	}
	digest, err := creds.Digest()
	if err != nil {
		return nil, err
	}
	return &AuthCreds{
		Salt:   salt,
		Digest: digest,
	}, nil
}

func (c *CapnpAuthenticator) Release() {
	for k, client := range c.clients {
		client.Release()
		delete(c.clients, k)
	}
}
