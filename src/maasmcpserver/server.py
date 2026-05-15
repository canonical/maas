# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""FastMCP application factory for MAAS MCP server."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from maasmcpserver.client import MAASClientPool
from maasmcpserver.config import MaasServerConfig
from maasmcpserver.middleware import AuthMiddleware
from maasmcpserver.tools import boot_sources as boot_sources_tools
from maasmcpserver.tools import diagnostics as diagnostics_tools
from maasmcpserver.tools import fleet as fleet_tools
from maasmcpserver.tools import info as info_tools
from maasmcpserver.tools import network as network_tools

# DNS rebinding protection is irrelevant on a Unix domain socket — the socket
# is only reachable via nginx (which terminates the TCP connection) and the
# local filesystem. Disabling it prevents spurious "Invalid Host header" errors
# when clients connect through nginx with their own Host header.
_TRANSPORT_SECURITY = TransportSecuritySettings(
    enable_dns_rebinding_protection=False
)


def get_app(config: MaasServerConfig):
    """Create and wrap the ASGI application with auth middleware.

    A single :class:`MAASClientPool` is created here and shared across all
    tool calls for the lifetime of the process.  The pool is closed cleanly
    on ASGI shutdown via a lifespan wrapper so that in-flight connections are
    drained before the process exits.
    """
    pool = MAASClientPool(config)

    app = FastMCP("MAAS MCP Server", transport_security=_TRANSPORT_SECURITY)
    fleet_tools.register(app, pool)
    diagnostics_tools.register(app, pool)
    info_tools.register(app, pool)
    network_tools.register(app, pool)
    boot_sources_tools.register(app, pool)
    # TODO: add ResourcesAsTools transform once available in python3-mcp
    # https://gofastmcp.com/servers/transforms/resources-as-tools

    inner_asgi = app.streamable_http_app()

    @asynccontextmanager
    async def _lifespan(
        inner: Any,
    ) -> AsyncGenerator[None, None]:
        try:
            yield
        finally:
            await pool.aclose()

    async def asgi(scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] == "lifespan":
            async with _lifespan(inner_asgi):
                await inner_asgi(scope, receive, send)
        else:
            await inner_asgi(scope, receive, send)

    return AuthMiddleware(asgi)
