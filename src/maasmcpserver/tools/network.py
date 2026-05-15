# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MCP tools for MAAS network fabric, VLAN, and subnet management."""

from collections.abc import Awaitable, Callable
from typing import Annotated, Any

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from maasmcpserver.client import MAASClient, MAASClientPool
from maasmcpserver.logging_events import log_tool_outcome, log_tool_received
from maasmcpserver.middleware import get_api_key, get_session_id
from maasmcpserver.models.network import Fabric, Subnet, VLAN
from maasmcpserver.tools.common import (
    items_from_payload,
    markdown_table,
    run_tool as _run_tool,
    safe_text,
)

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
    result = await _run_tool(
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
    if result == (
        'Error (error_code: "permission_denied"): '
        'Permission denied (HTTP 403).'
    ):
        return "Error: Permission denied (HTTP 403)"
    if result.startswith('Error (error_code: "http_error"): HTTP 404: '):
        detail = result.removeprefix(
            'Error (error_code: "http_error"): HTTP 404: '
        )
        return f"Error: Resource not found (HTTP 404): {detail}"
    return result


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


def _response_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        detail = (
            payload.get("detail")
            or payload.get("message")
            or payload.get("error")
        )
        if detail not in (None, ""):
            if isinstance(detail, list):
                return ", ".join(str(item) for item in detail)
            return str(detail)

    text = response.text.strip()
    if text:
        return text[:200]
    return "Request failed."


def _not_found_result(detail: str) -> str:
    return f"Error: Resource not found (HTTP 404): {detail}"


def _http_error_result(error: httpx.HTTPStatusError) -> str:
    status_code = error.response.status_code
    detail = _response_detail(error.response)
    if status_code == 404:
        return _not_found_result(detail)
    return f"Error: HTTP {status_code}: {detail}"


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

    @mcp.tool(
        title="List Fabrics",
        description="Return a paginated list of all network fabrics defined in MAAS.",
    )
    async def list_fabrics(
        page: Annotated[
            int,
            Field(description="Page number (1-based)."),
        ] = 1,
        page_size: Annotated[
            int,
            Field(description="Number of results per page."),
        ] = 100,
    ) -> str:
        async def _operation(client: MAASClient) -> str:
            response = await client.get(
                _FABRICS_PATH,
                query_params={"page": page, "size": page_size},
            )
            fabrics = [
                _fabric_from_payload(item)
                for item in items_from_payload(response.json())
            ]
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

        return await run_tool(
            "list_fabrics",
            {"page": page, "page_size": page_size},
            pool,
            _operation,
        )

    @mcp.tool(
        title="Get Fabric",
        description="Return details for a single fabric by its numeric ID.",
    )
    async def get_fabric(
        fabric_id: Annotated[
            int,
            Field(description="Numeric ID of the fabric."),
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
        description="Return a paginated list of VLANs belonging to a specific fabric.",
    )
    async def list_vlans(
        fabric_id: Annotated[
            int,
            Field(description="Numeric ID of the fabric."),
        ],
        page: Annotated[
            int,
            Field(description="Page number (1-based)."),
        ] = 1,
        page_size: Annotated[
            int,
            Field(description="Number of results per page."),
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
        description="Return details for a single VLAN identified by fabric ID and VLAN ID.",
    )
    async def get_vlan(
        fabric_id: Annotated[
            int,
            Field(description="Numeric ID of the fabric."),
        ],
        vlan_id: Annotated[
            int,
            Field(description="Numeric ID of the VLAN."),
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
        description="Return a paginated list of subnets within a specific VLAN (fabric_id and vlan_id are required).",
    )
    async def list_subnets(
        fabric_id: Annotated[
            int,
            Field(description="Numeric ID of the fabric."),
        ],
        vlan_id: Annotated[
            int,
            Field(description="Numeric ID of the VLAN."),
        ],
        page: Annotated[
            int,
            Field(description="Page number (1-based)."),
        ] = 1,
        page_size: Annotated[
            int,
            Field(description="Number of results per page."),
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
        description="Return details for a single subnet by its numeric ID, including CIDR, gateway, DNS servers, and VLAN membership.",
    )
    async def get_subnet(
        fabric_id: Annotated[
            int,
            Field(description="Numeric ID of the fabric."),
        ],
        vlan_id: Annotated[
            int,
            Field(description="Numeric ID of the VLAN."),
        ],
        subnet_id: Annotated[
            int,
            Field(description="Numeric ID of the subnet."),
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
        description="Create a new network fabric with an optional name and class type.",
    )
    async def create_fabric(
        name: Annotated[
            str,
            Field(description="Name for the new fabric."),
        ],
        class_type: Annotated[
            str | None,
            Field(description="Optional class type label for the fabric."),
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
        description="Update the name or class type of an existing fabric.",
    )
    async def update_fabric(
        fabric_id: Annotated[
            int,
            Field(description="Numeric ID of the fabric to update."),
        ],
        name: Annotated[
            str | None,
            Field(description="New name for the fabric."),
        ] = None,
        class_type: Annotated[
            str | None,
            Field(description="New class type label."),
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
        description="Permanently delete a fabric and all its VLANs from MAAS.",
    )
    async def delete_fabric(
        fabric_id: Annotated[
            int,
            Field(description="Numeric ID of the fabric to delete."),
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
        description="Create a new VLAN in a fabric with a given VID and optional name, MTU, and DHCP relay settings.",
    )
    async def create_vlan(
        fabric_id: Annotated[
            int,
            Field(description="Numeric ID of the fabric to create the VLAN in."),
        ],
        vid: Annotated[
            int,
            Field(description="VLAN ID (802.1Q VID, 1–4094)."),
        ],
        name: Annotated[
            str | None,
            Field(description="Optional name for the VLAN."),
        ] = None,
        mtu: Annotated[
            int | None,
            Field(description="Optional MTU for the VLAN."),
        ] = None,
        dhcp_relay_target: Annotated[
            int | None,
            Field(description="Optional VLAN ID to relay DHCP to."),
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
        description="Update properties of an existing VLAN such as name, MTU, DHCP state, or relay VLAN.",
    )
    async def update_vlan(
        fabric_id: Annotated[
            int,
            Field(description="Numeric ID of the fabric."),
        ],
        vlan_id: Annotated[
            int,
            Field(description="Numeric ID of the VLAN to update."),
        ],
        vid: Annotated[
            int | None,
            Field(description="New VLAN ID (802.1Q VID)."),
        ] = None,
        name: Annotated[
            str | None,
            Field(description="New name for the VLAN."),
        ] = None,
        mtu: Annotated[
            int | None,
            Field(description="New MTU for the VLAN."),
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
        description="Permanently delete a VLAN from a fabric.",
    )
    async def delete_vlan(
        fabric_id: Annotated[
            int,
            Field(description="Numeric ID of the fabric."),
        ],
        vlan_id: Annotated[
            int,
            Field(description="Numeric ID of the VLAN to delete."),
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
                    return _not_found_result(
                        "VLAN ID="
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
                    return _not_found_result(
                        "VLAN ID="
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
        description="Create a new subnet with a CIDR, optionally specifying gateway, DNS servers, VLAN membership, and IP range management settings.",
    )
    async def create_subnet(
        fabric_id: Annotated[
            int,
            Field(description="Numeric ID of the fabric."),
        ],
        vlan_id: Annotated[
            int,
            Field(description="Numeric ID of the VLAN to attach the subnet to."),
        ],
        cidr: Annotated[
            str,
            Field(
                description=(
                    "CIDR notation for the subnet (e.g. '192.168.1.0/24')."
                )
            ),
        ],
        name: Annotated[
            str | None,
            Field(description="Optional name for the subnet."),
        ] = None,
        gateway_ip: Annotated[
            str | None,
            Field(description="Optional gateway IP address."),
        ] = None,
        dns_servers: Annotated[
            list[str] | None,
            Field(description="Optional list of DNS server IP addresses."),
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
        description="Update properties of an existing subnet such as name, CIDR, gateway, DNS servers, or VLAN membership.",
    )
    async def update_subnet(
        fabric_id: Annotated[
            int,
            Field(description="Numeric ID of the fabric."),
        ],
        vlan_id: Annotated[
            int,
            Field(description="Numeric ID of the VLAN."),
        ],
        subnet_id: Annotated[
            int,
            Field(description="Numeric ID of the subnet to update."),
        ],
        name: Annotated[
            str | None,
            Field(description="New name for the subnet."),
        ] = None,
        cidr: Annotated[
            str | None,
            Field(description="New CIDR notation for the subnet."),
        ] = None,
        gateway_ip: Annotated[
            str | None,
            Field(description="New gateway IP address."),
        ] = None,
        dns_servers: Annotated[
            list[str] | None,
            Field(description="New list of DNS server IP addresses."),
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
        description="Permanently delete a subnet from MAAS.",
    )
    async def delete_subnet(
        fabric_id: Annotated[
            int,
            Field(description="Numeric ID of the fabric."),
        ],
        vlan_id: Annotated[
            int,
            Field(description="Numeric ID of the VLAN."),
        ],
        subnet_id: Annotated[
            int,
            Field(description="Numeric ID of the subnet to delete."),
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
                    return _not_found_result(
                        "Subnet ID="
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
                    return _not_found_result(
                        "Subnet ID="
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
