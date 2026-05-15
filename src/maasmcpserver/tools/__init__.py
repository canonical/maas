# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MCP tool implementations for the MAAS MCP server."""

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

DEFERRED_TOOLS = frozenset({"deploy"})


def deferred_tool(
    capability: str,
) -> Callable[
    [Callable[..., Awaitable[Any]]], Callable[..., Awaitable[dict[str, str]]]
]:
    """Mark a tool capability as intentionally deferred."""

    def decorator(
        func: Callable[..., Awaitable[Any]],
    ) -> Callable[..., Awaitable[dict[str, str]]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> dict[str, str]:
            return {
                "type": "not-implemented",
                "error": (
                    "TC-2 safety policy: "
                    f"'{capability}' tools are not implemented."
                ),
            }

        return wrapper

    return decorator
