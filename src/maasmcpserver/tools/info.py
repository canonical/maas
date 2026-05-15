# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MCP resource for MAAS deployment information."""

import asyncio
from typing import Any

from mcp.server.fastmcp import FastMCP

from maasmcpserver.client import MAASClient, MAASClientPool
from maasmcpserver.middleware import get_api_key
from maasmcpserver.models.info import MAASInfo, RackController
from maasmcpserver.tools.common import items_from_payload, safe_text

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
    """Register MAAS deployment information resources on a FastMCP app."""

    @mcp.resource(
        "maas://info",
        name="MAAS Info",
        description="MAAS instance metadata: deployment name and active rack controllers.",
        mime_type="text/plain",
    )
    async def get_maas_info() -> str:
        client = make_client(pool, get_api_key())
        try:
            config_response, racks_response = await asyncio.gather(
                client.get(_CONFIG_PATH),
                client.get(_RACKS_PATH),
            )
            maas_info = _build_maas_info(
                config_response.json(),
                racks_response.json(),
            )
            return _format_maas_info(maas_info)
        finally:
            if getattr(client, "_close_after_use", False):
                await client.client.aclose()
