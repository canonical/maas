from collections import namedtuple

from maasserver.prometheus import (
    prom_cli,
    PROMETHEUS_SUPPORTED,
)

# Definition for a Prometheus metric.
MetricDefinition = namedtuple(
    'MetricDefiniition', ['type', 'name', 'description', 'labels'])


class PrometheusMetrics:
    """Wrapper for accessing and interacting with Prometheus metrics."""

    def __init__(self, registry=None, metrics=None):
        self.registry = registry
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
        if self.registry is not None:
            return prom_cli.generate_latest(self.registry)


def create_metrics(metric_definitions):
    """Return a PrometheusMetrics from the specified definitions."""
    if not PROMETHEUS_SUPPORTED:
        return PrometheusMetrics(registry=None, metrics=None)
    registry = prom_cli.CollectorRegistry()
    metrics = {}
    for metric in metric_definitions:
        cls = getattr(prom_cli, metric.type)
        metrics[metric.name] = cls(
            metric.name, metric.description, metric.labels, registry=registry)
    return PrometheusMetrics(registry=registry, metrics=metrics)
