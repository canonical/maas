# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Shared helpers for MCP tool implementations."""

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from maasmcpserver.client import MAASClient, MAASClientPool
from maasmcpserver.errors import MAASPermissionError, MAASUnreachableError
from maasmcpserver.logging_events import log_tool_outcome, log_tool_received
from maasmcpserver.middleware import get_api_key, get_session_id


def items_from_payload(payload: Any) -> list[dict[str, Any]]:
    """Return a list of dicts from a paginated or plain JSON payload."""
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


async def fetch_all_pages(
    client: MAASClient,
    path: str,
) -> list[dict[str, Any]]:
    """Fetch every page from a MAAS v3 paginated endpoint.

    The MAAS v3 API uses offset pagination: each response contains an
    optional ``next`` URL pointing to the following page.  This helper
    follows those links until ``next`` is absent or null.

    Note: MCP resources do not receive a Context object in v1.27.0, so
    per-page progress reporting via ``ctx.report_progress()`` is not
    possible here.  When FastMCP adds Context injection for resources
    this function should be updated to accept and use a Context arg.
    """
    all_items: list[dict[str, Any]] = []
    next_path: str | None = path
    while next_path is not None:
        response = await client.get(next_path)
        payload = response.json()
        all_items.extend(items_from_payload(payload))
        next_path = payload.get("next") if isinstance(payload, dict) else None
    return all_items


def safe_text(value: Any, default: str = "-") -> str:
    """Convert a value to display text with a fallback for None/empty."""
    if value in (None, "", []):
        return default
    return str(value)


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a Markdown table from headers and rows."""
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        escaped = [cell.replace("|", r"\|") for cell in row]
        lines.append("| " + " | ".join(escaped) + " |")
    return "\n".join(lines)


def make_client(pool: MAASClientPool, api_key: str) -> MAASClient:
    """Return a request-scoped client from the shared pool."""
    return pool.client(api_key)


async def run_tool(
    tool_name: str,
    params: dict[str, Any],
    pool: MAASClientPool,
    operation: Callable[[MAASClient], Awaitable[str]],
    not_found_message: str | None = None,
    get_api_key_func: Callable[[], str] = get_api_key,
    get_session_id_func: Callable[[], str] = get_session_id,
    log_tool_received_func: Callable[[str, str, dict[str, Any]], None] = (
        log_tool_received
    ),
    log_tool_outcome_func: Callable[..., None] = log_tool_outcome,
    make_client_func: Callable[[Any, str], MAASClient] = make_client,
) -> str:
    """Run an MCP tool with standard logging and MAAS error handling.

    Obtains a request-scoped :class:`MAASClient` from *pool* (which reuses
    the underlying HTTP connection pool), runs *operation*, and maps all
    MAAS-specific exceptions to structured error strings so the MCP layer
    always receives a plain string result.

    Args:
        tool_name: Identifier used in log events.
        params: Tool parameters logged at tool-received time (sanitised by
            the logging layer).
        pool: Shared connection pool; used to obtain a per-request client.
        operation: Async callable that performs the actual MAAS API calls.
        not_found_message: Optional message returned when the MAAS API responds
            with HTTP 404.  When *None* a generic http_error is returned.
    """
    session_id = get_session_id_func()
    log_tool_received_func(session_id, tool_name, params)

    client = make_client_func(pool, get_api_key_func())
    try:
        result = await operation(client)
    except MAASUnreachableError as error:
        log_tool_outcome_func(
            session_id,
            tool_name,
            "error",
            "maas_unreachable",
        )
        return (
            'Error (error_code: "maas_unreachable"): MAAS unreachable '
            f"({error.failure_mode}) at {error.url_pattern}"
        )
    except MAASPermissionError as error:
        log_tool_outcome_func(
            session_id,
            tool_name,
            "error",
            "permission_denied",
        )
        return (
            'Error (error_code: "permission_denied"): '
            f"Permission denied (HTTP {error.status_code})."
        )
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404 and not_found_message is not None:
            log_tool_outcome_func(
                session_id,
                tool_name,
                "error",
                "not_found",
            )
            return not_found_message
        log_tool_outcome_func(
            session_id,
            tool_name,
            "error",
            "http_error",
        )
        return (
            'Error (error_code: "http_error"): HTTP '
            f"{error.response.status_code}: {error.response.text[:200]}"
        )
    except ValueError as error:
        log_tool_outcome_func(
            session_id,
            tool_name,
            "error",
            "not_found",
        )
        return f'Error (error_code: "not_found"): {error}'
    except Exception as error:  # pragma: no cover - defensive guard
        log_tool_outcome_func(
            session_id,
            tool_name,
            "error",
            "unexpected_error",
        )
        return (
            'Error (error_code: "unexpected_error"): '
            f"{type(error).__name__}: {error}"
        )
    finally:
        if getattr(client, "_close_after_use", False):
            await client.client.aclose()

    log_tool_outcome_func(session_id, tool_name, "success")
    return result
