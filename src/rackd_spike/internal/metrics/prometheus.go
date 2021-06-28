package metrics

import (
	"crypto/tls"
	"net"
	"net/http"
	"strconv"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

type Registry struct {
	prometheus.Registry
	Name string
}

func NewRegistry(name string) *Registry {
	return &Registry{
		Registry: *prometheus.NewRegistry(),
		Name:     name,
	}
}

func NewPrometheus(host string, port int, tlsConf *tls.Config, registries ...*Registry) (*http.Server, error) {
	mux := http.NewServeMux()
	for _, registry := range registries {
		// TODO add HandlerOpts
		mux.Handle("/metrics/"+registry.Name, promhttp.HandlerFor(registry, promhttp.HandlerOpts{}))
	}
	addr := net.JoinHostPort(host, strconv.Itoa(port))
	srvr := &http.Server{
		Addr:      addr,
		Handler:   mux,
		TLSConfig: tlsConf,
	}
	listener, err := net.Listen("tcp", addr)
	if err != nil {
		return nil, err
	}
	if tlsConf != nil {
		listener = tls.NewListener(listener, tlsConf)
	}
	go srvr.Serve(listener)
	return srvr, nil
}
