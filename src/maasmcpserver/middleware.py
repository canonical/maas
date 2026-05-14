# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""ASGI auth middleware for MCP server."""

import contextvars
from typing import Any, Awaitable, Callable
import uuid

from maasmcpserver.logging_events import log_session_closed, log_session_opened

# Per-request context variable for session state
session_context: contextvars.ContextVar[dict[str, Any] | None] = (
    contextvars.ContextVar("session_context", default=None)
)


class AuthMiddleware:
    """ASGI middleware for Bearer token authentication."""

    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract Authorization header
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("utf-8")

        # Validate Bearer token
        if not auth_header.startswith("Bearer "):
            await self._send_401(send)
            return

        token = auth_header[7:]  # Strip "Bearer "
        if not token:
            await self._send_401(send)
            return

        # Generate session ID and store in context
        session_id = str(uuid.uuid4())
        session_context.set({"session_id": session_id, "api_key": token})

        # Emit session.opened event
        log_session_opened(session_id, token)

        try:
            await self.app(scope, receive, send)
        finally:
            # Emit session.closed event and clear context
            log_session_closed(session_id)
            session_context.set({})

    async def _send_401(
        self, send: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Send HTTP 401 Unauthorized response."""
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    [b"content-type", b"application/json"],
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b'{"error":"Unauthorized"}',
            }
        )


def get_session_id() -> str:
    """Get the current session ID from context."""
    ctx = session_context.get()
    return ctx.get("session_id", "") if ctx else ""


def get_api_key() -> str:
    """Get the current API key from context."""
    ctx = session_context.get()
    return ctx.get("api_key", "") if ctx else ""
