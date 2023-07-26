from typing import Awaitable, Callable

from fastapi import Request, Response
from prometheus_client import CollectorRegistry, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match
from starlette.types import ASGIApp

from provisioningserver.prometheus.utils import (
    create_metrics,
    MetricDefinition,
    PrometheusMetrics,
)
from provisioningserver.utils.env import MAAS_UUID
from provisioningserver.utils.ipaddr import get_machine_default_gateway_ip


async def metrics(request: Request) -> Response:
    """Prometheus metrics endpoint."""
    content = request.state.prometheus_metrics.generate_latest()
    return Response(content=content, media_type=CONTENT_TYPE_LATEST)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Collect Prometheus metrics for the call.

    This requires the DatabaseMetricsMiddleware to be configured.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.metrics = _get_metrics()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # make metrics accessible everywhere
        request.state.prometheus_metrics = self.metrics

        def get_labels(request, response):
            return {
                "handler": self._get_handler(request),
                "method": request.method,
                "status": response.status_code,
            }

        # wrap the call to time request latency and call the next handler
        call_next = self.metrics.record_call_latency(
            "maas_apiserver_request_latency",
            get_labels=lambda args, kwargs, response: get_labels(
                request, response
            ),
        )(call_next)
        response = await call_next(request)

        labels = get_labels(request, response)
        # update HTTP metrics
        self.metrics.update(
            "maas_apiserver_response_size",
            "observe",
            int(response.headers.get("Content-Length", 0)),
            labels=labels,
        )

        # update DB metrics
        if query_count := request.state.query_metrics["count"]:
            self.metrics.update(
                "maas_apiserver_request_query_count",
                "inc",
                query_count,
                labels=labels,
            )
            self.metrics.update(
                "maas_apiserver_request_query_latency",
                "observe",
                request.state.query_metrics["latency"],
                labels=labels,
            )

        return response

    def _get_handler(self, request: Request) -> str:
        for route in request.app.routes:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                return route.path
        return request.url.path


def _get_metrics() -> PrometheusMetrics:
    http_labels = ("handler", "method", "status")
    definitions = (
        MetricDefinition(
            "Histogram",
            "maas_apiserver_request_latency",
            "API server - latency of HTTP request in seconds",
            labels=http_labels,
        ),
        MetricDefinition(
            "Histogram",
            "maas_apiserver_response_size",
            "API server - size of HTTP response in bytes",
            labels=http_labels,
            buckets=[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000],
        ),
        MetricDefinition(
            "Counter",
            "maas_apiserver_request_query_count",
            "API server - number of database queries per request",
            labels=http_labels,
        ),
        MetricDefinition(
            "Histogram",
            "maas_apiserver_request_query_latency",
            "API server - latency of database queries per request in seconds",
            labels=http_labels,
            buckets=(0.001, 0.005, 0.01, 0.1, 0.25, 0.5, 1.0),
        ),
    )
    return create_metrics(
        definitions,
        registry=CollectorRegistry(),
        extra_labels={
            "host": get_machine_default_gateway_ip(),
            "maas_id": MAAS_UUID.get(),
        },
    )
