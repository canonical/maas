# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MCP tools for MAAS boot source management."""

from collections.abc import Awaitable, Callable
from typing import Annotated, Any

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from maasmcpserver.client import MAASClient, MAASClientPool
from maasmcpserver.logging_events import log_tool_outcome, log_tool_received
from maasmcpserver.middleware import get_api_key, get_session_id
from maasmcpserver.models.boot_sources import BootSource, BootSourceSelection
from maasmcpserver.tools.common import (
    fetch_all_pages,
    items_from_payload,
    safe_text,
)
from maasmcpserver.tools.common import run_tool as _run_tool

_BOOT_SOURCES_PATH = "/MAAS/a/v3/boot_sources"
_BOOT_SOURCE_PATH = "/MAAS/a/v3/boot_sources/{boot_source_id}"
_BOOT_SOURCE_SELECTIONS_PATH = (
    "/MAAS/a/v3/boot_sources/{boot_source_id}/selections"
)
_BOOT_SOURCE_SYNC_PATH = (
    "/MAAS/a/v3/boot_sources/{boot_source_id}/selections/{selection_id}:sync"
)
_AVAILABLE_IMAGES_PATH = "/MAAS/a/v3/available_images"
_SELECTIONS_PATH = "/MAAS/a/v3/selections"
_CUSTOM_IMAGES_PATH = "/MAAS/a/v3/custom_images"


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


def _response_json(response: httpx.Response) -> Any:
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return {}


def _boot_source_selection_from_payload(
    payload: dict[str, Any],
) -> BootSourceSelection:
    return BootSourceSelection.model_validate(
        {
            "id": int(payload["id"]),
            "os": payload.get("os"),
            "release": payload.get("release"),
            "arches": payload.get("arches") or [],
            "subarches": payload.get("subarches") or [],
            "labels": payload.get("labels") or [],
        }
    )


def _boot_source_from_payload(payload: dict[str, Any]) -> BootSource:
    raw_selections = payload.get("selections")
    selections = []
    if isinstance(raw_selections, list):
        selections = [
            _boot_source_selection_from_payload(item)
            for item in raw_selections
            if isinstance(item, dict) and "id" in item
        ]

    return BootSource.model_validate(
        {
            "id": int(payload["id"]),
            "url": str(payload["url"]),
            "keyring_data": payload.get("keyring_data"),
            "selections": selections,
        }
    )


def _list_text(values: list[str]) -> str:
    if not values:
        return "[]"
    return f"[{', '.join(values)}]"


def _keyring_text(value: str | None) -> str:
    return "Present" if value else "None"


def _format_boot_sources(sources: list[BootSource]) -> str:
    if not sources:
        return "No boot sources configured."

    lines = ["## Boot Sources"]
    for index, source in enumerate(sources, start=1):
        lines.extend(
            [
                "",
                f"### Source {index} (ID: {source.id})",
                f"URL: {source.url}",
                f"Keyring: {_keyring_text(source.keyring_data)}",
                "",
                "**Selections:**",
            ]
        )
        if source.selections:
            lines.extend(
                _format_selection(selection) for selection in source.selections
            )
        else:
            lines.append("- None")
    return "\n".join(lines)


def _format_selection(selection: BootSourceSelection) -> str:
    return (
        f"- OS: {safe_text(selection.os)}, "
        f"Release: {safe_text(selection.release)}, "
        f"Arches: {_list_text(selection.arches)}, "
        f"Labels: {_list_text(selection.labels)}"
    )


def _format_image_item(item: dict[str, Any]) -> str:
    os = safe_text(item.get("os"))
    release = safe_text(item.get("release"))
    arch = safe_text(item.get("architecture"))
    title = safe_text(item.get("title"), default="")
    parts = [f"OS: {os}", f"Release: {release}", f"Arch: {arch}"]
    if title:
        parts.append(f"Title: {title}")
    return "- " + ", ".join(parts)


