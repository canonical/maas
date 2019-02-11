from collections import namedtuple
from functools import wraps
from time import time

from provisioningserver.prometheus import (
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
        if labels:
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

    def record_call_latency(
            self, metric_name, get_labels=lambda *args, **kwargs: {}):
        """Wrap a function returning a Deferred to record its call latency on a metric.

        The `get_labels` function is called with the same arguments as the call
        and must return a dict with labels for the metric.

        """

        def wrap_func(func):

            @wraps(func)
            def wrapper(*args, **kwargs):
                labels = get_labels(*args, **kwargs)
                before = time()
                d = func(*args, **kwargs)

                def record_latency(result):
                    latency = time() - before
                    self.update(
                        metric_name, 'observe', value=latency, labels=labels)
                    return result

                d.addCallback(record_latency)
                return d

            return wrapper

        return wrap_func


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
