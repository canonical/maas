# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Prometheus metrics."""

from provisioningserver.prometheus.utils import (
    create_metrics,
    MetricDefinition,
)


METRICS_DEFINITIONS = [
    MetricDefinition(
        'Histogram', 'http_request_latency', 'HTTP request latency',
        ['method', 'path', 'status']),
]


PROMETHEUS_METRICS = create_metrics(METRICS_DEFINITIONS)
