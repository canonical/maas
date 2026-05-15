# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""FastMCP application factory for MAAS MCP server."""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field

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


def _register_resources_as_tools(app: FastMCP) -> None:
    """Expose resources via tools for clients that lack native resource support.

    Mirrors the ResourcesAsTools transform from gofastmcp.com: adds
    ``list_resources`` and ``read_resource`` tools that route through the
    server's resource manager so that all middleware (auth, visibility) applies
    exactly as it would for direct ``resources/read`` calls.
    """

    @app.tool(
        title="List Resources",
        description="List all available MCP resources.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def list_resources() -> str:
        resources = await app.list_resources()
        templates = await app.list_resource_templates()
        items: list[dict[str, Any]] = [
            {
                "uri": str(r.uri),
                "name": r.name,
                "description": r.description,
                "mime_type": r.mimeType,
            }
            for r in resources
        ]
        items += [
            {
                "uri_template": str(t.uriTemplate),
                "name": t.name,
                "description": t.description,
            }
            for t in templates
        ]
        return json.dumps(items)

    @app.tool(
        title="Read Resource",
        description="Read a resource by URI (e.g. 'maas://info').",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def read_resource(
        uri: Annotated[str, Field(description="URI of the resource to read.")],
    ) -> str:
        contents = await app.read_resource(uri)
        parts = []
        for item in contents:
            if isinstance(item.content, bytes):
                parts.append(item.content.decode("utf-8", errors="replace"))
            else:
                parts.append(str(item.content))
        return "\n".join(parts)


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
    _register_resources_as_tools(app)

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
