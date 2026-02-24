// Copyright (c) 2025 Canonical Ltd
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

package cluster

import (
	"context"
	"errors"
	"os"
	"time"

	"github.com/canonical/microcluster/v2/microcluster"
	"github.com/canonical/microcluster/v2/state"
	"github.com/rs/zerolog"

	lxdutil "github.com/canonical/lxd/lxd/util"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/metric"
	tworkflow "go.temporal.io/sdk/workflow"
	"maas.io/core/src/maasagent/internal/pathutil"
	"maas.io/core/src/maasagent/internal/workflow"
)

const (
	clusteringPort = 5280
	daemonConf     = "microcluster/daemon.yaml" // only exists in initialized clusters
)

type ClusterService struct {
	fatal           chan error
	dataPathFactory dataPathFactory
	cluster         *microcluster.MicroCluster
	cancel          context.CancelFunc
	clusterHooks    *state.Hooks
	systemID        string
}

type dataPathFactory func(string) string

type ClusterServiceOption func(*ClusterService)

func NewClusterService(systemID string,
	options ...ClusterServiceOption) (*ClusterService, error) {
	s := &ClusterService{systemID: systemID,
		dataPathFactory: pathutil.DataPath,
	}

	for _, opt := range options {
		opt(s)
	}

	cluster, err := microcluster.App(microcluster.Args{
		StateDir: s.dataPathFactory("microcluster"),
	})
	if err != nil {
		return nil, err
	}

	s.cluster = cluster

	return s, nil
}

// WithDataPathFactory used for testing.
func WithDataPathFactory(factory dataPathFactory) ClusterServiceOption {
	return func(s *ClusterService) {
		s.dataPathFactory = factory
	}
}

func WithClusterHooks(hooks *state.Hooks) ClusterServiceOption {
	return func(s *ClusterService) {
		s.clusterHooks = hooks
	}
}

func must[T any](v T, err error) T {
	if err != nil {
		panic(err)
	}

	return v
}

// WithMetricMeter allows to set OpenTelemetry metric.Meter
// to collect cluster info.
func WithMetricMeter(meter metric.Meter) ClusterServiceOption {
	return func(s *ClusterService) {
		must(meter.Int64ObservableGauge("members",
			metric.WithUnit("{info}"),
			metric.WithInt64Callback(func(ctx context.Context, o metric.Int64Observer) error {
				client, err := s.cluster.LocalClient()
				if err != nil {
					return err
				}

				members, err := client.GetClusterMembers(ctx)
				if err != nil {
					return err
				}

				for _, m := range members {
					o.Observe(int64(1), metric.WithAttributes(
						attribute.String("member", m.Name),
						attribute.String("address", m.Address.String()),
						attribute.String("role", m.Role),
						attribute.String("status", string(m.Status)),
						attribute.Int64("last_heartbeat", m.LastHeartbeat.Unix()),
						//nolint:gosec // OpenTelemetry doesn’t support uint64
						attribute.Int64("schema_version_internal", int64(m.SchemaInternalVersion)),
						//nolint:gosec // OpenTelemetry doesn’t support uint64
						attribute.Int64("schema_version_external", int64(m.SchemaExternalVersion)),
					))
				}

				return nil
			})))
	}
}

func (s *ClusterService) ConfigurationWorkflows() map[string]any {
	return map[string]any{"configure-cluster-service": s.configure}
}

func (s *ClusterService) ConfigurationActivities() map[string]any {
	return map[string]any{}
}

type ClusterServiceConfigParam struct {
	// TODO: bootstrap node or join existing cluster with token
}

func (s *ClusterService) configure(ctx tworkflow.Context, config ClusterServiceConfigParam) error {
	log := tworkflow.GetLogger(ctx)
	log.Info("Configuring cluster-service")

	// Use new context.Background here because Workflow context will be closed once
	// workflow execution is completed.
	var cctx context.Context

	cctx, s.cancel = context.WithCancel(context.Background())

	if err := workflow.RunAsLocalActivity(ctx, func(ctx context.Context) error {
		go func() {
			// TODO: propagate version during build
			err := s.cluster.Start(cctx, microcluster.DaemonArgs{
				Version: "UNKNOWN",
				// Microcluster is using logrus and the format will be slightly different
				// than zerolog of MAAS Agent.
				Debug:            zerolog.GlobalLevel() == zerolog.DebugLevel,
				ExtensionsSchema: schemaExtensions,
				Hooks:            s.clusterHooks,
			})
			if err != nil {
				log.Error("Failed to start Microcluster", "err", err)
				s.fatal <- err
			}
		}()

		return nil
	}); err != nil {
		log.Error("Failed to setup cluster-service", "err", err)
		return err
	}

	log.Info("Started cluster-service")

	return nil
}

// ConfigureDirect is for the dhcp test server where the cluster is being configured outside of temporal
func (s *ClusterService) ConfigureDirect(ctx context.Context) error {
	return s.cluster.Start(ctx, microcluster.DaemonArgs{
		Version:          "UNKNOWN",
		Debug:            zerolog.GlobalLevel() == zerolog.DebugLevel,
		ExtensionsSchema: schemaExtensions,
		Hooks:            s.clusterHooks,
	})
}

func (s *ClusterService) Ready(ctx context.Context) error {
	return s.cluster.Ready(ctx)
}

// OnStart executes in microcluster's start hook and checks if there is an existing daemon configuration
// this allows us to confirm whether there is an existing cluster configuration (single host, or multi-member)
// or if one is needed to be created.
func (s *ClusterService) OnStart(ctx context.Context) error {
	// TODO: allow selecting interface used for clustering
	address := lxdutil.CanonicalNetworkAddress(lxdutil.NetworkInterfaceAddress(), clusteringPort)

	_, err := os.Stat(s.dataPathFactory(daemonConf))
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			// Bootstrap local cluster
			err = s.cluster.NewCluster(ctx, s.systemID, address, nil)
		}

		return err
	} else {
		tokens, err := s.cluster.ListJoinTokens(ctx)
		if err != nil {
			return err
		}

		for _, token := range tokens {
			if time.Since(token.ExpiresAt) >= 0 {
				// join existing cluster
				err = s.cluster.JoinCluster(ctx, s.systemID, address, token.Token, nil)
				if err != nil {
					return err
				}

				return nil
			}
		}
	}

	// TODO join new cluster

	return nil
}

func (s *ClusterService) stop() {
	if s.cancel != nil {
		s.cancel()
	}
}

func (s *ClusterService) Error() error {
	err := <-s.fatal

	return err
}
