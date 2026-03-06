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

package temporal

import (
	"context"
	"crypto/tls"
	"fmt"
	"os"
	"time"

	"github.com/cenkalti/backoff/v4"
	"github.com/rs/zerolog/log"
	"go.opentelemetry.io/otel/metric"
	"go.opentelemetry.io/otel/trace"
	"go.temporal.io/sdk/client"
	temporalotel "go.temporal.io/sdk/contrib/opentelemetry"
	"go.temporal.io/sdk/converter"
	"go.temporal.io/sdk/interceptor"
	wflog "maas.io/core/src/maasagent/internal/workflow/log"
	"maas.io/core/src/maasagent/pkg/workflow/codec"
)

// ClientConfig used to configure Temporal client
// The provided secret is used to configure the AES EncryptionCodec for
// payload encryption. The TLS configuration enables mTLS connections.
type ClientConfig struct {
	Meter     metric.Meter
	Tracer    trace.Tracer
	TLSConfig *tls.Config
	SystemID  string
	Secret    string
	Endpoint  string
}

// NewClient initializes a Temporal client
func NewClient(ctx context.Context,
	config ClientConfig) (client.Client, error) {
	if config.SystemID == "" {
		return nil, fmt.Errorf("missing system ID")
	}

	// Encryption Codec required for Temporal Workflow's payload encoding
	encCodec, err := codec.NewEncryptionCodec([]byte(config.Secret))
	if err != nil {
		return nil, fmt.Errorf("failed setting up encryption codec: %w", err)
	}

	metricsHandler := temporalotel.NewMetricsHandler(
		temporalotel.MetricsHandlerOptions{Meter: config.Meter},
	)

	retry := backoff.NewExponentialBackOff()
	retry.MaxElapsedTime = 60 * time.Second

	tracingInterceptor, err := temporalotel.NewTracingInterceptor(
		temporalotel.TracerOptions{Tracer: config.Tracer},
	)
	if err != nil {
		return nil, fmt.Errorf("failed setting up tracing interceptor: %w", err)
	}

	connect := func() (client.Client, error) {
		return client.DialContext(ctx, client.Options{
			HostPort:     config.Endpoint,
			Identity:     fmt.Sprintf("%s@agent:%d", config.SystemID, os.Getpid()),
			Logger:       wflog.NewZerologAdapter(log.Logger),
			Interceptors: []interceptor.ClientInterceptor{tracingInterceptor},
			DataConverter: converter.NewCodecDataConverter(
				converter.GetDefaultDataConverter(),
				encCodec,
			),
			ConnectionOptions: client.ConnectionOptions{
				TLS: config.TLSConfig,
			},
			MetricsHandler: metricsHandler,
		})
	}

	return backoff.RetryWithData(connect, retry)
}
