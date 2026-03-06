// Copyright (c) 2026 Canonical Ltd
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

package daemon

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"os"
	"time"

	"github.com/cenkalti/backoff/v4"
	"go.opentelemetry.io/otel/metric"
	temporalenum "go.temporal.io/api/enums/v1"
	temporalclient "go.temporal.io/sdk/client"
	"golang.org/x/sync/errgroup"
	"maas.io/core/src/maasagent/internal/apiclient"
	"maas.io/core/src/maasagent/internal/cache"
	"maas.io/core/src/maasagent/internal/certutil"
	"maas.io/core/src/maasagent/internal/client"
	"maas.io/core/src/maasagent/internal/cluster"
	"maas.io/core/src/maasagent/internal/dhcp"
	"maas.io/core/src/maasagent/internal/httpproxy"
	"maas.io/core/src/maasagent/internal/pathutil"
	"maas.io/core/src/maasagent/internal/power"
	"maas.io/core/src/maasagent/internal/resolver"
	"maas.io/core/src/maasagent/internal/servicecontroller"
	"maas.io/core/src/maasagent/internal/temporal"
	"maas.io/core/src/maasagent/internal/workflow/worker"
)

type powerSvcConfig struct {
	pool      *worker.WorkerPool
	agentUUID string
	// TODO: systemID should be removed.
	systemID string
}

func newPowerService(c powerSvcConfig) (*power.PowerService, error) {
	return power.NewPowerService(c.systemID, c.pool), nil
}

type clusterSvcConfig struct {
	meter     metric.Meter
	agentUUID string
	// TODO: systemID should be removed.
	systemID string
}

func newClusterService(c clusterSvcConfig) (*cluster.ClusterService, error) {
	return cluster.NewClusterService(
		c.systemID,
		cluster.WithMetricMeter(c.meter),
	)
}

type resolverSvcConfig struct {
	meter metric.Meter
	DNSConfig
}

func newResolverService(cfg resolverSvcConfig) (*resolver.ResolverService, error) {
	resolverCache, err := resolver.NewCache(
		resolver.WithMaxSize(cfg.Cache.Size.Bytes),
		resolver.WithCacheMetrics(cfg.meter),
	)
	if err != nil {
		return nil, err
	}

	resolverHandler := resolver.NewRecursiveHandler(
		resolverCache,
		resolver.WithConnPoolSize(cfg.ConnectionPool),
		resolver.WithDialTimeout(cfg.DialTimeout),
		resolver.WithHandlerMetrics(cfg.meter),
	)

	return resolver.NewResolverService(resolverHandler), nil
}

type httpProxySvcConfig struct {
	meter metric.Meter
	HTTPProxyConfig
}

func newHTTPProxyService(cfg httpProxySvcConfig) (*httpproxy.HTTPProxyService, error) {
	httpProxyCache, err := cache.NewFileCache(
		cfg.Cache.Size.Bytes,
		cfg.Cache.Dir,
		cache.WithMetricMeter(cfg.meter),
	)
	if err != nil {
		return nil, err
	}

	return httpproxy.NewHTTPProxyService(pathutil.RunDir(), httpProxyCache), nil
}

type dhcpSvcConfig struct {
	meter      metric.Meter
	clusterSvc *cluster.ClusterService
	apiClient  *apiclient.APIClient
	agentUUID  string
	// TODO: systemID should be removed.
	systemID string
}

func newDHCPService(c dhcpSvcConfig) (*dhcp.DHCPService, error) {
	return newExternalDHCPService(c)
}

func newExternalDHCPService(c dhcpSvcConfig) (*dhcp.DHCPService, error) {
	serviceName := func() string {
		if _, ok := os.LookupEnv("SNAP"); ok {
			return "dhcpd"
		}

		return "maas-dhcpd"
	}

	v4 := serviceName()
	v6 := v4 + "6"

	controllerV4, err := servicecontroller.NewController(v4)
	if err != nil {
		return nil, fmt.Errorf("DHCP v4 controller initialization failed: %w", err)
	}

	controllerV6, err := servicecontroller.NewController(v6)
	if err != nil {
		return nil, fmt.Errorf("DHCP v6 controller initialization failed: %w", err)
	}

	// TODO: systemID should not be used. Consider switching to agentUUID
	dhcpService := dhcp.NewDHCPService(
		c.systemID,
		controllerV4, controllerV6, false,
		dhcp.WithAPIClient(c.apiClient))

	return dhcpService, nil
}

