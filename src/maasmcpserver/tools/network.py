# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MCP tools for MAAS network fabric, VLAN, and subnet management."""

from collections.abc import Awaitable, Callable
from typing import Annotated, Any

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from maasmcpserver.client import MAASClient, MAASClientPool
from maasmcpserver.logging_events import log_tool_outcome, log_tool_received
from maasmcpserver.middleware import get_api_key, get_session_id
from maasmcpserver.models.network import Fabric, Subnet, VLAN
from maasmcpserver.tools.common import (
    fetch_all_pages,
    items_from_payload,
    markdown_table,
    safe_text,
)
from maasmcpserver.tools.common import run_tool as _run_tool

_FABRICS_PATH = "/MAAS/a/v3/fabrics"
_FABRIC_PATH = "/MAAS/a/v3/fabrics/{fabric_id}"
_VLANS_PATH = "/MAAS/a/v3/fabrics/{fabric_id}/vlans"
_VLAN_PATH = "/MAAS/a/v3/fabrics/{fabric_id}/vlans/{vlan_id}"
_SUBNETS_PATH = "/MAAS/a/v3/fabrics/{fabric_id}/vlans/{vlan_id}/subnets"
_SUBNET_PATH = (
    "/MAAS/a/v3/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}"
)


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


def _build_body(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _optional_text(value: Any) -> str | None:
    if value in (None, "", []):
        return None
    return str(value)


def _reference_text(value: Any, default: str = "-") -> str:
    if isinstance(value, dict):
        for key in ("id", "name", "vid", "cidr"):
            candidate = value.get(key)
            if candidate not in (None, "", []):
                return str(candidate)
        return default
    return safe_text(value, default=default)


def _int_value(value: Any, default: int = 0) -> int:
    if isinstance(value, dict):
        value = value.get("id") or value.get("vid")
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bool_text(value: Any) -> str:
    return "on" if bool(value) else "off"


def _dns_servers_text(value: Any) -> str:
    if value in (None, "", []):
        return "-"
    if isinstance(value, list):
        servers = [str(item) for item in value if item not in (None, "")]
        return ", ".join(servers) if servers else "-"
    return str(value)


def _fabric_from_payload(payload: dict[str, Any]) -> Fabric:
    fabric_id = _int_value(payload.get("id"))
    return Fabric.model_validate(
        {
            "id": fabric_id,
            "name": safe_text(
                payload.get("name"),
                default=f"fabric-{fabric_id}",
            ),
            "class_type": _optional_text(payload.get("class_type")),
            "description": _optional_text(payload.get("description")),
        }
    )


def _vlan_from_payload(payload: dict[str, Any], fabric_id: int) -> VLAN:
    return VLAN.model_validate(
        {
            "id": _int_value(payload.get("id")),
            "vid": _int_value(payload.get("vid")),
            "name": _optional_text(payload.get("name")),
            "fabric": _reference_text(payload.get("fabric"), str(fabric_id)),
            "mtu": _int_value(payload.get("mtu"), default=1500),
            "dhcp_on": bool(payload.get("dhcp_on", False)),
        }
    )


def _subnet_from_payload(
    payload: dict[str, Any],
    fabric_id: int,
    vlan_id: int,
) -> Subnet:
    cidr = safe_text(payload.get("cidr"), default="unknown")
    return Subnet.model_validate(
        {
            "id": _int_value(payload.get("id")),
            "name": safe_text(payload.get("name"), default=cidr),
            "cidr": cidr,
            "gateway_ip": _optional_text(payload.get("gateway_ip")),
            "dns_servers": [
                str(item)
                for item in payload.get("dns_servers", [])
                if item not in (None, "")
            ],
            "vlan": _int_value(payload.get("vlan"), default=vlan_id),
            "fabric": _reference_text(payload.get("fabric"), str(fabric_id)),
        }
    )


def _format_fabric_detail(payload: dict[str, Any]) -> str:
    fabric = _fabric_from_payload(payload)
    lines = [
        "Fabric",
        f"ID: {fabric.id}",
        f"Name: {fabric.name}",
        f"Class Type: {safe_text(fabric.class_type)}",
        f"Description: {safe_text(fabric.description)}",
    ]

    vlan_items = items_from_payload(payload.get("vlans", []))
    if vlan_items:
        vlans = [_vlan_from_payload(item, fabric.id) for item in vlan_items]
        rows = [
            [
                str(vlan.id),
                str(vlan.vid),
                safe_text(vlan.name),
                str(vlan.mtu),
                _bool_text(vlan.dhcp_on),
            ]
            for vlan in vlans
        ]
        lines.extend(
            [
                "",
                "VLANs",
                markdown_table(["ID", "VID", "Name", "MTU", "DHCP"], rows),
            ]
        )

    return "\n".join(lines)


def _format_vlan_detail(payload: dict[str, Any], fabric_id: int) -> str:
    vlan = _vlan_from_payload(payload, fabric_id)
    lines = [
        "VLAN",
        f"ID: {vlan.id}",
        f"VID: {vlan.vid}",
        f"Name: {safe_text(vlan.name)}",
        f"Fabric: {vlan.fabric}",
        f"MTU: {vlan.mtu}",
        f"DHCP: {_bool_text(vlan.dhcp_on)}",
    ]

    relay_target = payload.get("dhcp_relay_target")
    if relay_target not in (None, "", []):
        lines.append(
            f"DHCP Relay Target: {_reference_text(relay_target, default='-')}"
        )

    return "\n".join(lines)


def _format_subnet_detail(
    payload: dict[str, Any],
    fabric_id: int,
    vlan_id: int,
) -> str:
    subnet = _subnet_from_payload(payload, fabric_id, vlan_id)
    return "\n".join(
        [
            "Subnet",
            f"ID: {subnet.id}",
            f"Name: {subnet.name}",
            f"CIDR: {subnet.cidr}",
            f"Gateway: {safe_text(subnet.gateway_ip)}",
            f"DNS Servers: {_dns_servers_text(subnet.dns_servers)}",
            f"Fabric: {subnet.fabric}",
            f"VLAN: {subnet.vlan}",
        ]
    )


def register(mcp: FastMCP, pool: MAASClientPool) -> None:
    """Register network management tools on a FastMCP app."""

    @mcp.resource(
        "maas://fabrics",
        name="Network Fabrics",
        description="All network fabrics defined in MAAS.",
        mime_type="text/plain",
    )
    async def list_fabrics() -> str:
        client = make_client(pool, get_api_key())
        try:
            items = await fetch_all_pages(client, _FABRICS_PATH)
            fabrics = [_fabric_from_payload(item) for item in items]
            if not fabrics:
                return "No fabrics found."

            rows = [
                [
                    str(fabric.id),
                    fabric.name,
                    safe_text(fabric.class_type),
                    safe_text(fabric.description),
                ]
                for fabric in fabrics
            ]
            return markdown_table(
                ["ID", "Name", "Class Type", "Description"],
                rows,
            )
        finally:
            if getattr(client, "_close_after_use", False):
                await client.client.aclose()

    @mcp.tool(
        title="Get Fabric",
        description="Fetch and return full details for a single fabric as a formatted summary. Use when the user asks 'show me fabric <id>', 'get fabric details', or 'what is fabric <id>'. Do NOT use to list all fabrics — use list_fabrics instead. Returns fabric ID, name, class type, and associated VLANs.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def get_fabric(
        fabric_id: Annotated[
            int,
            Field(
                description="Integer ID of the fabric to retrieve. Obtain from list_fabrics if the user has not provided it explicitly."
            ),
        ],
    ) -> str:
        async def _operation(client: MAASClient) -> str:
            response = await client.get(
                _FABRIC_PATH,
                path_params={"fabric_id": fabric_id},
            )
            return _format_fabric_detail(response.json())

        return await run_tool(
            "get_fabric",
            {"fabric_id": fabric_id},
            pool,
            _operation,
        )

    @mcp.tool(
        title="List VLANs",
        description="List all VLANs in a fabric, returned as a paginated markdown table. Use when the user asks 'list VLANs', 'show VLANs in fabric <id>', or 'what VLANs exist'. Requires a fabric_id — call list_fabrics first if unknown. Returns columns: ID, VID, Name, MTU, DHCP.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def list_vlans(
        fabric_id: Annotated[
            int,
            Field(
                description="Integer ID of the fabric whose VLANs to list. Obtain from list_fabrics if not provided by the user."
            ),
        ],
        page: Annotated[
            int,
            Field(
                description="1-based page number for paginated results. Defaults to 1."
            ),
        ] = 1,
        page_size: Annotated[
            int,
            Field(
                description="Number of VLAN rows to return per page. Defaults to 100."
            ),
        ] = 100,
    ) -> str:
        async def _operation(client: MAASClient) -> str:
            response = await client.get(
                _VLANS_PATH,
                path_params={"fabric_id": fabric_id},
                query_params={"page": page, "size": page_size},
            )
            vlans = [
                _vlan_from_payload(item, fabric_id)
                for item in items_from_payload(response.json())
            ]
            if not vlans:
                return f"No VLANs found in fabric {fabric_id}."

            rows = [
                [
                    str(vlan.id),
                    str(vlan.vid),
                    safe_text(vlan.name),
                    str(vlan.mtu),
                    _bool_text(vlan.dhcp_on),
                ]
                for vlan in vlans
            ]
            return markdown_table(
                ["ID", "VID", "Name", "MTU", "DHCP"],
                rows,
            )

        return await run_tool(
            "list_vlans",
            {
                "fabric_id": fabric_id,
                "page": page,
                "page_size": page_size,
            },
            pool,
            _operation,
        )

    @mcp.tool(
        title="Get VLAN",
        description="Fetch and return full details for a single VLAN as a formatted summary. Use when the user asks 'show VLAN <id>', 'get VLAN details', or 'describe VLAN <id> in fabric <id>'. Do NOT use to list VLANs — use list_vlans instead. Returns VID, name, MTU, DHCP status, and relay target.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def get_vlan(
        fabric_id: Annotated[
            int,
            Field(
                description="Integer ID of the fabric that owns the VLAN. Obtain from list_fabrics if not provided by the user."
            ),
        ],
        vlan_id: Annotated[
            int,
            Field(
                description="Integer ID of the VLAN to retrieve. Obtain from list_vlans if not provided by the user."
            ),
        ],
    ) -> str:
        async def _operation(client: MAASClient) -> str:
            response = await client.get(
                _VLAN_PATH,
                path_params={"fabric_id": fabric_id, "vlan_id": vlan_id},
            )
            return _format_vlan_detail(response.json(), fabric_id)

        return await run_tool(
            "get_vlan",
            {"fabric_id": fabric_id, "vlan_id": vlan_id},
            pool,
            _operation,
        )

    @mcp.tool(
        title="List Subnets",
        description="List all subnets within a specific VLAN, returned as a paginated markdown table. Use when the user asks 'list subnets', 'show subnets in VLAN <id>', or 'what subnets are in fabric <id>'. Both fabric_id and vlan_id are required — call list_fabrics then list_vlans first if unknown. Returns columns: ID, Name, CIDR, Gateway, DNS Servers.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def list_subnets(
        fabric_id: Annotated[
            int,
            Field(
                description="Integer ID of the fabric. Obtain from list_fabrics if not provided by the user."
            ),
        ],
        vlan_id: Annotated[
            int,
            Field(
                description="Integer ID of the VLAN whose subnets to list. Obtain from list_vlans if not provided by the user."
            ),
        ],
        page: Annotated[
            int,
            Field(
                description="1-based page number for paginated results. Defaults to 1."
            ),
        ] = 1,
        page_size: Annotated[
            int,
            Field(
                description="Number of subnet rows to return per page. Defaults to 100."
            ),
        ] = 100,
    ) -> str:
        async def _operation(client: MAASClient) -> str:
            response = await client.get(
                _SUBNETS_PATH,
                path_params={"fabric_id": fabric_id, "vlan_id": vlan_id},
                query_params={"page": page, "size": page_size},
            )
            subnets = [
                _subnet_from_payload(item, fabric_id, vlan_id)
                for item in items_from_payload(response.json())
            ]
            if not subnets:
                return (
                    f"No subnets found in fabric {fabric_id}, VLAN {vlan_id}."
                )

            rows = [
                [
                    str(subnet.id),
                    subnet.name,
                    subnet.cidr,
                    safe_text(subnet.gateway_ip),
                    _dns_servers_text(subnet.dns_servers),
                ]
                for subnet in subnets
            ]
            return markdown_table(
                ["ID", "Name", "CIDR", "Gateway", "DNS Servers"],
                rows,
            )

        return await run_tool(
            "list_subnets",
            {
                "fabric_id": fabric_id,
                "vlan_id": vlan_id,
                "page": page,
                "page_size": page_size,
            },
            pool,
            _operation,
        )

    @mcp.tool(
        title="Get Subnet",
        description="Fetch and return full details for a single subnet as a formatted summary, including CIDR, gateway, DNS servers, and VLAN membership. Use when the user asks 'show subnet <id>', 'get subnet details', or 'describe subnet <id>'. Do NOT use to list subnets — use list_subnets instead.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def get_subnet(
        fabric_id: Annotated[
            int,
            Field(
                description="Integer ID of the fabric. Obtain from list_fabrics if not provided by the user."
            ),
        ],
        vlan_id: Annotated[
            int,
            Field(
                description="Integer ID of the VLAN that contains the subnet. Obtain from list_vlans if not provided by the user."
            ),
        ],
        subnet_id: Annotated[
            int,
            Field(
                description="Integer ID of the subnet to retrieve. Obtain from list_subnets if not provided by the user."
            ),
        ],
    ) -> str:
        async def _operation(client: MAASClient) -> str:
            response = await client.get(
                _SUBNET_PATH,
                path_params={
                    "fabric_id": fabric_id,
                    "vlan_id": vlan_id,
                    "subnet_id": subnet_id,
                },
            )
            return _format_subnet_detail(response.json(), fabric_id, vlan_id)

        return await run_tool(
            "get_subnet",
            {
                "fabric_id": fabric_id,
                "vlan_id": vlan_id,
                "subnet_id": subnet_id,
            },
            pool,
            _operation,
        )

    @mcp.tool(
        title="Create Fabric",
        description="Create a new network fabric in MAAS and return its ID and name. Use when the user asks 'create a fabric', 'add a new fabric', or 'set up a fabric named <name>'. Do NOT use to create VLANs or subnets — use create_vlan or create_subnet for those. Returns the new fabric ID and name.",
    )
    async def create_fabric(
        name: Annotated[
            str,
            Field(
                description="Human-readable name for the new fabric. Must be a non-empty string provided by the user."
            ),
        ],
        class_type: Annotated[
            str | None,
            Field(
                description="Optional class type label (string) to categorise the fabric, e.g. 'flat'. Omit or pass null if not specified by the user."
            ),
        ] = None,
    ) -> str:
        async def _operation(client: MAASClient) -> str:
            body = _build_body({"name": name, "class_type": class_type})
            response = await client.post(_FABRICS_PATH, body=body)
            fabric = _fabric_from_payload(response.json())
            return f"Fabric created: ID={fabric.id}, Name={fabric.name}"

        return await run_tool(
            "create_fabric",
            {"name": name, "class_type": class_type},
            pool,
            _operation,
        )

    @mcp.tool(
        title="Update Fabric",
        description="Update the name or class type of an existing fabric and return the updated details. Use when the user asks 'rename fabric <id>', 'update fabric', or 'change class type of fabric <id>'. Do NOT use to modify VLANs or subnets — use update_vlan or update_subnet instead. Returns the updated fabric summary.",
    )
    async def update_fabric(
        fabric_id: Annotated[
            int,
            Field(
                description="Integer ID of the fabric to update. Obtain from list_fabrics if not provided by the user."
            ),
        ],
        name: Annotated[
            str | None,
            Field(
                description="New name string for the fabric. Omit or pass null to leave unchanged."
            ),
        ] = None,
        class_type: Annotated[
            str | None,
            Field(
                description="New class type label string for the fabric. Omit or pass null to leave unchanged."
            ),
        ] = None,
    ) -> str:
        async def _operation(client: MAASClient) -> str:
            body = _build_body({"name": name, "class_type": class_type})
            response = await client.put(
                _FABRIC_PATH,
                path_params={"fabric_id": fabric_id},
                body=body,
            )
            return _format_fabric_detail(response.json())

        return await run_tool(
            "update_fabric",
            {
                "fabric_id": fabric_id,
                "name": name,
                "class_type": class_type,
            },
            pool,
            _operation,
        )

    @mcp.tool(
        title="Delete Fabric",
        description="Permanently and irreversibly delete a fabric and ALL of its VLANs and subnets from MAAS. Use ONLY when the user explicitly confirms deletion with phrases like 'delete fabric <id>', 'remove fabric <id>', or 'destroy fabric <id>'. Do NOT use if the user is asking to rename, inspect, or list fabrics. Do NOT use if the user has not confirmed the destructive action. This cannot be undone. Returns confirmation of the deleted fabric name and ID.",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def delete_fabric(
        fabric_id: Annotated[
            int,
            Field(
                description="Integer ID of the fabric to permanently delete. Obtain from list_fabrics if not provided by the user. Confirm with the user before passing this value."
            ),
        ],
    ) -> str:
        async def _operation(client: MAASClient) -> str:
            get_response = await client.get(
                _FABRIC_PATH,
                path_params={"fabric_id": fabric_id},
            )
            fabric = _fabric_from_payload(get_response.json())
            await client.delete(
                _FABRIC_PATH,
                path_params={"fabric_id": fabric_id},
            )
            return f"Fabric deleted: ID={fabric_id}, Name={fabric.name}"

        return await run_tool(
            "delete_fabric",
            {"fabric_id": fabric_id},
            pool,
            _operation,
        )

    @mcp.tool(
        title="Create VLAN",
        description="Create a new 802.1Q VLAN inside a fabric and return its details. Use when the user asks 'create a VLAN', 'add VLAN <vid> to fabric <id>', or 'set up a VLAN'. Do NOT use to create subnets — use create_subnet instead. Requires a valid VID (1–4094). Returns the new VLAN ID, VID, and name.",
    )
    async def create_vlan(
        fabric_id: Annotated[
            int,
            Field(
                description="Integer ID of the fabric in which to create the VLAN. Obtain from list_fabrics if not provided by the user."
            ),
        ],
        vid: Annotated[
            int,
            Field(
                description="802.1Q VLAN ID integer in the range 1–4094. Must be unique within the fabric. Provided by the user."
            ),
        ],
        name: Annotated[
            str | None,
            Field(
                description="Optional human-readable name string for the VLAN. Omit or pass null if not specified by the user."
            ),
        ] = None,
        mtu: Annotated[
            int | None,
            Field(
                description="Optional MTU integer for the VLAN (e.g. 1500 or 9000). Omit or pass null to use the fabric default."
            ),
        ] = None,
        dhcp_relay_target: Annotated[
            int | None,
            Field(
                description="Optional integer VLAN ID to relay DHCP traffic to. Obtain from list_vlans if needed. Omit or pass null if DHCP relay is not required."
            ),
        ] = None,
    ) -> str:
        async def _operation(client: MAASClient) -> str:
            body = _build_body(
                {
                    "vid": vid,
                    "name": name,
                    "mtu": mtu,
                    "dhcp_relay_target": dhcp_relay_target,
                }
            )
            response = await client.post(
                _VLANS_PATH,
                path_params={"fabric_id": fabric_id},
                body=body,
            )
            vlan = _vlan_from_payload(response.json(), fabric_id)
            return (
                "VLAN created: "
                f"VID={vlan.vid}, Name={safe_text(vlan.name)}, ID={vlan.id}"
            )

        return await run_tool(
            "create_vlan",
            {
                "fabric_id": fabric_id,
                "vid": vid,
                "name": name,
                "mtu": mtu,
                "dhcp_relay_target": dhcp_relay_target,
            },
            pool,
            _operation,
        )

    @mcp.tool(
        title="Update VLAN",
        description="Update one or more properties of an existing VLAN (name, VID, MTU) and return the updated details. Use when the user asks 'rename VLAN <id>', 'change MTU of VLAN', 'update VLAN <id> in fabric <id>', or similar. Do NOT use to delete or create VLANs. Only fields provided will be changed. Returns the updated VLAN summary.",
    )
    async def update_vlan(
        fabric_id: Annotated[
            int,
            Field(
                description="Integer ID of the fabric that owns the VLAN. Obtain from list_fabrics if not provided by the user."
            ),
        ],
        vlan_id: Annotated[
            int,
            Field(
                description="Integer ID of the VLAN to update. Obtain from list_vlans if not provided by the user."
            ),
        ],
        vid: Annotated[
            int | None,
            Field(
                description="New 802.1Q VID integer (1–4094) to assign. Omit or pass null to leave unchanged."
            ),
        ] = None,
        name: Annotated[
            str | None,
            Field(
                description="New name string for the VLAN. Omit or pass null to leave unchanged."
            ),
        ] = None,
        mtu: Annotated[
            int | None,
            Field(
                description="New MTU integer for the VLAN (e.g. 1500 or 9000). Omit or pass null to leave unchanged."
            ),
        ] = None,
    ) -> str:
        async def _operation(client: MAASClient) -> str:
            body = _build_body({"vid": vid, "name": name, "mtu": mtu})
            response = await client.put(
                _VLAN_PATH,
                path_params={"fabric_id": fabric_id, "vlan_id": vlan_id},
                body=body,
            )
            return _format_vlan_detail(response.json(), fabric_id)

        return await run_tool(
            "update_vlan",
            {
                "fabric_id": fabric_id,
                "vlan_id": vlan_id,
                "vid": vid,
                "name": name,
                "mtu": mtu,
            },
            pool,
            _operation,
        )

    @mcp.tool(
        title="Delete VLAN",
        description="Permanently and irreversibly delete a VLAN and all its subnets from a fabric. Use ONLY when the user explicitly confirms deletion with phrases like 'delete VLAN <id>', 'remove VLAN <vid>', or 'destroy VLAN <id> in fabric <id>'. Do NOT use if the user is asking to inspect, list, or rename VLANs. Do NOT use if the user has not confirmed the destructive action. This cannot be undone. Returns confirmation of the deleted VLAN VID and ID.",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def delete_vlan(
        fabric_id: Annotated[
            int,
            Field(
                description="Integer ID of the fabric that owns the VLAN. Obtain from list_fabrics if not provided by the user."
            ),
        ],
        vlan_id: Annotated[
            int,
            Field(
                description="Integer ID of the VLAN to permanently delete. Obtain from list_vlans if not provided by the user. Confirm with the user before passing this value."
            ),
        ],
    ) -> str:
        async def _operation(client: MAASClient) -> str:
            try:
                get_response = await client.get(
                    _VLAN_PATH,
                    path_params={
                        "fabric_id": fabric_id,
                        "vlan_id": vlan_id,
                    },
                )
            except httpx.HTTPStatusError as error:
                if error.response.status_code == 404:
                    return (
                        'Error (error_code: "not_found"): VLAN ID='
                        f"{vlan_id} was not found in fabric {fabric_id}."
                    )
                raise

            vlan = _vlan_from_payload(get_response.json(), fabric_id)

            try:
                await client.delete(
                    _VLAN_PATH,
                    path_params={
                        "fabric_id": fabric_id,
                        "vlan_id": vlan_id,
                    },
                )
            except httpx.HTTPStatusError as error:
                if error.response.status_code == 404:
                    return (
                        'Error (error_code: "not_found"): VLAN ID='
                        f"{vlan_id} was not found in fabric {fabric_id}."
                    )
                raise

            return (
                "VLAN deleted: "
                f"VID={vlan.vid}, Name={safe_text(vlan.name)}, ID={vlan_id}"
            )

        return await run_tool(
            "delete_vlan",
            {"fabric_id": fabric_id, "vlan_id": vlan_id},
            pool,
            _operation,
        )

    @mcp.tool(
        title="Create Subnet",
        description="Create a new IP subnet within a VLAN and return its details. Use when the user asks 'create a subnet', 'add subnet <cidr> to VLAN <id>', or 'set up a network <cidr>'. Requires both fabric_id and vlan_id — call list_fabrics then list_vlans first if unknown. CIDR must be in standard notation (e.g. '10.0.0.0/24'). Returns the new subnet ID, CIDR, and name.",
    )
    async def create_subnet(
        fabric_id: Annotated[
            int,
            Field(
                description="Integer ID of the fabric. Obtain from list_fabrics if not provided by the user."
            ),
        ],
        vlan_id: Annotated[
            int,
            Field(
                description="Integer ID of the VLAN to attach the subnet to. Obtain from list_vlans if not provided by the user."
            ),
        ],
        cidr: Annotated[
            str,
            Field(
                description=(
                    "IP subnet in CIDR notation, e.g. '192.168.1.0/24' or '10.0.0.0/8'. Must be a valid, non-overlapping CIDR provided by the user."
                )
            ),
        ],
        name: Annotated[
            str | None,
            Field(
                description="Optional human-readable name string for the subnet. Omit or pass null if not specified by the user."
            ),
        ] = None,
        gateway_ip: Annotated[
            str | None,
            Field(
                description="Optional gateway IPv4/IPv6 address string (e.g. '192.168.1.1'). Must be within the subnet CIDR. Omit or pass null if not specified."
            ),
        ] = None,
        dns_servers: Annotated[
            list[str] | None,
            Field(
                description="Optional list of DNS server IP address strings (e.g. ['8.8.8.8', '1.1.1.1']). Omit or pass null if not specified by the user."
            ),
        ] = None,
    ) -> str:
        async def _operation(client: MAASClient) -> str:
            body = _build_body(
                {
                    "cidr": cidr,
                    "name": name,
                    "gateway_ip": gateway_ip,
                    "dns_servers": dns_servers,
                }
            )
            response = await client.post(
                _SUBNETS_PATH,
                path_params={"fabric_id": fabric_id, "vlan_id": vlan_id},
                body=body,
            )
            subnet = _subnet_from_payload(response.json(), fabric_id, vlan_id)
            return (
                "Subnet created: "
                f"CIDR={subnet.cidr}, Name={subnet.name}, ID={subnet.id}"
            )

        return await run_tool(
            "create_subnet",
            {
                "fabric_id": fabric_id,
                "vlan_id": vlan_id,
                "cidr": cidr,
                "name": name,
                "gateway_ip": gateway_ip,
                "dns_servers": dns_servers,
            },
            pool,
            _operation,
        )

    @mcp.tool(
        title="Update Subnet",
        description="Update one or more properties of an existing subnet (name, CIDR, gateway, DNS servers) and return the updated details. Use when the user asks 'update subnet <id>', 'change gateway of subnet', 'rename subnet <id>', or 'set DNS on subnet <id>'. Do NOT use to delete or create subnets. Only fields provided will be changed. Returns the updated subnet summary.",
    )
    async def update_subnet(
        fabric_id: Annotated[
            int,
            Field(
                description="Integer ID of the fabric. Obtain from list_fabrics if not provided by the user."
            ),
        ],
        vlan_id: Annotated[
            int,
            Field(
                description="Integer ID of the VLAN that contains the subnet. Obtain from list_vlans if not provided by the user."
            ),
        ],
        subnet_id: Annotated[
            int,
            Field(
                description="Integer ID of the subnet to update. Obtain from list_subnets if not provided by the user."
            ),
        ],
        name: Annotated[
            str | None,
            Field(
                description="New name string for the subnet. Omit or pass null to leave unchanged."
            ),
        ] = None,
        cidr: Annotated[
            str | None,
            Field(
                description="New CIDR notation string for the subnet (e.g. '10.0.1.0/24'). Omit or pass null to leave unchanged."
            ),
        ] = None,
        gateway_ip: Annotated[
            str | None,
            Field(
                description="New gateway IPv4/IPv6 address string. Must be within the subnet CIDR. Omit or pass null to leave unchanged."
            ),
        ] = None,
        dns_servers: Annotated[
            list[str] | None,
            Field(
                description="New list of DNS server IP address strings (e.g. ['8.8.8.8']). Replaces the existing list. Omit or pass null to leave unchanged."
            ),
        ] = None,
    ) -> str:
        async def _operation(client: MAASClient) -> str:
            body = _build_body(
                {
                    "name": name,
                    "cidr": cidr,
                    "gateway_ip": gateway_ip,
                    "dns_servers": dns_servers,
                }
            )
            response = await client.put(
                _SUBNET_PATH,
                path_params={
                    "fabric_id": fabric_id,
                    "vlan_id": vlan_id,
                    "subnet_id": subnet_id,
                },
                body=body,
            )
            return _format_subnet_detail(response.json(), fabric_id, vlan_id)

        return await run_tool(
            "update_subnet",
            {
                "fabric_id": fabric_id,
                "vlan_id": vlan_id,
                "subnet_id": subnet_id,
                "name": name,
                "cidr": cidr,
                "gateway_ip": gateway_ip,
                "dns_servers": dns_servers,
            },
            pool,
            _operation,
        )

    @mcp.tool(
        title="Delete Subnet",
        description="Permanently and irreversibly delete a subnet from MAAS. Use ONLY when the user explicitly confirms deletion with phrases like 'delete subnet <id>', 'remove subnet <cidr>', or 'destroy subnet <id>'. Do NOT use if the user is asking to inspect, list, or modify subnets. Do NOT use if the user has not confirmed the destructive action. This cannot be undone. Returns confirmation of the deleted subnet CIDR and ID.",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def delete_subnet(
        fabric_id: Annotated[
            int,
            Field(
                description="Integer ID of the fabric. Obtain from list_fabrics if not provided by the user."
            ),
        ],
        vlan_id: Annotated[
            int,
            Field(
                description="Integer ID of the VLAN that contains the subnet. Obtain from list_vlans if not provided by the user."
            ),
        ],
        subnet_id: Annotated[
            int,
            Field(
                description="Integer ID of the subnet to permanently delete. Obtain from list_subnets if not provided by the user. Confirm with the user before passing this value."
            ),
        ],
    ) -> str:
        async def _operation(client: MAASClient) -> str:
            try:
                get_response = await client.get(
                    _SUBNET_PATH,
                    path_params={
                        "fabric_id": fabric_id,
                        "vlan_id": vlan_id,
                        "subnet_id": subnet_id,
                    },
                )
            except httpx.HTTPStatusError as error:
                if error.response.status_code == 404:
                    return (
                        'Error (error_code: "not_found"): Subnet ID='
                        f"{subnet_id} was not found in fabric {fabric_id}, "
                        f"VLAN {vlan_id}."
                    )
                raise

            subnet = _subnet_from_payload(
                get_response.json(),
                fabric_id,
                vlan_id,
            )

            try:
                await client.delete(
                    _SUBNET_PATH,
                    path_params={
                        "fabric_id": fabric_id,
                        "vlan_id": vlan_id,
                        "subnet_id": subnet_id,
                    },
                )
            except httpx.HTTPStatusError as error:
                if error.response.status_code == 404:
                    return (
                        'Error (error_code: "not_found"): Subnet ID='
                        f"{subnet_id} was not found in fabric {fabric_id}, "
                        f"VLAN {vlan_id}."
                    )
                raise

            return (
                "Subnet deleted: "
                f"CIDR={subnet.cidr}, Name={subnet.name}, ID={subnet_id} "
                f"(Fabric {fabric_id}, VLAN {vlan_id})"
            )

        return await run_tool(
            "delete_subnet",
            {
                "fabric_id": fabric_id,
                "vlan_id": vlan_id,
                "subnet_id": subnet_id,
            },
            pool,
            _operation,
        )
