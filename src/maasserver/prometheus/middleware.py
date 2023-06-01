# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from contextlib import contextmanager
from time import time

from django.db import connections
from django.db.backends.utils import CursorWrapper
from django.urls import resolve, reverse

from provisioningserver.prometheus.metrics import PROMETHEUS_METRICS


class QueryCountCursorWrapper(CursorWrapper):
    """Track execution times for queries."""

    def __init__(self, cursor, db, times):
        super().__init__(cursor, db)
        self.times = times

    def execute(self, sql, params=None):
        with self._track_time():
            return super().execute(sql, params=params)

    # XXX this doesn't support executemany as it's not really possible to get
    # times for each call, and it's not used in MAAS anyway.

    def callproc(self, procname, params=None, kparams=None):
        with self._track_time():
            return super().callproc(procname, params=None, kparams=None)

    @contextmanager
    def _track_time(self):
        start = time()
        try:
            yield
        finally:
            self.times.append(time() - start)


class PrometheusRequestMetricsMiddleware:
    """Middleware to set Prometheus metrics related to HTTP requests."""

    def __init__(self, get_response, prometheus_metrics=PROMETHEUS_METRICS):
        self.get_response = get_response
        self.prometheus_metrics = prometheus_metrics

    def __call__(self, request):
        latencies = []

        with wrap_query_counter_cursor(latencies):
            start_time = time()
            response = self.get_response(request)
            latency = time() - start_time

        self._process_metrics(request, response, latency, latencies)
        return response

    def _process_metrics(self, request, response, latency, query_latencies):
        labels = {
            "method": request.method,
            "status": response.status_code,
            "op": request.POST.get("op", request.GET.get("op", "")),
            "path": request.path,
        }
        try:
            match = resolve(request.path.removeprefix("/MAAS"))
            args = [f":arg{i}" for i in range(len(match.args))]
            kwargs = {k: f":{k}" for k in match.kwargs.keys()}
            labels["path"] = reverse(match.url_name, None, args, kwargs)
        except Exception:
            # use the request path as-is
            pass

        self.prometheus_metrics.update(
            "maas_http_request_latency",
            "observe",
            value=latency,
            labels=labels,
        )
        if not response.streaming:
            self.prometheus_metrics.update(
                "maas_http_response_size",
                "observe",
                value=len(response.content),
                labels=labels,
            )
        self.prometheus_metrics.update(
            "maas_http_request_query_count",
            "observe",
            value=len(query_latencies),
            labels=labels,
        )
        for latency in query_latencies:
            self.prometheus_metrics.update(
                "maas_http_request_query_latency",
                "observe",
                value=latency,
                labels=labels,
            )


@contextmanager
def wrap_query_counter_cursor(query_latencies, dbconn_name="default"):
    """Context manager replacing the cursor with a QueryCountCursorWrapper."""
    dbconn = connections[dbconn_name]
    orig_make_cursor = dbconn.make_cursor
    dbconn.make_cursor = lambda cursor: QueryCountCursorWrapper(
        cursor, dbconn, query_latencies
    )
    try:
        yield
    finally:
        dbconn.make_cursor = orig_make_cursor
