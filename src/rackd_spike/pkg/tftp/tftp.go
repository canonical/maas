package tftp

import (
	"context"
	"errors"
	"sync"

	"rackd/internal/metrics"
	"rackd/internal/service"
	internal "rackd/internal/tftp"
	"rackd/internal/transport"
	"rackd/pkg/rpc"
)

var (
	ErrInvalidTFTPService = errors.New("the provided service is not a TFTP service")
)

type Client interface {
	transport.RPCClient
	GetTFTPServers(context.Context, string) error
}

type CapnpClient struct {
	sync.RWMutex
	svc            internal.TFTPService
	clients        map[string]*rpc.RegionController
	lastGoodClient string
	needReset      bool
}

func New(sup service.SvcManager) (Client, error) {
	svcs, err := sup.GetByType(service.SvcTFTP)
	if err != nil {
		return nil, err
	}
	svc, ok := svcs[0].(internal.TFTPService)
	if !ok {
		return nil, ErrInvalidTFTPService
	}
	return &CapnpClient{
		svc:     svc,
		clients: make(map[string]*rpc.RegionController),
	}, nil
}

func (c *CapnpClient) Name() string {
	return "tftp"
}

func (c *CapnpClient) RegisterMetrics(registry *metrics.Registry) error {
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

func (c *CapnpClient) GetTFTPServers(ctx context.Context, systemID string) (err error) {
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
	resp, release := client.GetTFTPServers(ctx, func(params rpc.RegionController_getTFTPServers_Params) error {
		return params.SetSystemId(systemID)
	})
	defer release()
	srvrsResp, err := resp.Struct()
	if err != nil {
		return err
	}
	srvrsList, err := srvrsResp.Servers()
	if err != nil {
		return err
	}
	servers, err := srvrsList.Servers()
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
	return c.svc.Configure(ctx, srvrs)
}
