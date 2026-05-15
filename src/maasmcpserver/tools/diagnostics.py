# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MCP diagnostic tools for MAAS machines."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from maasmcpserver.client import MAASClient, MAASClientPool
from maasmcpserver.logging_events import log_tool_outcome, log_tool_received
from maasmcpserver.middleware import get_api_key, get_session_id
from maasmcpserver.models.diagnostics import MachineEvent, ScriptResult
from maasmcpserver.tools.common import items_from_payload, safe_text
from maasmcpserver.tools.common import run_tool as _run_tool

_EVENTS_PATH = "/MAAS/a/v3/events"
_MACHINES_PATH = "/MAAS/a/v3/machines"
_SCRIPT_RESULTS_PATH = "/MAAS/a/v3/machines/{system_id}/script_results"


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


def _parse_created(value: str) -> datetime | None:
    """Parse an ISO 8601 timestamp into a timezone-aware datetime."""
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _markdown_cell(value: str) -> str:
    """Escape Markdown table separators in cell values."""
    return value.replace("|", r"\|")


def _truncate_output(output: str | None) -> str:
    """Trim script output to a compact preview."""
    if not output:
        return "-"

    preview = " ".join(output.split())
    if len(preview) <= 500:
        return preview
    return f"{preview[:500]}..."


async def _resolve_system_id(client: MAASClient, identifier: str) -> str:
    """Resolve hostname or system_id to system_id."""
    if "/" not in identifier:
        response = await client.get(
            _MACHINES_PATH,
            query_params={"hostname": identifier},
        )
        data = response.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        if not items:
            raise ValueError(f"Machine not found: {identifier!r}")
        return items[0]["system_id"]
    return identifier


async def _resolve_hostname(
    client: MAASClient,
    identifier: str,
    system_id: str,
) -> str:
    """Resolve a display hostname for output headings."""
    if "/" not in identifier:
        return identifier

    response = await client.get(
        _MACHINES_PATH,
        query_params={"system_id": system_id},
    )
    items = items_from_payload(response.json())
    if not items:
        return system_id

    hostname = safe_text(
        items[0].get("hostname")
        or items[0].get("fqdn")
        or items[0].get("name"),
        default=system_id,
    )
    return hostname.split(".", 1)[0]


