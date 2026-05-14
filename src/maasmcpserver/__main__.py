# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MCP server entry point."""

import os
import sys

from pydantic import ValidationError
import uvicorn

from maasmcpserver.config import MaasServerConfig
from maasmcpserver.logging_events import configure_logging
from maasmcpserver.server import get_app


def _validate_socket_path(socket_path: str) -> None:
    socket_dir = os.path.dirname(socket_path)
    if not os.path.exists(socket_dir):
        print(
            f"ERROR: Socket directory does not exist: {socket_dir}",
            file=sys.stderr,
        )
        sys.exit(1)
    if not os.access(socket_dir, os.W_OK):
        print(
            f"ERROR: Socket directory is not writable: {socket_dir}",
            file=sys.stderr,
        )
        sys.exit(1)


def main():
    """Main entry point for the MAAS MCP server."""
    try:
        config = MaasServerConfig()
    except ValidationError as e:
        print("Configuration error:", file=sys.stderr)
        for error in e.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            print(f"  {field}: {error['msg']}", file=sys.stderr)
        sys.exit(1)

    configure_logging(config.log_level)
    _validate_socket_path(config.mcp_socket_path)

    app = get_app(config)

    # Bind to Unix domain socket (NOT host/port)
    uvicorn.run(
        app,
        uds=config.mcp_socket_path,
        log_config=None,
    )


if __name__ == "__main__":
    main()
