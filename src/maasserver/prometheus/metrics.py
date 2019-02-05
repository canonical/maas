# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Prometheus metrics."""

from django.http import (
    HttpResponse,
    HttpResponseNotFound,
)
from maasserver.prometheus.stats import (
    STATS_DEFINITIONS,
    update_prometheus_stats,
)
from provisioningserver.prometheus.utils import (
    create_metrics,
    MetricDefinition,
)


METRICS_DEFINITIONS = [
    MetricDefinition(
        'Histogram', 'http_request_latency', 'HTTP request latency',
        ['method', 'path', 'status']),
]


PROMETHEUS_METRICS = create_metrics(METRICS_DEFINITIONS + STATS_DEFINITIONS)


def prometheus_metrics_handler(request):
    """Handeler for prometheus metrics."""
    update_prometheus_stats(PROMETHEUS_METRICS)
    content = PROMETHEUS_METRICS.generate_latest()
    if content is None:
        return HttpResponseNotFound()

    return HttpResponse(content=content, content_type="text/plain")
