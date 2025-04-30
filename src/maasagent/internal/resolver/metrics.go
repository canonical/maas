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

package resolver

import (
	"context"
	"net/netip"
	"sync/atomic"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/metric"
	"maas.io/core/src/maasagent/internal/connpool"
)

type handlerStats struct {
	fromCache        atomic.Int64
	authoritative    atomic.Int64
	nonauthoritative atomic.Int64
	srvFail          atomic.Int64
	invalid          atomic.Int64
	queries          atomic.Int64
}

type cacheStats struct {
	hits        atomic.Int64
	misses      atomic.Int64
	expirations atomic.Int64
}

func must[T any](v T, err error) T {
	if err != nil {
		panic(err)
	}

	return v
}

func WithHandlerMetrics(meter metric.Meter) RecursiveHandlerOption {
	return func(h *RecursiveHandler) {
		fromCache := attribute.String("type", "cache")
		authoritative := attribute.String("type", "authoritative")
		nonauthoritative := attribute.String("type", "nonauthoritative")
		srvFail := attribute.String("type", "servfail")
		invalid := attribute.String("type", "invalid")

		must(meter.Int64ObservableCounter("resolver.responses",
			metric.WithUnit("{count}"),
			metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
				o.Observe(h.stats.fromCache.Load(), metric.WithAttributes(fromCache))
				o.Observe(h.stats.authoritative.Load(), metric.WithAttributes(authoritative))
				o.Observe(h.stats.nonauthoritative.Load(), metric.WithAttributes(nonauthoritative))
				o.Observe(h.stats.srvFail.Load(), metric.WithAttributes(srvFail))
				o.Observe(h.stats.invalid.Load(), metric.WithAttributes(invalid))

				return nil
			})))

		must(meter.Int64ObservableGauge("resolver.upstream_connection_pool.size",
			metric.WithUnit("{count}"),
			metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
				h.conns.Range(func(k netip.Addr, v connpool.Pool) {
					upstream := attribute.String("upstream", k.String())
					o.Observe(int64(v.Len()), metric.WithAttributes(upstream))
				})

				return nil
			})))

		must(meter.Int64ObservableCounter("resolver.queries",
			metric.WithUnit("{count}"),
			metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
				o.Observe(h.stats.queries.Load())

				return nil
			})))
	}
}

func WithCacheMetrics(meter metric.Meter) CacheOption {
	return func(c *cache) {
		hits := attribute.String("type", "hits")
		expirations := attribute.String("type", "expirations")
		misses := attribute.String("type", "misses")

		must(meter.Int64ObservableCounter("resolver.cache.usage",
			metric.WithUnit("{count}"),
			metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
				o.Observe(c.stats.hits.Load(), metric.WithAttributes(hits))
				o.Observe(c.stats.expirations.Load(), metric.WithAttributes(expirations))
				o.Observe(c.stats.misses.Load(), metric.WithAttributes(misses))

				return nil
			})))

		currentSize := attribute.String("type", "current")
		maxSize := attribute.String("type", "max")

		must(meter.Int64ObservableGauge("resolver.cache.size",
			metric.WithUnit("{count}"),
			metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
				o.Observe(int64(c.cache.Len()), metric.WithAttributes(currentSize))
				o.Observe(int64(c.maxNumRecords), metric.WithAttributes(maxSize))

				return nil
			})))
	}
}
