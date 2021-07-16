package controller

import (
	"context"
	"errors"
	"net"
	"net/url"

	capnpSrvr "capnproto.org/go/capnp/v3/server"

	"rackd/internal/metrics"
	"rackd/internal/service"
	"rackd/internal/transport"
	"rackd/pkg/dhcp"
	"rackd/pkg/rpc"
)

var (
	ErrInvalidRackController = errors.New("rack controller of invalid type")
	ErrNoRegionIPFound       = errors.New("no suitable region controller IP found")
)

// Controller is an interface for a Controller's RPC implementation
type Controller interface {
	transport.RPCHandler
	// TODO define protocl-agnostic behavior
}

type CapnpController interface {
	Controller
	Capnp() rpc.RegionController_RackController
}

// RackControllerServer is an implementation of the Capnp RackController Server
type RackControllerServer struct {
	regionIP    string
	dhcpHandler *dhcp.Handler
}

func (r *RackControllerServer) ConfigureDHCPv4(ctx context.Context, req rpc.RegionController_RackController_configureDHCPv4) error {
	return r.dhcpHandler.ConfigureDHCPv4(ctx, req, r.regionIP)
}

func (r *RackControllerServer) ConfigureDHCPv6(ctx context.Context, req rpc.RegionController_RackController_configureDHCPv6) error {
	return r.dhcpHandler.ConfigureDHCPv6(ctx, req, r.regionIP)
}

func (r *RackControllerServer) Ping(_ context.Context, _ rpc.Controller_ping) error {
	return nil
}

type RackController struct {
	capnpInterface rpc.RegionController_RackController
	rpcMgr         *transport.RPCManager
}

func NewRackController(ctx context.Context, proxyMode bool, regionURL string, sup service.SvcManager) (*RackController, error) {
	parsedUrl, err := url.Parse(regionURL)
	if err != nil {
		return nil, err
	}
	regionIP := net.ParseIP(parsedUrl.Hostname())
	if regionIP == nil {
		addrs, err := net.DefaultResolver.LookupIPAddr(ctx, parsedUrl.Hostname())
		if err != nil {
			return nil, err
		}
		if len(addrs) == 0 {
			return nil, ErrNoRegionIPFound
		}
		regionIP = addrs[0].IP
	}
	dhcpHandler, err := dhcp.NewHandler(proxyMode, sup)
	if err != nil {
		return nil, err
	}
	rc := rpc.RegionController_RackController_ServerToClient(
		&RackControllerServer{
			regionIP:    regionIP.String(),
			dhcpHandler: dhcpHandler,
		},
		&capnpSrvr.Policy{
			MaxConcurrentCalls: 32,
			AnswerQueueSize:    32,
		},
	)
	return &RackController{
		capnpInterface: rc,
	}, nil
}

func (r *RackController) Name() string {
	return "rack-controller"
}

func (r *RackController) RegisterMetrics(registry *metrics.Registry) error {
	// TODO
	return nil
}

func (r *RackController) SetupServer(_ context.Context, _ *transport.ConnWrapper) {
	// NOOP
}

func (r *RackController) UpdateConn(region string, conn *transport.ConnWrapper) {
	// TODO
}

func (r *RackController) Capnp() rpc.RegionController_RackController {
	return r.capnpInterface
}
