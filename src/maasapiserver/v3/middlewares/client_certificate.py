#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""
Middleware for extracting client certificate information from TLS connections.
"""

from typing import Awaitable, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
import structlog

logger = structlog.getLogger(__name__)


class RequireClientCertMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces client certificate authentication by checking
    for the presence of a Common Name (CN) in the TLS connection metadata.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ):
        # skip client cert check for agent enrollment endpoint
        if (
            request.scope["path"].endswith("/agents:enroll")
            and request.scope["method"] == "POST"
        ):
            return await call_next(request)

        # The internal API server is using a special version of uvicorn to always include the tls info inside the context,
        # so we can assume it's there.
        cn = request.scope["extensions"].get("tls", {}).get("client_cn", None)
        if cn is None:
            return JSONResponse(
                {"detail": "Client certificate required."},
                status_code=403,
            )

        request.scope["client_cn"] = cn
        return await call_next(request)
