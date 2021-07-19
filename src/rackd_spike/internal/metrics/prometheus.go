package metrics

import (
	"context"
	"crypto/tls"
	"errors"
	"net"
	"net/http"
	"strconv"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/rs/zerolog/log"
)

// Registry is a wrapper around prometheus' registry object, adding a name for distinction
type Registry struct {
	prometheus.Registry
	Name string
}

type MetricsServer struct {
	server   *http.Server
	listener net.Listener
	cancel   context.CancelFunc
}

func NewRegistry(name string) *Registry {
	return &Registry{
		Registry: *prometheus.NewRegistry(),
		Name:     name,
	}
}

// NewPrometheus setups a prometheus exporter, returning the corresponding *MetricsServer for said exporter
func NewPrometheus(host string, port int, tlsConf *tls.Config, registries ...*Registry) (srvr *MetricsServer, err error) {
	srvr = &MetricsServer{}

	mux := http.NewServeMux()
	for _, registry := range registries {
		// TODO add HandlerOpts
		mux.Handle("/metrics/"+registry.Name, promhttp.HandlerFor(registry, promhttp.HandlerOpts{}))
	}
	addr := net.JoinHostPort(host, strconv.Itoa(port))
	srvr.server = &http.Server{
		Addr:      addr,
		Handler:   mux,
		TLSConfig: tlsConf,
	}
	srvr.listener, err = net.Listen("tcp", addr)
	if err != nil {
		return nil, err
	}
	if tlsConf != nil {
		srvr.listener = tls.NewListener(srvr.listener, tlsConf)
	}
	return srvr, nil
}

func (srvr *MetricsServer) Start(ctx context.Context) {
	ctx, srvr.cancel = context.WithCancel(ctx)

	go func() {
		err := srvr.server.Serve(srvr.listener)
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Err(err).Msg("failed to start metrics endpoint")
		}
	}()

	go func() {
		<-ctx.Done()
		srvr.server.Close()
	}()
}

func (srvr *MetricsServer) Stop() {
	if srvr.cancel != nil {
		srvr.cancel()
	}
}
