# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""HTTP server for the Redfish power driver using aiohttp."""

import argparse
import asyncio
import json
import logging
import os
import signal
from pathlib import Path

from aiohttp import web

from maas_power_driver_redfish.driver import RedfishPowerDriver

logger = logging.getLogger("maas-power-driver-redfish")

METADATA_PATH = Path(__file__).parent / "metadata.json"


class RedfishDriverServer:
    """Aiohttp-based server for the Redfish power driver."""

    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self.driver = RedfishPowerDriver()
        self.app = web.Application()
        self.runner = None
        self.site = None
        self._setup_routes()

    def _setup_routes(self):
        self.app.router.add_get("/metadata", self.handle_metadata)
        self.app.router.add_post("/query", self.handle_query)
        self.app.router.add_post("/on", self.handle_on)
        self.app.router.add_post("/off", self.handle_off)
        self.app.router.add_post("/cycle", self.handle_cycle)
        self.app.router.add_post("/reset", self.handle_reset)
        self.app.router.add_post("/set-boot-order", self.handle_set_boot_order)

    async def handle_metadata(self, request):
        try:
            metadata = json.loads(METADATA_PATH.read_text())
            return web.json_response(metadata)
        except Exception as e:
            return web.json_response(
                {
                    "status": "error",
                    "error_type": "internal_error",
                    "error_message": str(e),
                },
                status=500,
            )

    async def _get_params(self, request):
        try:
            body = await request.json()
        except json.JSONDecodeError:
            raise web.HTTPBadRequest(
                text=json.dumps({
                    "status": "error",
                    "error_type": "invalid_parameters",
                    "error_message": "Invalid JSON",
                })
            )

        system_id = body.get("system_id")
        if not system_id:
            raise web.HTTPBadRequest(
                text=json.dumps({
                    "status": "error",
                    "error_type": "invalid_parameters",
                    "error_message": "Missing 'system_id' parameter",
                })
            )

        context = body.get("context", {})
        if not context:
            raise web.HTTPBadRequest(
                text=json.dumps({
                    "status": "error",
                    "error_type": "invalid_parameters",
                    "error_message": "Missing 'context' parameter",
                })
            )

        order = body.get("order", [])
        return system_id, context, order

    async def handle_query(self, request):
        try:
            system_id, context, _ = await self._get_params(request)
            state = self.driver.query(system_id, context)
            return web.json_response({"status": "ok", "state": state})
        except web.HTTPBadRequest:
            raise
        except Exception as e:
            return web.json_response(
                {
                    "status": "error",
                    "error_type": "internal_error",
                    "error_message": str(e),
                },
                status=500,
            )

    async def handle_on(self, request):
        try:
            system_id, context, _ = await self._get_params(request)
            self.driver.on(system_id, context)
            return web.json_response({"status": "ok"})
        except web.HTTPBadRequest:
            raise
        except Exception as e:
            return web.json_response(
                {
                    "status": "error",
                    "error_type": "internal_error",
                    "error_message": str(e),
                },
                status=500,
            )

    async def handle_off(self, request):
        try:
            system_id, context, _ = await self._get_params(request)
            self.driver.off(system_id, context)
            return web.json_response({"status": "ok"})
        except web.HTTPBadRequest:
            raise
        except Exception as e:
            return web.json_response(
                {
                    "status": "error",
                    "error_type": "internal_error",
                    "error_message": str(e),
                },
                status=500,
            )

    async def handle_cycle(self, request):
        try:
            system_id, context, _ = await self._get_params(request)
            self.driver.cycle(system_id, context)
            return web.json_response({"status": "ok"})
        except web.HTTPBadRequest:
            raise
        except Exception as e:
            return web.json_response(
                {
                    "status": "error",
                    "error_type": "internal_error",
                    "error_message": str(e),
                },
                status=500,
            )

    async def handle_reset(self, request):
        try:
            system_id, context, _ = await self._get_params(request)
            self.driver.reset(system_id, context)
            return web.json_response({"status": "ok"})
        except web.HTTPBadRequest:
            raise
        except Exception as e:
            return web.json_response(
                {
                    "status": "error",
                    "error_type": "internal_error",
                    "error_message": str(e),
                },
                status=500,
            )

    async def handle_set_boot_order(self, request):
        try:
            system_id, context, order = await self._get_params(request)
            self.driver.set_boot_order(system_id, context, order)
            return web.json_response({"status": "ok"})
        except NotImplementedError as e:
            return web.json_response(
                {
                    "status": "error",
                    "error_type": "not_implemented",
                    "error_message": str(e),
                },
                status=501,
            )
        except web.HTTPBadRequest:
            raise
        except Exception as e:
            return web.json_response(
                {
                    "status": "error",
                    "error_type": "internal_error",
                    "error_message": str(e),
                },
                status=500,
            )

    async def start(self):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        # Remove stale socket
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        self.site = web.UnixSite(self.runner, self.socket_path)
        await self.site.start()

        logger.info("Redfish power driver listening on %s", self.socket_path)

    async def stop(self):
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()

        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        logger.info("Server stopped")


def main():
    parser = argparse.ArgumentParser(description="Redfish Power Driver Service")
    parser.add_argument(
        "command",
        choices=["start", "status"],
        help="Command to execute",
    )
    snap_common = os.environ["SNAP_COMMON"]
    default_socket = os.path.join(snap_common, "power-drivers", "redfish.sock")

    parser.add_argument(
        "--socket-path",
        default=default_socket,
        help="Path to the UNIX domain socket",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.command == "status":
        if os.path.exists(args.socket_path):
            logger.info("Service is running on %s", args.socket_path)
            return 0
        else:
            logger.info("Service is not running")
            return 3

    server = RedfishDriverServer(args.socket_path)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def shutdown():
        logger.info("Shutting down...")
        loop.create_task(server.stop())
        loop.stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown)

    try:
        loop.run_until_complete(server.start())
        loop.run_forever()
    finally:
        loop.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