def _format_image_list(heading: str, items: list[dict[str, Any]]) -> str:
    if not items:
        return f"No {heading.lower()} found."
    lines = [f"## {heading}"]
    for item in items:
        source_id = item.get("source_id")
        source_url = item.get("source_url")
        line = _format_image_item(item)
        if source_id is not None:
            line += f", Source ID: {source_id}"
        if source_url:
            line += f", Source URL: {source_url}"
        lines.append(line)
    return "\n".join(lines)


def _format_custom_image_item(item: dict[str, Any]) -> str:
    id_ = item.get("id", "-")
    os = safe_text(item.get("os"))
    release = safe_text(item.get("release"))
    arch = safe_text(item.get("architecture"))
    subarch = safe_text(item.get("sub_architecture"), default="")
    parts = [f"ID: {id_}", f"OS: {os}", f"Release: {release}", f"Arch: {arch}"]
    if subarch:
        parts.append(f"Sub-arch: {subarch}")
    return "- " + ", ".join(parts)


def _format_custom_images(items: list[dict[str, Any]]) -> str:
    if not items:
        return "No custom images found."
    lines = ["## Custom Images"]
    lines.extend(_format_custom_image_item(item) for item in items)
    return "\n".join(lines)


def register(mcp: FastMCP, pool: MAASClientPool) -> None:
    """Register boot source tools on a FastMCP application."""

    @mcp.resource(
        "maas://boot-sources",
        name="Boot Sources",
        description="All configured boot sources and their sync selections.",
        mime_type="text/plain",
    )
    async def list_boot_sources() -> str:
        client = make_client(pool, get_api_key())
        try:
            items = await fetch_all_pages(client, _BOOT_SOURCES_PATH)
            sources = [_boot_source_from_payload(item) for item in items]
            return _format_boot_sources(sources)
        finally:
            if getattr(client, "_close_after_use", False):
                await client.client.aclose()

    @mcp.tool(
        title="Trigger Boot Source Sync",
        description="Initiate an asynchronous image sync for a specific boot source selection. Use this when the user wants to pull or refresh images from a boot source. Do NOT use this to inspect sync status or list images — use list_boot_sources or list_available_images instead. Returns a confirmation message with boot source ID, selection ID, and HTTP status.",
    )
    async def trigger_boot_source_sync(
        boot_source_id: Annotated[
            int,
            Field(
                description="Integer ID of the boot source to sync against. Obtain from list_boot_sources if not provided by the user."
            ),
        ],
        selection_id: Annotated[
            int,
            Field(
                description="Integer ID of the specific image selection within the boot source. Obtain from list_boot_source_selections if not provided by the user."
            ),
        ],
    ) -> str:
        params = {
            "boot_source_id": boot_source_id,
            "selection_id": selection_id,
        }

        async def operation(client: MAASClient) -> str:
            response = await client.post(
                _BOOT_SOURCE_SYNC_PATH,
                path_params={
                    "boot_source_id": boot_source_id,
                    "selection_id": selection_id,
                },
            )
            return (
                "Boot source sync triggered.\n"
                f"Boot Source ID: {boot_source_id}\n"
                f"Selection ID: {selection_id}\n"
                f"Status: {response.status_code}\n\n"
                "Note: Sync is asynchronous. Check completion via "
                "list_boot_sources."
            )

        return await run_tool(
            "trigger_boot_source_sync",
            params,
            pool,
            operation,
        )

    @mcp.tool(
        title="Delete Boot Source",
        description="Permanently delete a boot source and ALL of its image selections from MAAS. Use this only when the user explicitly confirms deletion. Do NOT use this to remove a single selection or to disable syncing — it removes the entire source irreversibly. Returns the deleted source ID and URL on success.",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def delete_boot_source(
        boot_source_id: Annotated[
            int,
            Field(
                description="Integer ID of the boot source to delete. Obtain from list_boot_sources if not provided by the user. Deleting this ID removes all associated selections permanently."
            ),
        ],
    ) -> str:
        params = {"boot_source_id": boot_source_id}

        async def operation(client: MAASClient) -> str:
            try:
                response = await client.get(
                    _BOOT_SOURCE_PATH,
                    path_params={"boot_source_id": boot_source_id},
                )
            except httpx.HTTPStatusError as error:
                if error.response.status_code == 404:
                    return (
                        'Error (error_code: "not_found"): '
                        f"Boot source {boot_source_id} was not found."
                    )
                raise

            boot_source = _boot_source_from_payload(_response_json(response))

            try:
                await client.delete(
                    _BOOT_SOURCE_PATH,
                    path_params={"boot_source_id": boot_source_id},
                )
            except httpx.HTTPStatusError as error:
                if error.response.status_code == 404:
                    return (
                        'Error (error_code: "not_found"): '
                        f"Boot source {boot_source_id} was not found."
                    )
                raise

            return (
                f"Boot source deleted: ID={boot_source_id}, "
                f"URL={boot_source.url}"
            )

        return await run_tool("delete_boot_source", params, pool, operation)

    @mcp.tool(
        title="List Boot Source Selections",
        description="Fetch and list all OS image selections configured under a specific boot source. Use this to inspect what OS/release/arch combinations are selected for syncing. Do NOT use this to trigger a sync or to list already-available images — use trigger_boot_source_sync or list_available_images for those. Returns a paginated markdown list of selections.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def list_boot_source_selections(
        boot_source_id: Annotated[
            int,
            Field(
                description="Integer ID of the boot source whose selections to list. Obtain from list_boot_sources if not provided by the user."
            ),
        ],
        page: Annotated[
            int,
            Field(
                description="Page number to retrieve, 1-based integer. Defaults to 1. Increment to paginate through large result sets."
            ),
        ] = 1,
        page_size: Annotated[
            int,
            Field(
                description="Number of selections to return per page, integer. Defaults to 100. Reduce if responses are too large."
            ),
        ] = 100,
    ) -> str:
        params = {
            "boot_source_id": boot_source_id,
            "page": page,
            "page_size": page_size,
        }

        async def operation(client: MAASClient) -> str:
            response = await client.get(
                _BOOT_SOURCE_SELECTIONS_PATH,
                path_params={"boot_source_id": boot_source_id},
                query_params={"page": page, "size": page_size},
            )
            items = items_from_payload(_response_json(response))
            return _format_image_list(
                f"Selections for Boot Source {boot_source_id}", items
            )

        return await run_tool(
            "list_boot_source_selections", params, pool, operation
        )

    @mcp.resource(
        "maas://available-images",
        name="Available Images",
        description="All OS images available from all configured boot sources.",
        mime_type="text/plain",
    )
    async def list_available_images() -> str:
        client = make_client(pool, get_api_key())
        try:
            items = await fetch_all_pages(client, _AVAILABLE_IMAGES_PATH)
            return _format_image_list("Available Images", items)
        finally:
            if getattr(client, "_close_after_use", False):
                await client.client.aclose()

    @mcp.resource(
        "maas://selections",
        name="Image Selections",
        description="All active image selections across all boot sources.",
        mime_type="text/plain",
    )
    async def list_selections() -> str:
        client = make_client(pool, get_api_key())
        try:
            items = await fetch_all_pages(client, _SELECTIONS_PATH)
            return _format_image_list("Image Selections", items)
        finally:
            if getattr(client, "_close_after_use", False):
                await client.client.aclose()

    @mcp.tool(
        title="List Custom Images",
        description="List all custom (user-uploaded) boot images registered in MAAS. Use this when the user asks about non-standard or manually imported OS images. Do NOT use this for Canonical-synced images — use list_available_images for those. Returns a paginated markdown list with image ID, OS, release, arch, and sub-arch.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def list_custom_images(
        page: Annotated[
            int,
            Field(
                description="Page number to retrieve, 1-based integer. Defaults to 1. Increment to paginate through results."
            ),
        ] = 1,
        page_size: Annotated[
            int,
            Field(
                description="Number of custom images to return per page, integer. Defaults to 100."
            ),
        ] = 100,
    ) -> str:
        params = {"page": page, "page_size": page_size}

        async def operation(client: MAASClient) -> str:
            response = await client.get(
                _CUSTOM_IMAGES_PATH,
                query_params={"page": page, "size": page_size},
            )
            items = items_from_payload(_response_json(response))
            return _format_custom_images(items)

        return await run_tool("list_custom_images", params, pool, operation)
