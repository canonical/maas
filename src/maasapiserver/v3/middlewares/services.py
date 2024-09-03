from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.services import ServiceCollectionV3


async def services(
    request: Request,
) -> ServiceCollectionV3:
    """Dependency to return the services collection."""
    return request.state.services


class ServicesMiddleware(BaseHTTPMiddleware):
    """Injects the V3 services in the request context if the request targets a v3 endpoint."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Just pass through the request if it's not a V3 endpoint. The other V2 endpoints have another authentication
        # architecture/mechanism.
        if not request.url.path.startswith(V3_API_PREFIX):
            return await call_next(request)

        services = await ServiceCollectionV3.produce(request.state.conn)
        request.state.services = services
        return await call_next(request)
