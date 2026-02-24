# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class ResponseFinalizerMiddleware(BaseHTTPMiddleware):
    """Finalizes the response by binding any unbound cookies during request processing to the response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if cookie_manager := getattr(request.state, "cookie_manager", None):
            cookie_manager.bind_response(response)
        return response
