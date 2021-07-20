package ntp

import (
	"context"
	"errors"
	"sync"

	"rackd/internal/metrics"
	internal "rackd/internal/ntp"
	"rackd/internal/service"
	"rackd/internal/transport"
	"rackd/pkg/rpc"
)

var (
	ErrInvalidNTPService = errors.New("error invalid ntp service")
)

type Client interface {
	transport.RPCClient
	GetTimeConfiguration(context.Context, string) error
}

type CapnpClient struct {
	sync.RWMutex
	svc            internal.NTPService
	clients        map[string]*rpc.RegionController
	lastGoodClient string
	needReset      bool
}

func New(sup service.SvcManager) (Client, error) {
	svcs, err := sup.GetByType(service.SvcNTP)
	if err != nil {
		return nil, err
	}
	svc, ok := svcs[0].(internal.NTPService)
	if !ok {
		return nil, ErrInvalidNTPService
	}
	return &CapnpClient{
		svc:     svc,
		clients: make(map[string]*rpc.RegionController),
	}, nil
}

func (c *CapnpClient) Name() string {
	return "ntp"
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
	c.RLock()
	defer c.RUnlock()
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

func (c *CapnpClient) GetTimeConfiguration(ctx context.Context, systemID string) (err error) {
	client, err := c.getClient(c.needReset)
	if err != nil {
		return err
	}
	defer func() {
		if err != nil {
			c.Lock()
			defer c.Unlock()
			c.needReset = true
		}
	}()
	resp, release := client.GetTimeConfiguration(ctx, func(params rpc.RegionController_getTimeConfiguration_Params) error {
		return params.SetSystemId(systemID)
	})
	defer release()
	cfgResp, err := resp.Struct()
	if err != nil {
		return err
	}
	cfg, err := cfgResp.Resp()
	if err != nil {
		return err
	}
	servers, err := cfg.Servers()
	if err != nil {
		return err
	}
	srvrs := make([]string, servers.Len())
	for i := 0; i < servers.Len(); i++ {
		srvrs[i], err = servers.At(i)
		if err != nil {
			return err
		}
	}
	peers, err := cfg.Peers()
	if err != nil {
		return err
	}
	prs := make([]string, peers.Len())
	for i := 0; i < peers.Len(); i++ {
		prs[i], err = peers.At(i)
		if err != nil {
			return err
		}
	}
	err = c.svc.Configure(ctx, srvrs, prs)
	if err != nil {
		return err
	}
	return c.svc.Restart(ctx)
}
