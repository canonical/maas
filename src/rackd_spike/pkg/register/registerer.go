package register

import (
	"context"

	"github.com/rs/zerolog"

	machinehelpers "rackd/internal/machine_helpers"
	"rackd/internal/metrics"
	"rackd/internal/transport"
	"rackd/pkg/rpc"
)

type Registerer interface {
	transport.RPCClient
	Register(
		ctx context.Context,
		region, clusterUUID, systemId, hostname, version string,
		interfaces map[string]machinehelpers.Interface,
	) error
}

type CapnpRegisterer struct {
	clients map[string]*rpc.Registerer
}

func NewCapnpRegisterer() Registerer {
	return &CapnpRegisterer{}
}

func (c *CapnpRegisterer) Name() string {
	return "Registerer"
}

func (c *CapnpRegisterer) RegisterMetrics(registry *metrics.Registry) error {
	// TODO
	return nil
}

func (c *CapnpRegisterer) SetupClient(ctx context.Context, client *transport.ConnWrapper) {
	c.clients[client.Conn.RemoteAddr().String()] = &rpc.Registerer{Client: client.Capnp().Bootstrap(ctx)}
}

func (c *CapnpRegisterer) Register(
	ctx context.Context,
	region, clusterUUID, systemId, hostname, version string,
	interfaces map[string]machinehelpers.Interface,
) error {
	client, ok := c.clients[region]
	if !ok {
		return transport.ErrRPCClientNotFound
	}
	result, release := client.Register(ctx, func(params rpc.Registerer_register_Params) error {
		req, err := params.NewReq()
		if err != nil {
			return err
		}
		err = req.SetSystemId(systemId)
		if err != nil {
			return err
		}
		err = req.SetHostname(hostname)
		if err != nil {
			return err
		}
		ifaces, err := req.NewInterfaces()
		if err != nil {
			return err
		}
		capnpIfaces := machinehelpers.CapnpInterfaces(interfaces)
		err = capnpIfaces.SetProto(ifaces)
		if err != nil {
			return err
		}
		err = req.SetUrl(region)
		if err != nil {
			return err
		}
		err = req.SetNodegroup(clusterUUID)
		if err != nil {
			return err
		}
		req.SetBeaconSupport(true)
		err = req.SetVersion(version)
		if err != nil {
			return err
		}
		return nil
	})
	defer release()
	resp, err := result.Struct()
	if err != nil {
		return err
	}
	res, err := resp.Resp()
	if err != nil {
		return err
	}
	localId, err := res.SystemId()
	if err != nil {
		return err
	}
	// TODO set global metrics labels
	err = machinehelpers.SetMAASId(localId)
	if err != nil {
		return err
	}
	respVersion, err := res.Version()
	if err != nil {
		return err
	}
	if len(respVersion) == 0 {
		respVersion = "unknown MAAS version"
	}
	log := zerolog.Ctx(ctx)
	log.Log().Msgf("Rack controller '%s' registered (via %s) with %s.", localId, region, respVersion)
	return nil
}

func (c *CapnpRegisterer) Release() {
	for k, client := range c.clients {
		client.Release()
		delete(c.clients, k)
	}
}
