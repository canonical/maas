from prometheus_client import CONTENT_TYPE_LATEST
from starlette.requests import Request
from starlette.responses import Response

from maasapiserver.common.api.base import Handler, handler


class MetricsHandler(Handler):
    @handler(path="/metrics", methods=["GET"], include_in_schema=False)
    async def metrics(self, request: Request) -> Response:
        """Prometheus metrics endpoint."""
        content = request.state.prometheus_metrics.generate_latest()
        return Response(content=content, media_type=CONTENT_TYPE_LATEST)
