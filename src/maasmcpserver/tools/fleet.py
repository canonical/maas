# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Fleet discovery MCP tools for MAAS machines, pools, and zones."""

from collections.abc import Awaitable, Callable
from typing import Annotated, Any

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from maasmcpserver.client import MAASClient, MAASClientPool
from maasmcpserver.logging_events import log_tool_outcome, log_tool_received
from maasmcpserver.middleware import get_api_key, get_session_id
from maasmcpserver.models.machines import (
    BlockDevice,
    InterfaceSummary,
    MachineDetail,
    MachineSummary,
)
from maasmcpserver.tools.common import (
    fetch_all_pages,
    items_from_payload,
    markdown_table,
)
from maasmcpserver.tools.common import run_tool as _run_tool

_MACHINES_PATH = "/MAAS/a/v3/machines"
_MACHINE_PATH = "/MAAS/a/v3/machines/{system_id}"
_INTERFACES_PATH = "/MAAS/a/v3/machines/{system_id}/interfaces"
_RESOURCE_POOLS_PATH = "/MAAS/a/v3/resource_pools"
_ZONES_PATH = "/MAAS/a/v3/zones"


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


def _machine_from_payload(payload: Any) -> dict[str, Any] | None:
    """Return a single machine mapping from a MAAS API response payload."""
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list) and items:
            first_item = items[0]
            if isinstance(first_item, dict):
                return first_item
        return payload
    if isinstance(payload, list) and payload:
        first_item = payload[0]
        if isinstance(first_item, dict):
            return first_item
    return None


def _text(value: Any, default: str | None = "-") -> str | None:
    """Convert a value to text while preserving empty-value defaults."""
    if value in (None, "", []):
        return default
    return str(value)


def _name(value: Any, default: str | None = "-") -> str | None:
    """Extract a display name from MAAS API values."""
    if isinstance(value, dict):
        for key in (
            "name",
            "username",
            "hostname",
            "system_id",
            "description",
            "id",
        ):
            nested = _text(value.get(key), default=None)
            if nested is not None:
                return nested
        return default
    if isinstance(value, list):
        names = [name for item in value if (name := _name(item, default=None))]
        return ", ".join(names) if names else default
    return _text(value, default=default)


def _hostname(machine: dict[str, Any]) -> str:
    """Return a short display hostname for a machine payload."""
    hostname = _text(
        machine.get("hostname")
        or machine.get("fqdn")
        or machine.get("name")
        or machine.get("system_id"),
        default="unknown",
    )
    return (hostname or "unknown").split(".", 1)[0]


def _memory_mb(machine: dict[str, Any]) -> int:
    """Extract memory in MiB from a machine payload."""
    raw_value = machine.get("memory_mb") or machine.get("memory_MiB") or 0
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return 0


def _memory_gib_text(memory_mb: int) -> str:
    """Format memory in GiB with one decimal place."""
    if memory_mb <= 0:
        return "-"
    return f"{round(memory_mb / 1024, 1):.1f}"


