package register

import (
	"context"
	"net/url"

	"github.com/rs/zerolog"

	"rackd/internal/config"
	machinehelpers "rackd/internal/machine_helpers"
	"rackd/internal/metrics"
	"rackd/internal/transport"
	"rackd/pkg/controller"
	"rackd/pkg/rpc"
)

// Registerer is an interface for making register calls to a region controller
type Registerer interface {
	transport.RPCClient
	Register(
		ctx context.Context,
		ctrlr controller.CapnpController,
		region, clusterUUID, systemId, hostname, version string,
		interfaces map[string]machinehelpers.Interface,
	) error
}

type CapnpRegisterer struct {
	clients map[string]*rpc.RegionController
}

func NewCapnpRegisterer() Registerer {
	return &CapnpRegisterer{
		clients: make(map[string]*rpc.RegionController),
	}
}

func (c *CapnpRegisterer) Name() string {
	return "registerer"
}

func (c *CapnpRegisterer) RegisterMetrics(registry *metrics.Registry) error {
	// TODO
	return nil
}

func (c *CapnpRegisterer) SetupClient(ctx context.Context, client *transport.ConnWrapper) {
	c.clients[client.Conn.RemoteAddr().String()] = client.Capnp()
}

// Register will send the info and rack controller interface necessary for the region controller to
// register the running rack controller
func (c *CapnpRegisterer) Register(
	ctx context.Context,
	ctrlr controller.CapnpController,
	region, clusterUUID, systemId, hostname, version string,
	interfaces map[string]machinehelpers.Interface,
) error {
	regionUrl, err := url.Parse(region)
	if err != nil {
		return nil
	}
	client, ok := c.clients[regionUrl.Host]
	if !ok {
		return transport.ErrRPCClientNotFound
	}
	reg, release := client.GetRegisterer(ctx, func(params rpc.RegionController_getRegisterer_Params) error {
		return params.SetRackController(ctrlr.Capnp())
	})
	defer release()
	regClient := reg.Reg()
	result, release := regClient.Register(ctx, func(params rpc.RegionController_Registerer_register_Params) error {
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

	config.Config.SystemID = localId
	err = config.Save(ctx)
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
