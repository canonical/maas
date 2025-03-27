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

	"github.com/canonical/microcluster/v2/microcluster"
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
)

type ClusterService struct {
	fatal           chan error
	dataPathFactory dataPathFactory
	cluster         *microcluster.MicroCluster
	systemID        string
}

type dataPathFactory func(string) string

type ClusterServiceOption func(*ClusterService)

func NewClusterService(systemID string,
	options ...ClusterServiceOption) (*ClusterService, error) {
	s := &ClusterService{systemID: systemID,
		dataPathFactory: pathutil.GetDataPath,
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
						attribute.Int64("schema_version_internal", int64(m.SchemaInternalVersion)),
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
	cctx := context.Background()

	if err := workflow.RunAsLocalActivity(ctx, func(ctx context.Context) error {
		go func() {
			// TODO: propagate version during build
			err := s.cluster.Start(cctx, microcluster.DaemonArgs{
				Version: "UNKNOWN",
				// Microcluster is using logrus and the format will be slightly different
				// than zerolog of MAAS Agent.
				Debug: zerolog.GlobalLevel() == zerolog.DebugLevel,
			})
			if err != nil {
				log.Error("Failed to start Microcluster", "err", err)
				s.fatal <- err
			}
		}()

		err := s.cluster.Ready(cctx)
		if err != nil {
			log.Error("Microcluster is not ready", "err", err)
			return err
		}

		status, err := s.cluster.Status(cctx)
		if err == nil && status.Ready {
			return nil
		}

		// TODO: allow selecting interface used for clustering
		address := lxdutil.CanonicalNetworkAddress(lxdutil.NetworkInterfaceAddress(), clusteringPort)

		// TODO: join existing cluster with token
		err = s.cluster.NewCluster(cctx, s.systemID, address, nil)

		log.Error("Cannot bootstrap Microcluster", "err", err)
		return err
	}); err != nil {
		log.Error("Failed to setup cluster-service", "err", err)
		return err
	}

	log.Info("Started cluster-service")

	return nil
}

func (s *ClusterService) Error() error {
	err := <-s.fatal

	return err
}
