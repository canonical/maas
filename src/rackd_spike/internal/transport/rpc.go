package transport

import (
	"context"
	"crypto/tls"
	"errors"
	"net"
	"net/url"

	capnprpc "capnproto.org/go/capnp/v3/rpc"
	"github.com/rs/zerolog"

	"rackd/internal/metrics"
)

var (
	ErrRPCClientNotFound = errors.New("error client not found")
)

type RPCHandler interface {
	Name() string
	RegisterMetrics(*metrics.Registry) error
	SetupServer(context.Context, *ConnWrapper)
}

type RPCClient interface {
	Name() string
	RegisterMetrics(*metrics.Registry) error
	SetupClient(context.Context, *ConnWrapper)
}

type CapnpRPCClient interface {
	RPCClient
	Release()
}

type ConnWrapper struct {
	Conn      net.Conn
	capnpConn *capnprpc.Conn
}

func NewConnWrapper(conn net.Conn) *ConnWrapper {
	return &ConnWrapper{
		Conn:      conn,
		capnpConn: capnprpc.NewConn(capnprpc.NewStreamTransport(conn), nil),
	}
}

func (c *ConnWrapper) Capnp() *capnprpc.Conn {
	return c.capnpConn
}

type RPCManager struct {
	conns          map[string]*ConnWrapper
	handlers       map[string]RPCHandler
	clients        map[string]RPCClient
	initURL        string
	skipHostVerify bool
}

func NewRPCManager(rpcServerURL string, skipHostVerify bool) *RPCManager {
	return &RPCManager{
		conns:          make(map[string]*ConnWrapper),
		handlers:       make(map[string]RPCHandler),
		clients:        make(map[string]RPCClient),
		initURL:        rpcServerURL,
		skipHostVerify: skipHostVerify,
	}
}

// Init initiates the initial region connection
func (r *RPCManager) Init(ctx context.Context) error {
	parsedURL, err := url.Parse(r.initURL)
	if err != nil {
		return err
	}
	var conn net.Conn
	if parsedURL.Scheme == "https" {
		conn, err = tls.Dial(
			"tcp",
			net.JoinHostPort(parsedURL.Hostname(), parsedURL.Port()),
			&tls.Config{InsecureSkipVerify: r.skipHostVerify},
		)
	} else {
		conn, err = net.Dial("tcp", net.JoinHostPort(parsedURL.Hostname(), parsedURL.Port()))
	}
	if err != nil {
		return err
	}
	r.AddConn(ctx, conn)
	log := zerolog.Ctx(ctx)
	log.Debug().Msg("connected to region server")
	return nil
}

func (r *RPCManager) AddHandler(ctx context.Context, handler RPCHandler) {
	r.handlers[handler.Name()] = handler
	for _, conn := range r.conns {
		handler.SetupServer(ctx, conn)
	}
}

func (r *RPCManager) AddClient(ctx context.Context, client RPCClient) {
	r.clients[client.Name()] = client
	for _, conn := range r.conns {
		client.SetupClient(ctx, conn)
	}
}

func (r *RPCManager) AddConn(ctx context.Context, conn net.Conn) {
	newConn := NewConnWrapper(conn)
	r.conns[conn.RemoteAddr().String()] = newConn
	for _, handler := range r.handlers {
		handler.SetupServer(ctx, newConn)
	}
	for _, client := range r.clients {
		client.SetupClient(ctx, newConn)
	}
}

func (r *RPCManager) GetClient(clientName string) (RPCClient, error) {
	c, ok := r.clients[clientName]
	if !ok {
		return nil, ErrRPCClientNotFound
	}
	return c, nil
}
