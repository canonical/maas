package authenticate

import (
	"bytes"
	"context"
	"fmt"
	"net/url"

	"rackd/internal/metrics"
	"rackd/internal/transport"
	"rackd/pkg/rpc"
)

// AuthCreds contains the credentials returned from the server
type AuthCreds struct {
	Salt   []byte
	Digest []byte
}

// local digest calculates the digest of the secret and generated message
func (c *AuthCreds) localDigest(secret, message []byte) []byte {
	// TODO
	return nil
}

// Verify verifies that both the local digest and the digest returned from the server match
func (c *AuthCreds) Verify(secret, message []byte) bool {
	return bytes.Compare(c.Digest, c.localDigest(secret, message)) == 0
}

// Authenticator is an interface for making calls to authenticate with a server
type Authenticator interface {
	transport.RPCClient
	Authenticate(context.Context, string, []byte, []byte) (*AuthCreds, error)
}

type CapnpAuthenticator struct {
	clients map[string]*rpc.RegionController
}

func NewCapnpAuthenticator() Authenticator {
	// Perhaps we should initialize this with the shared secret already loaded either
	// from the config manager or load from the FS on instantiation?
	return &CapnpAuthenticator{
		clients: make(map[string]*rpc.RegionController),
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
	c.clients[conn.Conn.RemoteAddr().String()] = conn.Capnp()
}

func (c *CapnpAuthenticator) Authenticate(ctx context.Context, region string, secret, message []byte) (*AuthCreds, error) {
	regionUrl, err := url.Parse(region)
	if err != nil {
		return nil, err
	}
	regionClient, ok := c.clients[regionUrl.Host]
	if !ok {
		return nil, fmt.Errorf("%w: %s", transport.ErrRPCClientNotFound, regionUrl.Host)
	}
	auth, release := regionClient.GetAuthenticator(ctx, func(params rpc.RegionController_getAuthenticator_Params) error {
		return nil
	})
	defer release()
	authClient := auth.Auth()
	result, release := authClient.Authenticate(ctx, func(params rpc.RegionController_Authenticator_authenticate_Params) error {
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
