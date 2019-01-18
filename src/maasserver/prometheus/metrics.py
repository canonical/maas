# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Prometheus metrics."""

from collections import namedtuple

from django.http import (
    HttpResponse,
    HttpResponseNotFound,
)
from maasserver.prometheus import (
    prom_cli,
    PROMETHEUS_SUPPORTED,
)


PrometheusMetrics = namedtuple('PrometheusMetrics', ['metrics', 'registry'])

METRICS_DEFINITIONS = [
    ('Histogram', 'http_request_latency', 'HTTP request latency',
     ['method', 'path', 'status']),
]


def create_metrics():
    """Return a PrometheusMetrics with """
    if not PROMETHEUS_SUPPORTED:
        return None
    registry = prom_cli.CollectorRegistry()
    metrics = {}
    for metric_type, name, description, labels in METRICS_DEFINITIONS:
        cls = getattr(prom_cli, metric_type)
        metrics[name] = cls(name, description, labels, registry=registry)
    return PrometheusMetrics(metrics=metrics, registry=registry)


PROMETHEUS_METRICS = create_metrics()


def prometheus_metrics_handler(request):
    """Handeler for prometheus metrics."""
    if PROMETHEUS_METRICS is None:
        return HttpResponseNotFound()

    return HttpResponse(
        content=prom_cli.generate_latest(PROMETHEUS_METRICS.registry),
        content_type="text/plain")
