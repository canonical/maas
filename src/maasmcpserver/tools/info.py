# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MCP tool for MAAS deployment information."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from maasmcpserver.client import MAASClient, MAASClientPool
from maasmcpserver.logging_events import log_tool_outcome, log_tool_received
from maasmcpserver.middleware import get_api_key, get_session_id
from maasmcpserver.models.info import MAASInfo, RackController
from maasmcpserver.tools.common import items_from_payload, safe_text
from maasmcpserver.tools.common import run_tool as _run_tool

_CONFIG_PATH = "/MAAS/a/v3/configurations/maas_name"
_RACKS_PATH = "/MAAS/a/v3/racks"


def make_client(pool: Any, api_key: str) -> MAASClient:
    if hasattr(pool, "client"):
        client = pool.client(api_key)
        client._close_after_use = False
        return client

    client = MAASClient(pool, api_key)
    client._close_after_use = True
    return client


async def run_tool(
    tool_name: str,
    params: dict[str, Any],
    pool: MAASClientPool,
    operation: Callable[[MAASClient], Awaitable[str]],
    not_found_message: str | None = None,
) -> str:
    return await _run_tool(
        tool_name,
        params,
        pool,
        operation,
        not_found_message=not_found_message,
        get_api_key_func=get_api_key,
        get_session_id_func=get_session_id,
        log_tool_received_func=log_tool_received,
        log_tool_outcome_func=log_tool_outcome,
        make_client_func=make_client,
    )


def _rack_controller_from_payload(payload: dict[str, Any]) -> RackController:
    return RackController.model_validate(
        {
            "hostname": safe_text(
                payload.get("hostname") or payload.get("name"),
                default="unknown",
            ),
            "rack_id": safe_text(
                payload.get("rack_id") or payload.get("system_id"),
                default="unknown",
            ),
            "connection_state": safe_text(
                payload.get("connection_state"),
                default="unknown",
            ),
        }
    )


def _build_maas_info(config_payload: Any, racks_payload: Any) -> MAASInfo:
    deployment_name = "unknown"
    if isinstance(config_payload, dict):
        deployment_name = safe_text(
            config_payload.get("value"),
            default="unknown",
        )

    return MAASInfo.model_validate(
        {
            "deployment_name": deployment_name,
            "rack_controllers": [
                _rack_controller_from_payload(item)
                for item in items_from_payload(racks_payload)
            ],
        }
    )


def _format_maas_info(maas_info: MAASInfo) -> str:
    lines = [
        "## MAAS Deployment Info",
        "",
        f"**Deployment Name**: {maas_info.deployment_name}",
        "",
        "### Rack Controllers",
    ]
    if not maas_info.rack_controllers:
        lines.append("No rack controllers registered.")
        return "\n".join(lines)

    lines.extend(
        [
            "| Hostname | Rack ID | Connection State |",
            "|----------|---------|------------------|",
        ]
    )
    lines.extend(
        (f"| {rack.hostname} | {rack.rack_id} | {rack.connection_state} |")
        for rack in maas_info.rack_controllers
    )
    return "\n".join(lines)


def register(mcp: FastMCP, pool: MAASClientPool) -> None:
    """Register MAAS deployment information tools on a FastMCP app."""

    @mcp.tool(
        title="Get MAAS Info",
        description="Return MAAS instance metadata: version, UUID, active controllers, and deployment statistics.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def get_maas_info() -> str:
        async def operation(client: MAASClient) -> str:
            config_response, racks_response = await asyncio.gather(
                client.get(_CONFIG_PATH),
                client.get(_RACKS_PATH),
            )
            maas_info = _build_maas_info(
                config_response.json(),
                racks_response.json(),
            )
            return _format_maas_info(maas_info)

        return await run_tool("get_maas_info", {}, pool, operation)
