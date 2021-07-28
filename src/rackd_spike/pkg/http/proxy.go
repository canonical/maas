package http

import (
	"context"
	"net"
	internal "rackd/internal/http"
	"rackd/internal/metrics"
	"rackd/internal/service"
	"rackd/internal/transport"
	"rackd/pkg/rpc"
	"sync"
)

type Client interface {
	transport.RPCClient
	GetProxyConfiguration(context.Context, string) error
}

type CapnpClient struct {
	sync.Mutex
	svc            internal.ProxyService
	clients        map[string]*rpc.RegionController
	lastGoodClient string
	needReset      bool
}

func New(sup service.SvcManager) (Client, error) {
	svcs, err := sup.GetByType(service.SvcPROXY)
	if err != nil {
		return nil, err
	}
	svc, ok := svcs[0].(internal.ProxyService)
	if !ok {

	}
	return &CapnpClient{
		svc:     svc,
		clients: make(map[string]*rpc.RegionController),
	}, nil
}

func (c *CapnpClient) Name() string {
	return "http"
}

func (c *CapnpClient) RegisterMetrics(registry *metrics.Registry) error {
	// TODO
	return nil
}

func (c *CapnpClient) SetupClient(ctx context.Context, client *transport.ConnWrapper) {
	c.Lock()
	defer c.Unlock()
	c.clients[client.Conn.RemoteAddr().String()] = client.Capnp()
}

func (c *CapnpClient) getClient(reset bool) (*rpc.RegionController, error) {
	c.Lock()
	defer c.Unlock()
	if len(c.clients) == 0 {
		return nil, transport.ErrRPCClientNotFound
	}
	if !reset && len(c.lastGoodClient) > 0 {
		return c.clients[c.lastGoodClient], nil
	}
	for k, v := range c.clients {
		c.lastGoodClient = k
		return v, nil
	}
	return nil, transport.ErrRPCClientNotFound
}

func (c *CapnpClient) GetProxyConfiguration(ctx context.Context, systemID string) error {
	client, err := c.getClient(c.needReset)
	if err != nil {
		return err
	}
	resp, release := client.GetProxyConfiguration(ctx, func(params rpc.RegionController_getProxyConfiguration_Params) error {
		return params.SetSystemId(systemID)
	})
	defer release()
	cfgResp, err := resp.Struct()
	if err != nil {
		return err
	}
	cfg, err := cfgResp.ProxyConfig()
	if err != nil {
		return err
	}
	enabled := cfg.Enabled()
	preferV4 := cfg.PreferV4Proxy()
	port := cfg.Port()
	allowedCidrsProto, err := cfg.AllowedCidrs()
	if err != nil {
		return err
	}
	allowedCidrs := make([]*net.IPNet, allowedCidrsProto.Len())
	for i := 0; i < allowedCidrsProto.Len(); i++ {
		cidrProto, err := allowedCidrsProto.At(i)
		if err != nil {
			return err
		}
		_, cidr, err := net.ParseCIDR(cidrProto)
		if err != nil {
			return err
		}
		allowedCidrs[i] = cidr
	}
	return c.svc.Configure(ctx, enabled, preferV4, port, allowedCidrs)
}
