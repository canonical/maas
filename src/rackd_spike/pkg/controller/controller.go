package controller

import (
	"context"
	"errors"

	capnpSrvr "capnproto.org/go/capnp/v3/server"

	"rackd/internal/metrics"
	"rackd/internal/transport"
	"rackd/pkg/rpc"
)

var (
	ErrInvalidRackController = errors.New("rack controller of invalid type")
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
}

func (r *RackControllerServer) Todo(_ context.Context, _ rpc.RegionController_RackController_todo) error {
	return nil
}

func (r *RackControllerServer) Ping(_ context.Context, _ rpc.Controller_ping) error {
	return nil
}

type RackController struct {
	capnpInterface rpc.RegionController_RackController
	rpcMgr         *transport.RPCManager
}

func NewRackController() *RackController {
	rc := rpc.RegionController_RackController_ServerToClient(
		&RackControllerServer{},
		&capnpSrvr.Policy{
			MaxConcurrentCalls: 32,
			AnswerQueueSize:    32,
		},
	)
	return &RackController{
		capnpInterface: rc,
	}
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
