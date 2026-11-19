# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Example MAAS webhook for Eaton PDUs using the retired driver's outlet MIB."""

import os
import secrets
import shutil
import subprocess
import time

from flask import abort, Flask, request


def create_app() -> Flask:
    app = Flask(__name__)
    settings = {}
    for name in ("PDU_ADDRESS", "SNMP_COMMUNITY", "WEBHOOK_TOKEN"):
        value = os.environ.get(name)
        if not value:
            raise RuntimeError(f"Set the {name} environment variable.")
        settings[name] = value
    commands = {}
    for name in ("snmpget", "snmpset"):
        executable = shutil.which(name)
        if executable is None:
            raise RuntimeError(f"Install the snmp package: {name} is missing.")
        commands[name] = executable

    @app.before_request
    def authorize() -> None:
        supplied = request.headers.get("Authorization", "").encode()
        expected = f"Bearer {settings['WEBHOOK_TOKEN']}".encode()
        if not secrets.compare_digest(supplied, expected):
            abort(401)
        outlet = (request.view_args or {}).get("outlet")
        if outlet is not None and not 1 <= outlet <= 24:
            abort(404)

    def snmp(column: int, outlet: int, write: bool = False) -> str:
        program = "snmpset" if write else "snmpget"
        command = [
            commands[program],
            "-v1",
            "-c",
            settings["SNMP_COMMUNITY"],
            "-Oqve",
            "-t",
            "2",
            "-r",
            "1",
            settings["PDU_ADDRESS"],
            f"1.3.6.1.4.1.534.6.6.7.6.6.1.{column}.0.{outlet}",
        ]
        if write:
            # Eaton's on/off OIDs accept a delay in seconds, not a power state.
            command.extend(["i", "0"])
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
        except subprocess.TimeoutExpired:
            app.logger.error("SNMP request timed out.")
            abort(504, description="PDU timed out; query before retrying.")
        except (subprocess.CalledProcessError, OSError):
            # Command arguments and stderr may contain the SNMP community.
            app.logger.error("SNMP request failed; check PDU access.")
            abort(502, description="Check PDU address, community and access.")
        return result.stdout.strip()

    def query_power(outlet: int) -> str:
        value = snmp(2, outlet)
        if value not in ("0", "1"):
            app.logger.error("PDU returned an unrecognized outlet state.")
            abort(502, description="Unrecognized PDU outlet state.")
        return "running" if value == "1" else "stopped"

    def set_power(outlet: int, on: bool) -> None:
        snmp(4 if on else 3, outlet, write=True)

    @app.get("/outlets/<int:outlet>/status")
    def power_query(outlet: int):
        return {"status": query_power(outlet)}

    @app.post("/outlets/<int:outlet>/on")
    def power_on(outlet: int):
        # Match the retired driver: cycle an already-powered outlet.
        if query_power(outlet) == "running":
            set_power(outlet, False)
        time.sleep(5)
        set_power(outlet, True)
        return {"result": "accepted"}

    @app.post("/outlets/<int:outlet>/off")
    def power_off(outlet: int):
        set_power(outlet, False)
        return {"result": "accepted"}

    return app
