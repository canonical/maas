from typing import Awaitable, Callable

from fastapi import Request, Response
from prometheus_client import CollectorRegistry, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match
from starlette.types import ASGIApp

from provisioningserver.prometheus.utils import (
    create_metrics,
    MetricDefinition,
)
from provisioningserver.utils.env import MAAS_UUID
from provisioningserver.utils.ipaddr import get_machine_default_gateway_ip

HTTP_LABELS = ("handler", "method")

METRICS_DEFINITIONS = (
    MetricDefinition(
        "Counter",
        "maas_apiserver_call_query_count",
        "API server - number of database queries per request",
        labels=HTTP_LABELS,
    ),
    MetricDefinition(
        "Histogram",
        "maas_apiserver_call_query_latency",
        "API server - latency of database queries per request in seconds",
        labels=HTTP_LABELS,
        buckets=(0.001, 0.005, 0.01, 0.1, 0.25, 0.5, 1.0),
    ),
)


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
        self.metrics = create_metrics(
            METRICS_DEFINITIONS,
            registry=CollectorRegistry(),
            extra_labels={
                "host": get_machine_default_gateway_ip(),
                "maas_id": MAAS_UUID.get(),
            },
        )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # make metrics accessible everywhere
        request.state.prometheus_metrics = self.metrics

        response = await call_next(request)

        handler = self._get_handler(request)
        # update DB-related metrics
        if query_count := request.state.query_metrics["count"]:
            self.metrics.update(
                "maas_apiserver_call_query_count",
                "inc",
                query_count,
                labels={"handler": handler, "method": request.method},
            )
            self.metrics.update(
                "maas_apiserver_call_query_latency",
                "observe",
                request.state.query_metrics["latency"],
                labels={"handler": handler, "method": request.method},
            )

        return response

    def _get_handler(self, request: Request) -> str:
        for route in request.app.routes:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                return route.path
        return request.url.path
