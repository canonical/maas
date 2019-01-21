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

# Definition for a Prometheus metric.
MetricDefinition = namedtuple(
    'MetricDefiniition', ['type', 'name', 'description', 'labels'])


METRICS_DEFINITIONS = [
    MetricDefinition(
        'Histogram', 'http_request_latency', 'HTTP request latency',
        ['method', 'path', 'status']),
]


class PrometheusMetrics:
    """Wrapper for accessing and interacting with Prometheus metrics."""

    def __init__(self, registry=None, metrics=None):
        self._registry = registry
        self._metrics = metrics or {}

    @property
    def available_metrics(self):
        """Return a list of available metric names."""
        return list(self._metrics)

    def update(self, metric_name, action, value=None, labels=None):
        """Update the specified metric."""
        if not self._metrics:
            return

        metric = self._metrics[metric_name]
        if labels is not None:
            metric = metric.labels(**labels)
        func = getattr(metric, action)
        if value is None:
            func()
        else:
            func(value)

    def generate_latest(self):
        """Generate a bytestring with metric values."""
        if self._registry is not None:
            return prom_cli.generate_latest(self._registry)


def create_metrics():
    """Return a PrometheusMetrics with """
    if not PROMETHEUS_SUPPORTED:
        return PrometheusMetrics(registry=None, metrics=None)
    registry = prom_cli.CollectorRegistry()
    metrics = {}
    for metric in METRICS_DEFINITIONS:
        cls = getattr(prom_cli, metric.type)
        metrics[metric.name] = cls(
            metric.name, metric.description, metric.labels, registry=registry)
    return PrometheusMetrics(registry=registry, metrics=metrics)


PROMETHEUS_METRICS = create_metrics()


def prometheus_metrics_handler(request):
    """Handeler for prometheus metrics."""
    content = PROMETHEUS_METRICS.generate_latest()
    if content is None:
        return HttpResponseNotFound()

    return HttpResponse(content=content, content_type="text/plain")