def _int_value(value: Any, default: int = 0) -> int:
    """Convert a value to int with a default fallback."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _tags(machine: dict[str, Any]) -> list[str]:
    """Extract tag names from a machine payload."""
    raw_tags = machine.get("tags") or machine.get("tag_names") or []
    if isinstance(raw_tags, str):
        return [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
    if not isinstance(raw_tags, list):
        return []

    tags: list[str] = []
    for item in raw_tags:
        tag_name = _name(item, default=None)
        if tag_name is not None:
            tags.append(tag_name)
    return tags


def _machine_summary(machine: dict[str, Any]) -> MachineSummary:
    """Parse a machine payload into a MachineSummary model."""
    return MachineSummary.model_validate(
        {
            "system_id": _text(machine.get("system_id"), default="unknown"),
            "hostname": _hostname(machine),
            "status": _text(
                machine.get("status_name") or machine.get("status"),
                default="unknown",
            ),
            "zone": _name(machine.get("zone"), default="-"),
            "pool": _name(
                machine.get("pool") or machine.get("resource_pool"),
                default="-",
            ),
            "architecture": _text(
                machine.get("architecture"),
                default="-",
            ),
            "cpu_count": _int_value(machine.get("cpu_count")),
            "memory_mb": _memory_mb(machine),
            "owner": _name(machine.get("owner"), default=None),
            "power_state": _text(machine.get("power_state"), default=None),
            "tags": _tags(machine),
        }
    )


def _interface_summaries(payload: Any) -> list[InterfaceSummary]:
    """Parse interface payloads into InterfaceSummary models."""
    interfaces: list[InterfaceSummary] = []
    for item in items_from_payload(payload):
        addresses: list[str] = []
        for address in item.get("ip_addresses") or item.get("links") or []:
            if isinstance(address, str):
                addresses.append(address)
            elif isinstance(address, dict):
                ip_value = address.get("ip") or address.get("address")
                if ip_value:
                    addresses.append(str(ip_value))

        vlan = item.get("vlan")
        vlan_id = item.get("vlan_id")
        if isinstance(vlan, dict) and vlan_id is None:
            vlan_id = vlan.get("id")

        interfaces.append(
            InterfaceSummary.model_validate(
                {
                    "id": str(item.get("id", "")),
                    "name": _text(item.get("name"), default="unknown"),
                    "type": _text(item.get("type"), default="unknown"),
                    "mac_address": _text(
                        item.get("mac_address"),
                        default="-",
                    ),
                    "enabled": bool(item.get("enabled", True)),
                    "vlan_id": _int_value(vlan_id, default=0)
                    if vlan_id is not None
                    else None,
                    "ip_addresses": addresses,
                }
            )
        )
    return interfaces


def _block_devices(machine: dict[str, Any]) -> list[BlockDevice]:
    """Parse block device data from a machine payload."""
    raw_devices = (
        machine.get("block_devices")
        or machine.get("physical_block_devices")
        or []
    )
    if not isinstance(raw_devices, list):
        return []

    devices: list[BlockDevice] = []
    for item in raw_devices:
        if not isinstance(item, dict):
            continue

        size_gb = item.get("size_gb")
        if size_gb is None:
            raw_size = item.get("size") or item.get("size_bytes") or 0
            try:
                size_gb = (
                    round(int(raw_size) / (1024**3), 2) if raw_size else 0.0
                )
            except (TypeError, ValueError):
                size_gb = 0.0

        devices.append(
            BlockDevice.model_validate(
                {
                    "id": str(item.get("id", "")),
                    "name": _text(item.get("name"), default="unknown"),
                    "type": _text(item.get("type"), default="unknown"),
                    "size_gb": float(size_gb),
                    "model": _text(item.get("model"), default=None),
                    "serial": _text(item.get("serial"), default=None),
                }
            )
        )
    return devices


def _machine_detail(
    machine: dict[str, Any], interfaces_payload: Any
) -> MachineDetail:
    """Parse machine and interface payloads into a MachineDetail model."""
    summary = _machine_summary(machine)
    return MachineDetail.model_validate(
        {
            **summary.model_dump(),
            "interfaces": [
                interface.model_dump()
                for interface in _interface_summaries(interfaces_payload)
            ],
            "block_devices": [
                device.model_dump() for device in _block_devices(machine)
            ],
            "bios_boot_method": _text(
                machine.get("bios_boot_method"),
                default=None,
            ),
            "osystem": _text(machine.get("osystem"), default=None),
            "distro_series": _text(
                machine.get("distro_series"),
                default=None,
            ),
        }
    )


async def _resolve_system_id(client: MAASClient, identifier: str) -> str:
    """Resolve a hostname-like identifier to a system_id when possible."""
    if "/" in identifier:
        return identifier

    response = await client.get(
        _MACHINES_PATH,
        query_params={"hostname": identifier},
    )
    items = items_from_payload(response.json())
    if not items:
        return identifier

    system_id = _text(items[0].get("system_id"), default=None)
    return system_id or identifier


async def _get_machine_payload(
    client: MAASClient,
    identifier: str,
) -> dict[str, Any]:
    """Fetch a single machine payload by hostname or system_id."""
    system_id = await _resolve_system_id(client, identifier)
    response = await client.get(
        _MACHINE_PATH,
        path_params={"system_id": system_id},
    )
    payload = _machine_from_payload(response.json())
    if payload is None:
        raise httpx.HTTPStatusError(
            "Machine not found",
            request=response.request,
            response=response,
        )
    return payload


def register(mcp: FastMCP, _pool: MAASClientPool) -> None:
    """Register fleet discovery tools on a FastMCP application."""

    @mcp.tool(
        title="List Machines",
        description="Return a paginated list of machines in the fleet, optionally filtered by hostname, status, resource pool, zone, or tags.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def list_machines(
        status: Annotated[
            str | None,
            Field(
                description=(
                    "Filter by machine status (e.g. 'ready', 'deployed', "
                    "'commissioning')."
                )
            ),
        ] = None,
        hostname: Annotated[
            str | None,
            Field(description="Filter by hostname (substring match)."),
        ] = None,
        zone: Annotated[
            str | None,
            Field(description="Filter by availability zone name."),
        ] = None,
        pool: Annotated[
            str | None,
            Field(description="Filter by resource pool name."),
        ] = None,
        architecture: Annotated[
            str | None,
            Field(
                description="Filter by architecture (e.g. 'amd64/generic')."
            ),
        ] = None,
        tags: Annotated[
            str | None,
            Field(description="Filter by tag (comma-separated or repeated)."),
        ] = None,
        owner: Annotated[
            str | None,
            Field(description="Filter by owning username."),
        ] = None,
        power_state: Annotated[
            str | None,
            Field(
                description="Filter by power state ('on', 'off', 'unknown')."
            ),
        ] = None,
        page: Annotated[
            int,
            Field(description="Page number (1-based)."),
        ] = 1,
        page_size: Annotated[
            int,
            Field(description="Number of results per page."),
        ] = 50,
    ) -> str:
        """List MAAS machines using optional fleet filters."""
        params = {
            "status": status,
            "hostname": hostname,
            "zone": zone,
            "pool": pool,
            "architecture": architecture,
            "tags": tags,
            "owner": owner,
            "power_state": power_state,
            "page": page,
            "page_size": page_size,
        }

        async def operation(client: MAASClient) -> str:
            query_params = {
                key: value
                for key, value in {
                    "status": status,
                    "hostname": hostname,
                    "zone": zone,
                    "pool": pool,
                    "architecture": architecture,
                    "tags": tags,
                    "owner": owner,
                    "power_state": power_state,
                    "page": page,
                    "size": page_size,
                }.items()
                if value is not None
            }
            response = await client.get(
                _MACHINES_PATH,
                query_params=query_params,
            )
            items = items_from_payload(response.json())
            if not items:
                return "No machines found."

            rows: list[list[str]] = []
            for item in items:
                machine = _machine_summary(item)
                rows.append(
                    [
                        machine.hostname,
                        machine.system_id,
                        machine.status,
                        machine.zone,
                        machine.pool,
                        machine.architecture,
                        str(machine.cpu_count),
                        _memory_gib_text(machine.memory_mb),
                        machine.owner or "-",
                        machine.power_state or "-",
                        ", ".join(machine.tags) or "-",
                    ]
                )

            return markdown_table(
                [
                    "hostname",
                    "system_id",
                    "status",
                    "zone",
                    "pool",
                    "architecture",
                    "CPUs",
                    "Memory (GiB)",
                    "owner",
                    "power_state",
                    "tags",
                ],
                rows,
            )

        return await run_tool(
            "list_machines",
            params,
            _pool,
            operation,
        )

    @mcp.tool(
        title="Get Machine",
        description="Return full details for a single machine identified by system_id, hostname, or FQDN.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def get_machine(
        identifier: Annotated[
            str,
            Field(description="System ID, hostname, or FQDN of the machine."),
        ],
    ) -> str:
        """Return detailed machine information by hostname or system_id."""

        async def operation(client: MAASClient) -> str:
            machine_payload = await _get_machine_payload(client, identifier)
            system_id = (
                _text(machine_payload.get("system_id"), default=identifier)
                or identifier
            )
            interfaces_response = await client.get(
                _INTERFACES_PATH,
                path_params={"system_id": system_id},
            )
            machine = _machine_detail(
                machine_payload,
                interfaces_response.json(),
            )

            lines = [
                f"# Machine: {machine.hostname}",
                "",
                "## Hardware",
                f"- System ID: {machine.system_id}",
                f"- Status: {machine.status}",
                f"- Zone: {machine.zone}",
                f"- Pool: {machine.pool}",
                f"- Architecture: {machine.architecture}",
                f"- CPUs: {machine.cpu_count}",
                f"- Memory: {_memory_gib_text(machine.memory_mb)} GiB",
                f"- Power state: {machine.power_state or '-'}",
                f"- Owner: {machine.owner or '-'}",
                f"- Tags: {', '.join(machine.tags) or '-'}",
                "",
                "## Operating system",
                f"- OS: {machine.osystem or '-'}",
                f"- Distro series: {machine.distro_series or '-'}",
                f"- BIOS boot method: {machine.bios_boot_method or '-'}",
                "",
                "## Network interfaces",
            ]

            if machine.interfaces:
                lines.append(
                    markdown_table(
                        [
                            "name",
                            "type",
                            "mac_address",
                            "enabled",
                            "vlan_id",
                            "ip_addresses",
                        ],
                        [
                            [
                                interface.name,
                                interface.type,
                                interface.mac_address,
                                "true" if interface.enabled else "false",
                                _text(interface.vlan_id, default="-") or "-",
                                ", ".join(interface.ip_addresses) or "-",
                            ]
                            for interface in machine.interfaces
                        ],
                    )
                )
            else:
                lines.append("No interfaces found.")

            lines.extend(["", "## Block devices"])
            if machine.block_devices:
                lines.append(
                    markdown_table(
                        ["name", "type", "size_gb", "model", "serial"],
                        [
                            [
                                device.name,
                                device.type,
                                str(device.size_gb),
                                device.model or "-",
                                device.serial or "-",
                            ]
                            for device in machine.block_devices
                        ],
                    )
                )
            else:
                lines.append("No block devices found.")

            return "\n".join(lines)

        return await run_tool(
            "get_machine",
            {"identifier": identifier},
            _pool,
            operation,
            not_found_message=(
                f'Error (error_code: "not_found"): Machine '
                f"'{identifier}' was not found."
            ),
        )

    @mcp.resource(
        "maas://resource-pools",
        name="Resource Pools",
        description="All resource pools available in this MAAS instance.",
        mime_type="text/plain",
    )
    async def list_resource_pools() -> str:
        client = make_client(_pool, get_api_key())
        try:
            items = await fetch_all_pages(client, _RESOURCE_POOLS_PATH)
            if not items:
                return "No resource pools found."

            rows: list[list[str]] = []
            for item in items:
                machine_count = _text(
                    item.get("machine_count")
                    or item.get("machines_count")
                    or item.get("count"),
                    default=None,
                )
                if machine_count is None and isinstance(
                    item.get("machines"), list
                ):
                    machine_count = str(len(item["machines"]))
                rows.append(
                    [
                        _text(item.get("name"), default="unknown")
                        or "unknown",
                        _text(item.get("description"), default="-") or "-",
                        machine_count or "-",
                    ]
                )

            return markdown_table(
                ["name", "description", "machine_count"],
                rows,
            )
        finally:
            if getattr(client, "_close_after_use", False):
                await client.client.aclose()

    @mcp.resource(
        "maas://zones",
        name="Availability Zones",
        description="All availability zones defined in this MAAS instance.",
        mime_type="text/plain",
    )
    async def list_zones() -> str:
        client = make_client(_pool, get_api_key())
        try:
            items = await fetch_all_pages(client, _ZONES_PATH)
            if not items:
                return "No zones found."

            rows = [
                [
                    _text(item.get("name"), default="unknown") or "unknown",
                    _text(item.get("description"), default="-") or "-",
                ]
                for item in items
            ]
            return markdown_table(["name", "description"], rows)
        finally:
            if getattr(client, "_close_after_use", False):
                await client.client.aclose()

    @mcp.tool(
        title="Get Machine Power State",
        description="Return the current power state (on/off/unknown) for a machine identified by system_id, hostname, or FQDN.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def get_machine_power_state(
        identifier: Annotated[
            str,
            Field(description="System ID, hostname, or FQDN of the machine."),
        ],
    ) -> str:
        """Return a machine power state by hostname or system_id."""

        async def operation(client: MAASClient) -> str:
            machine = await _get_machine_payload(client, identifier)
            hostname = _hostname(machine)
            power_state = _text(
                machine.get("power_state"),
                default="unknown",
            )
            return f"{hostname}: power state is {power_state}"

        return await run_tool(
            "get_machine_power_state",
            {"identifier": identifier},
            _pool,
            operation,
            not_found_message=(
                f'Error (error_code: "not_found"): Machine '
                f"'{identifier}' was not found."
            ),
        )
