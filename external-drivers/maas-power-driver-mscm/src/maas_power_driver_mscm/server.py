# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""HTTP server for the IBM MSCM power driver, listening on a UNIX domain socket."""

import argparse
import json
import logging
import os
import signal
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from maas_power_driver_mscm.driver import MSCMPowerDriver

logger = logging.getLogger("maas-power-driver-mscm")

METADATA_PATH = Path(__file__).parent / "metadata.json"


class PowerDriverHandler(BaseHTTPRequestHandler):
    """HTTP request handler for power driver operations."""

    driver = None

    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.info(format, *args)

    def send_json(self, status_code, data):
        """Send a JSON response."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json_body(self):
        """Read and parse JSON from the request body."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return None
        raw = self.rfile.read(content_length)
        return json.loads(raw)

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/metadata":
            try:
                metadata = json.loads(METADATA_PATH.read_text())
                self.send_json(200, metadata)
            except Exception as e:
                self.send_json(500, {
                    "status": "error",
                    "error_type": "internal_error",
                    "error_message": str(e),
                })
        else:
            self.send_json(404, {
                "status": "error",
                "error_type": "not_found",
                "error_message": f"Unknown path: {self.path}",
            })

    def do_POST(self):
        """Handle POST requests for power operations."""
        if self.path == "/query":
            self.handle_query()
        elif self.path == "/on":
            self.handle_on()
        elif self.path == "/off":
            self.handle_off()
        elif self.path == "/cycle":
            self.handle_cycle()
        elif self.path == "/reset":
            self.handle_reset()
        elif self.path == "/set-boot-order":
            self.handle_set_boot_order()
        else:
            self.send_json(404, {
                "status": "error",
                "error_type": "not_found",
                "error_message": f"Unknown path: {self.path}",
            })

    def _get_params(self):
        """Extract and validate common POST parameters."""
        try:
            body = self.read_json_body()
            if body is None:
                raise ValueError("Missing request body")
            system_id = body.get("system_id")
            if not system_id:
                raise ValueError("Missing 'system_id' parameter")
            context = body.get("context", {})
            if not context:
                raise ValueError("Missing 'context' parameter")
            return system_id, context
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

    def handle_query(self):
        """Handle POST /query."""
        try:
            system_id, context = self._get_params()
            state = self.driver.query(system_id, context)
            self.send_json(200, {"status": "ok", "state": state})
        except ValueError as e:
            self.send_json(400, {
                "status": "error",
                "error_type": "invalid_parameters",
                "error_message": str(e),
            })
        except Exception as e:
            self.send_json(500, {
                "status": "error",
                "error_type": "internal_error",
                "error_message": str(e),
            })

    def handle_on(self):
        """Handle POST /on."""
        try:
            system_id, context = self._get_params()
            self.driver.on(system_id, context)
            self.send_json(200, {"status": "ok"})
        except ValueError as e:
            self.send_json(400, {
                "status": "error",
                "error_type": "invalid_parameters",
                "error_message": str(e),
            })
        except Exception as e:
            self.send_json(500, {
                "status": "error",
                "error_type": "internal_error",
                "error_message": str(e),
            })

    def handle_off(self):
        """Handle POST /off."""
        try:
            system_id, context = self._get_params()
            self.driver.off(system_id, context)
            self.send_json(200, {"status": "ok"})
        except ValueError as e:
            self.send_json(400, {
                "status": "error",
                "error_type": "invalid_parameters",
                "error_message": str(e),
            })
        except Exception as e:
            self.send_json(500, {
                "status": "error",
                "error_type": "internal_error",
                "error_message": str(e),
            })

    def handle_cycle(self):
        """Handle POST /cycle."""
        try:
            system_id, context = self._get_params()
            self.driver.cycle(system_id, context)
            self.send_json(200, {"status": "ok"})
        except ValueError as e:
            self.send_json(400, {
                "status": "error",
                "error_type": "invalid_parameters",
                "error_message": str(e),
            })
        except Exception as e:
            self.send_json(500, {
                "status": "error",
                "error_type": "internal_error",
                "error_message": str(e),
            })

    def handle_reset(self):
        """Handle POST /reset."""
        try:
            system_id, context = self._get_params()
            self.driver.reset(system_id, context)
            self.send_json(200, {"status": "ok"})
        except ValueError as e:
            self.send_json(400, {
                "status": "error",
                "error_type": "invalid_parameters",
                "error_message": str(e),
            })
        except Exception as e:
            self.send_json(500, {
                "status": "error",
                "error_type": "internal_error",
                "error_message": str(e),
            })

    def handle_set_boot_order(self):
        """Handle POST /set-boot-order."""
        try:
            system_id, context = self._get_params()
            self.driver.set_boot_order(system_id, context)
            self.send_json(200, {"status": "ok"})
        except ValueError as e:
            self.send_json(400, {
                "status": "error",
                "error_type": "invalid_parameters",
                "error_message": str(e),
            })
        except Exception as e:
            self.send_json(500, {
                "status": "error",
                "error_type": "internal_error",
                "error_message": str(e),
            })


def main():
    """Start the IBM MSCM power driver HTTP server."""
    parser = argparse.ArgumentParser(description="IBM MSCM Power Driver Service")
    parser.add_argument(
        "command",
        choices=["start", "status"],
        help="Command to execute",
    )
    parser.add_argument(
        "--socket-path",
        default="/var/snap/maas-power-driver-mscm/common/power-driver/mscm.sock",
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
            sys.exit(0)
        else:
            logger.info("Service is not running")
            sys.exit(3)

    # Remove stale socket file
    if os.path.exists(args.socket_path):
        os.unlink(args.socket_path)

    # Initialize the driver
    PowerDriverHandler.driver = MSCMPowerDriver()

    # Create UNIX domain socket server
    unix_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    unix_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    unix_socket.bind(args.socket_path)
    unix_socket.listen(5)

    class UnixHTTPServer(HTTPServer):
        """HTTPServer that uses a pre-created UNIX socket."""

        allow_reuse_address = True

        def server_bind(self):
            pass

        def server_close(self):
            self.socket.close()

    server = UnixHTTPServer((args.socket_path,), PowerDriverHandler)
    server.socket = unix_socket

    logger.info("IBM MSCM power driver listening on %s", args.socket_path)

    def shutdown(signum, frame):
        logger.info("Shutting down...")
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        server.serve_forever()
    finally:
        if os.path.exists(args.socket_path):
            os.unlink(args.socket_path)
        logger.info("Server stopped")


if __name__ == "__main__":
    main()