// startServices is a temporary method, a general sink for all the services
// that need to be run as a part of MAAS agent.
func (d *Daemon) startServices(ctx context.Context, g *errgroup.Group) error {
	// TODO: It would be nice to remove Temporal from the agent, as there is no
	// real need for it. Everything can be orchestrated with the workflow running
	// on the region controller, with HTTP API being the only way of communication
	// between region and agent. Until then workerPool should be injected to any
	// services that might bring up new workers dynamically per each task queue.
	var workerPool worker.WorkerPool

	caPool, err := certutil.LoadCAPool(d.fs, d.cfg.TLS.CAFile)
	if err != nil {
		return fmt.Errorf("loading ca: %w", err)
	}

	id, err := d.id()
	if err != nil {
		return err
	}

	clusterService, err := newClusterService(clusterSvcConfig{
		agentUUID: id,
		systemID:  d.dynCfg.SystemID,
		meter:     d.meterProvider.Meter("cluster"),
	})
	if err != nil {
		return fmt.Errorf("failed to initialize cluster service: %w", err)
	}

	httpProxyService, err := newHTTPProxyService(httpProxySvcConfig{
		HTTPProxyConfig: d.cfg.Services.HTTPProxy,
		meter:           d.meterProvider.Meter("http_proxy"),
	})
	if err != nil {
		return fmt.Errorf("failed to initialize httpproxy service: %w", err)
	}

	resolverService, err := newResolverService(resolverSvcConfig{
		DNSConfig: d.cfg.Services.DNS,
		meter:     d.meterProvider.Meter("resolver"),
	})
	if err != nil {
		return fmt.Errorf("failed to initialize resolver service: %w", err)
	}

	powerService, err := newPowerService(powerSvcConfig{
		agentUUID: id,
		systemID:  d.dynCfg.SystemID,
		pool:      &workerPool,
	})
	if err != nil {
		return fmt.Errorf("failed to initialize power service: %w", err)
	}
	// API client used to communicate with MAAS controller.
	// It is using HTTP client with TLS configuration for mTLS
	//nolint:staticcheck // TODO: migrate to new client
	apiClient := apiclient.NewAPIClient(
		d.cfg.ControllerURL.JoinPath("/MAAS/a/v3internal"),
		&http.Client{
			Transport: &http.Transport{
				// TODO: We should validate FQDN/IP, not just CA validation.
				// That requires proper PKI integration/implementation.
				TLSClientConfig: client.NewTLSConfigWithCAValidationOnly(d.cert, caPool),
			},
		})

	dhcpService, err := newDHCPService(dhcpSvcConfig{
		agentUUID:  id,
		systemID:   d.dynCfg.SystemID,
		clusterSvc: clusterService,
		apiClient:  apiClient,
		meter:      d.meterProvider.Meter("dhcp"),
	})
	if err != nil {
		return fmt.Errorf("failed to initialize dhcp service: %w", err)
	}

	services := []worker.Configurator{
		clusterService,
		powerService,
		httpProxyService,
		resolverService,
		dhcpService,
	}

	workerPoolOptions := []worker.WorkerPoolOption{
		worker.WithMainWorkerTaskQueueSuffix("agent:main"),
	}
	for _, svc := range services {
		workerPoolOptions = append(workerPoolOptions, worker.WithConfigurator(svc))
	}
	// XXX: MAAS has Temporal Server running next to each controller, hence
	// the endpoint is the controller endpoint host, but different port.
	// In theory it can be running elsewhere, but it is not supported.
	// However we should consider adding support for this.
	temporalClient, err := temporal.NewClient(ctx, temporal.ClientConfig{
		SystemID:  d.dynCfg.SystemID,
		Secret:    d.dynCfg.Temporal.EncryptionKey,
		Endpoint:  net.JoinHostPort(d.cfg.ControllerURL.Hostname(), "5271"),
		TLSConfig: client.NewTLSConfigWithCAValidationOnly(d.cert, caPool),
		Meter:     d.meterProvider.Meter("temporal"),
		Tracer:    d.tracerProvider.Tracer("temporal"),
	})
	if err != nil {
		return fmt.Errorf("failed to initialize temporal client: %w", err)
	}

	workerPool = *worker.NewWorkerPool(d.dynCfg.SystemID, temporalClient,
		workerPoolOptions...)
	workerPoolBackoff := backoff.NewExponentialBackOff()
	workerPoolBackoff.MaxElapsedTime = 60 * time.Second

	if err := backoff.Retry(workerPool.Start, workerPoolBackoff); err != nil {
		return fmt.Errorf("failed to initialize worker pool: %w", err)
	}
	// TODO: Add support for cancellation context
	g.Go(workerPool.Error)
	g.Go(clusterService.Error)
	g.Go(httpProxyService.Error)
	g.Go(dhcpService.Error)
	// Region controller will start configuration workflows based on certain
	// events, however this explicit call from the agent is used to cover
	// situations when agent is (re)started and has a clean state.
	// Once we can detect that agent was reconnected or restarted via
	// Temporal server API, we should no longer need this.
	type configureAgentParam struct {
		SystemID string `json:"system_id"`
	}

	workflowOptions := temporalclient.StartWorkflowOptions{
		ID:        fmt.Sprintf("configure-agent:%s", d.dynCfg.SystemID),
		TaskQueue: "region",
		// If we failed to execute this workflow in 120 seconds, then something bad
		// happened and we don't want to keep it in a task queue (will be canceled)
		WorkflowExecutionTimeout: 120 * time.Second,
		WorkflowIDReusePolicy:    temporalenum.WORKFLOW_ID_REUSE_POLICY_TERMINATE_IF_RUNNING,
	}

	workflowRun, err := temporalClient.ExecuteWorkflow(ctx, workflowOptions,
		"configure-agent", configureAgentParam{SystemID: d.dynCfg.SystemID},
	)
	if err != nil {
		return fmt.Errorf("failed to execute configure-agent workflow: %w", err)
	}

	if err := workflowRun.Get(ctx, nil); err != nil {
		return fmt.Errorf("configure-agent workflow failed: %w", err)
	}

	return nil
}
