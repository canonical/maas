#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
import structlog

from maascommon.tracing import get_or_set_trace_id, set_trace_id
from maasservicelayer.context import Context

logger = structlog.getLogger()

TRACE_ID_HEADER_KEY = "MAAS-trace-id"


class ContextMiddleware(BaseHTTPMiddleware):
    """Injects the Context object in the request state."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        trace_id = request.headers.get(TRACE_ID_HEADER_KEY, None)
        if trace_id:
            set_trace_id(trace_id)
        else:
            trace_id = get_or_set_trace_id()

        context = Context(trace_id=trace_id)
        request.state.context = context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            trace_id=context.trace_id,
        )
        logger.info(
            "Start processing request",
            request_method=request.method,
            request_path=request.url.path,
            request_query=request.url.query,
            # From our nginx config
            request_remote_ip=request.headers.get("x-real-ip"),
            useragent=request.headers.get("user-agent"),
        )
        response = await call_next(request)

        logger.info(
            "End processing request",
            status_code=response.status_code,
            elapsed_time_seconds=context.get_elapsed_time_seconds(),
        )
        response.headers[TRACE_ID_HEADER_KEY] = trace_id
        return response
