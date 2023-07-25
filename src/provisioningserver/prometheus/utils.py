import asyncio
from functools import wraps
import glob
import os
import re
import time
from typing import Optional, Tuple

import prometheus_client
from twisted.internet.defer import Deferred

from provisioningserver.utils.ps import is_pid_running


class MetricDefinition:
    """Definition for a Prometheus metric."""

    def __init__(self, type, name, description, labels=(), **kwargs):
        self.type = type
        self.name = name
        self.description = description
        self.labels = list(labels)
        self.kwargs = kwargs


class PrometheusMetrics:
    """Wrapper for accessing and interacting with Prometheus metrics."""

    def __init__(
        self,
        definitions=None,
        extra_labels=None,
        update_handlers=(),
        registry=None,
    ):
        self._extra_labels = extra_labels or {}
        self._update_handlers = update_handlers
        if definitions is None:
            self.registry = None
            self._metrics = {}
        else:
            self.registry = registry or prometheus_client.REGISTRY
            self._metrics = self._create_metrics(definitions)

    def _create_metrics(self, definitions):
        metrics = {}
        for definition in definitions:
            labels = definition.labels.copy()
            if self._extra_labels:
                labels.extend(self._extra_labels)
            cls = getattr(prometheus_client, definition.type)
            metrics[definition.name] = cls(
                definition.name,
                definition.description,
                labels,
                registry=self.registry,
                **definition.kwargs
            )

        return metrics

    @property
    def available_metrics(self):
        """Return a list of available metric names."""
        return list(self._metrics)

    def update(self, metric_name, action, value=None, labels=None):
        """Update the specified metric."""
        if not self._metrics:
            return

        metric = self._metrics[metric_name]
        all_labels = labels.copy() if labels else {}
        if self._extra_labels:
            extra_labels = {
                key: value() if callable(value) else value
                for key, value in self._extra_labels.items()
            }
            all_labels.update(extra_labels)
        if all_labels:
            metric = metric.labels(**all_labels)
        func = getattr(metric, action, None)
        if func is None:
            # access the ValueClass directly
            func = getattr(metric._value, action)
        if value is None:
            func()
        else:
            func(value)

    def generate_latest(self):
        """Generate a bytestring with metric values."""
        if self.registry is None:
            return

        registry = self.registry
        if registry is prometheus_client.REGISTRY:
            # when using the global registry, setup up multiprocess
            # support. In this case, a separate registry needs to be used
            # for generating the samples.
            registry = prometheus_client.CollectorRegistry()
            from prometheus_client import multiprocess

            multiprocess.MultiProcessCollector(registry)

        for handler in self._update_handlers:
            handler(self)
        return prometheus_client.generate_latest(registry)

    def record_call_latency(
        self, metric_name, get_labels=lambda *args, **kwargs: {}
    ):
        """Wrap a function to record its call latency on a metric.

        If the function returns an asyncio coroutine or a Twisted Deferred,,
        the time to complete the async funcion is tracked.

        The `get_labels` function is called with the same arguments as the call
        and must return a dict with labels for the metric.
        """

        def wrap_func(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                before = time.perf_counter()
                result = func(*args, **kwargs)
                after = time.perf_counter()

                if asyncio.iscoroutine(result):
                    # wrap to track time after the call has completed
                    async def record_latency(coro):
                        result = await coro
                        latency = time.perf_counter() - before
                        self.update(
                            metric_name,
                            "observe",
                            value=latency,
                            labels=get_labels(*args, **kwargs),
                        )
                        return result

                    return record_latency(result)

                elif isinstance(result, Deferred):
                    # attach a callback to the deferred to track time after the
                    # call has completed
                    def record_latency(result):
                        latency = time.perf_counter() - before
                        self.update(
                            metric_name,
                            "observe",
                            value=latency,
                            labels=get_labels(*args, **kwargs),
                        )
                        return result

                    result.addCallback(record_latency)
                else:
                    latency = after - before
                    self.update(
                        metric_name,
                        "observe",
                        value=latency,
                        labels=get_labels(*args, **kwargs),
                    )
                return result

            return wrapper

        return wrap_func

    def failure_counter(
        self,
        metric_name: str,
        exceptions_filter: Optional[Tuple[Exception]] = None,
        get_labels=lambda *args, **kwargs: {},
    ):
        """
        failure_counter increments the given metric when an exception within its
        context occurs, if a filter is provided, only exceptions of that type will
        increment the metric.
        """

        def counter(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                labels = get_labels(*args, **kwargs)
                try:
                    result = func(*args, **kwargs)
                except Exception as e:
                    if not exceptions_filter or type(e) in exceptions_filter:
                        self.update(metric_name, "inc", value=1, labels=labels)
                    raise e
                return result

            return wrapper

        return counter


def create_metrics(
    metric_definitions, extra_labels=None, update_handlers=(), registry=None
):
    """Return a PrometheusMetrics from the specified definitions."""
    return PrometheusMetrics(
        definitions=metric_definitions,
        extra_labels=extra_labels,
        update_handlers=update_handlers,
        registry=registry,
    )


def clean_prometheus_dir(path=None):
    """Delete unused Prometheus database files from the specified dir.

    Files for PIDs not matching running processes are removed.
    """
    if path is None:
        path = os.environ.get("prometheus_multiproc_dir")
    if not path or not os.path.isdir(path):
        return

    file_re = re.compile(r".*_(?P<pid>[0-9]+)\.db")

    for dbfile in glob.iglob(path + "/*.db"):
        match = file_re.match(dbfile)
        if not match:
            continue

        pid = int(match.groupdict()["pid"])
        if not is_pid_running(pid):
            try:
                os.remove(dbfile)
            except FileNotFoundError:
                # might have been deleted by a concurrent run from
                # another process
                pass
