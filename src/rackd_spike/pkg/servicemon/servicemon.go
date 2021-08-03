package servicemon

import (
	"context"
	"fmt"
	"sync"
	"time"

	"rackd/internal/config"
	"rackd/internal/metrics"
	"rackd/internal/service"
	"rackd/internal/transport"
	"rackd/pkg/rpc"

	"github.com/rs/zerolog/log"
)

type Monitor interface {
	transport.RPCClient
	Start(ctx context.Context) error
}

type CapnpClient struct {
	sync.RWMutex
	sup            service.SvcManager
	clients        map[string]*rpc.RegionController
	lastGoodClient string
	needReset      bool
	poolInterval   time.Duration
}

var rackServices = map[string]string{
	"http":        "http_proxy",
	"dhcpd":       "dhcp_relay",
	"dhcpd6":      "dhcp_relay",
	"ntp_rack":    "ntp",
	"dns_rack":    "dns",
	"proxy_rack":  "http_reverse_proxy",
	"syslog_rack": "syslog",
	"tftp":        "tftp",
	"rackd":       "rackd",
}

func New(ctx context.Context, sup service.SvcManager) (Monitor, error) {

	mon := &CapnpClient{
		sup:          sup,
		clients:      make(map[string]*rpc.RegionController),
		poolInterval: time.Duration(10) * time.Second,
	}

	return mon, mon.Start(ctx)
}

func (c *CapnpClient) Name() string {
	return "service_monitor"
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

func (c *CapnpClient) Start(ctx context.Context) error {
	ctx, cancel := context.WithCancel(ctx)

	go func() {
		ticker := time.NewTicker(c.poolInterval)

		for {
			select {
			case <-ticker.C:
				if config.Config.SystemID != "" {
					err := c.update(ctx, config.Config.SystemID)
					if err != nil {
						log.Ctx(ctx).Err(err).Msg("failed to update services status")
					}
				}
			case <-ctx.Done():
				ticker.Stop()
				cancel()
				return
			}
		}
	}()
	return nil
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

func (c *CapnpClient) update(ctx context.Context, systemID string) (err error) {
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
	resp, release := client.UpdateService(ctx, func(params rpc.RegionController_updateService_Params) error {
		req, err := params.NewMsg()
		if err != nil {
			return err
		}
		err = req.SetSystemId(systemID)
		if err != nil {
			return err
		}

		statuses := c.sup.GetStatusMap(ctx)

		lst, err := req.NewServices(int32(len(rackServices)))
		if err != nil {
			return err
		}

		var idx int
		for rackName, ourName := range rackServices {
			s := lst.At(idx)

			err := s.SetName(rackName)
			if err != nil {
				return err
			}

			var status, status_info string
			if st, ok := statuses[ourName]; ok {
				status = st
				status_info = fmt.Sprintf("service %s is %s", rackName, st)
			} else {
				status = "off"
				status_info = fmt.Sprintf("service %s is unknown", rackName)
			}

			err = s.SetStatus(status)
			if err != nil {
				return err
			}
			err = s.SetStatusInfo(status_info)
			if err != nil {
				return err
			}

			idx++
		}
		return nil
	})
	defer release()
	<-resp.Done()
	return nil
}