def register(mcp: FastMCP, pool: MAASClientPool) -> None:
    """Register diagnostic tools on a FastMCP application."""

    @mcp.tool(
        title="Get Machine Events",
        description="Return recent audit and lifecycle events for a machine, optionally filtered by event type and limited by count.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def get_machine_events(
        identifier: Annotated[
            str,
            Field(description="System ID, hostname, or FQDN of the machine."),
        ],
        since_hours: Annotated[
            int | None,
            Field(description="Only return events from the last N hours."),
        ] = None,
    ) -> str:
        """Return recent machine events for a hostname or system_id."""
        params = {
            "identifier": identifier,
            "since_hours": since_hours,
        }

        async def operation(client: MAASClient) -> str:
            system_id = await _resolve_system_id(client, identifier)
            hostname = await _resolve_hostname(client, identifier, system_id)
            response = await client.get(
                _EVENTS_PATH,
                query_params={"system_id": system_id},
            )
            payload_items = items_from_payload(response.json())
            events = [
                MachineEvent.model_validate(item) for item in payload_items
            ]
            levels_by_id = {
                event_item.id: safe_text(payload_item.get("level"))
                for event_item, payload_item in zip(
                    events, payload_items, strict=False
                )
            }

            if since_hours is not None:
                threshold = datetime.now(timezone.utc) - timedelta(
                    hours=since_hours
                )
                events = [
                    event
                    for event in events
                    if (created := _parse_created(event.created)) is not None
                    and created >= threshold
                ]

            events.sort(
                key=lambda event: _parse_created(event.created)
                or datetime.min.replace(tzinfo=timezone.utc)
            )

            lines = [
                f"## Machine Events: {hostname} ({system_id})",
                "",
            ]
            if not events:
                lines.append("No events found.")
                return "\n".join(lines)

            lines.extend(
                [
                    "| Timestamp | Type | Level | Description |",
                    "|-----------|------|-------|-------------|",
                ]
            )
            lines.extend(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(event.created),
                        _markdown_cell(event.type),
                        _markdown_cell(levels_by_id.get(event.id, "-")),
                        _markdown_cell(event.description),
                    ]
                )
                + " |"
                for event in events
            )
            return "\n".join(lines)

        return await run_tool(
            "get_machine_events",
            params,
            pool,
            operation,
        )

    @mcp.tool(
        title="Get Script Results",
        description="Return commissioning or testing script results for a machine, optionally filtered by script type (commissioning/testing) and script name.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def get_script_results(
        identifier: Annotated[
            str,
            Field(description="System ID, hostname, or FQDN of the machine."),
        ],
        script_type: Annotated[
            str | None,
            Field(
                description=(
                    "Filter by script type: 'commissioning' or 'testing'."
                )
            ),
        ] = None,
    ) -> str:
        """Return script results for a hostname or system_id."""
        params = {
            "identifier": identifier,
            "script_type": script_type,
        }

        async def operation(client: MAASClient) -> str:
            system_id = await _resolve_system_id(client, identifier)
            hostname = await _resolve_hostname(client, identifier, system_id)
            query_params = (
                {"script_type": script_type}
                if script_type is not None
                else None
            )
            response = await client.get(
                _SCRIPT_RESULTS_PATH,
                path_params={"system_id": system_id},
                query_params=query_params,
            )
            results = [
                ScriptResult.model_validate(item)
                for item in items_from_payload(response.json())
            ]

            lines = [
                f"## Script Results: {hostname} ({system_id})",
                f"Script Type: {script_type or 'all'}",
                "",
            ]
            if not results:
                lines.append("No script results found.")
                return "\n".join(lines)

            for index, result in enumerate(results):
                lines.extend(
                    [
                        f"### {result.name}",
                        f"- Status: {result.status}",
                        f"- Exit Code: {safe_text(result.exit_status)}",
                        (
                            "- Runtime: "
                            f"{safe_text(result.started)} → {safe_text(result.ended)}"
                        ),
                        f"- Output: {_truncate_output(result.output)}",
                    ]
                )
                if index < len(results) - 1:
                    lines.append("")
            return "\n".join(lines)

        return await run_tool(
            "get_script_results",
            params,
            pool,
            operation,
        )

    @mcp.tool(
        title="List Events",
        description="Return paginated MAAS audit and lifecycle events, optionally filtered by one or more machine system IDs.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def list_events(
        system_ids: Annotated[
            list[str] | None,
            Field(description="Filter events to these machine system IDs."),
        ] = None,
        page: Annotated[
            int,
            Field(description="Page number (1-based)."),
        ] = 1,
        page_size: Annotated[
            int,
            Field(description="Number of results per page."),
        ] = 100,
    ) -> str:
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if system_ids:
            params["system_ids"] = system_ids

        async def operation(client: MAASClient) -> str:
            query_params: dict[str, Any] = {"page": page, "size": page_size}
            if system_ids:
                query_params["system_id"] = system_ids

            response = await client.get(
                _EVENTS_PATH, query_params=query_params
            )
            payload = response.json()
            items = items_from_payload(payload)
            total = (
                payload.get("total", len(items))
                if isinstance(payload, dict)
                else len(items)
            )

            heading = "## MAAS Events"
            if system_ids:
                heading += f" (system_ids: {', '.join(system_ids)})"

            if not items:
                return f"{heading}\n\nNo events found."

            lines = [
                heading,
                f"Total: {total}",
                "",
                "| Timestamp | Level | Node | Owner | Action | Description |",
                "|-----------|-------|------|-------|--------|-------------|",
            ]
            for item in items:
                event_type = item.get("type") or {}
                if isinstance(event_type, dict):
                    level = safe_text(event_type.get("level"))
                    action = safe_text(
                        item.get("action") or event_type.get("name")
                    )
                else:
                    level = "-"
                    action = safe_text(item.get("action"))
                lines.append(
                    "| "
                    + " | ".join(
                        _markdown_cell(c)
                        for c in [
                            safe_text(item.get("created")),
                            level,
                            safe_text(
                                item.get("node_hostname")
                                or item.get("node_system_id")
                            ),
                            safe_text(item.get("owner")),
                            action,
                            safe_text(item.get("description")),
                        ]
                    )
                    + " |"
                )
            return "\n".join(lines)

        return await run_tool("list_events", params, pool, operation)
