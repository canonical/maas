# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for the IBM MSCM power driver HTTP server."""

import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time

import pytest


def _start_server(socket_path: str):
    """Start the server in a subprocess and return the process."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(
        __import__("pathlib").Path(__file__).resolve().parent.parent / "src"
    )
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "maas_power_driver_mscm.server",
            "start",
            "--socket-path",
            socket_path,
        ],
        env=env,
    )
    # Wait for socket to appear
    for _ in range(50):
        if os.path.exists(socket_path):
            break
        time.sleep(0.1)
    return proc


def _make_request(socket_path: str, method: str, path: str, body=None):
    """Make an HTTP request to the UNIX socket server."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(socket_path)
    try:
        if body:
            body_bytes = json.dumps(body).encode("utf-8")
            request = (
                f"{method} {path} HTTP/1.1\r\n"
                f"Host: localhost\r\n"
                f"Content-Length: {len(body_bytes)}\r\n"
                f"Content-Type: application/json\r\n"
                f"\r\n"
            )
            sock.sendall(request.encode("utf-8"))
            sock.sendall(body_bytes)
        else:
            request = (
                f"{method} {path} HTTP/1.1\r\n"
                f"Host: localhost\r\n"
                f"\r\n"
            )
            sock.sendall(request.encode("utf-8"))

        response = b""
        sock.settimeout(2.0)
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if b"\r\n\r\n" in response:
                header_end = response.index(b"\r\n\r\n")
                headers = response[:header_end].decode("utf-8").lower()
                cl = 0
                for line in headers.split("\r\n"):
                    if line.startswith("content-length:"):
                        cl = int(line.split(":")[1].strip())
                body_start = header_end + 4
                if len(response) - body_start >= cl:
                    break

        header_end = response.index(b"\r\n\r\n")
        status_line = response[:header_end].split(b"\r\n")[0].decode("utf-8")
        body_part = response[header_end + 4:]
        return status_line, json.loads(body_part)
    finally:
        sock.close()


@pytest.fixture(scope="module")
def server():
    """Start the server for the test module."""
    with tempfile.NamedTemporaryFile(suffix=".sock", delete=False) as f:
        socket_path = f.name
    try:
        os.unlink(socket_path)
    except FileNotFoundError:
        pass

    proc = _start_server(socket_path)
    try:
        yield socket_path
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)
        try:
            os.unlink(socket_path)
        except FileNotFoundError:
            pass


class TestMetadataEndpoint:
    """Tests for GET /metadata."""

    def test_metadata_returns_200(self, server):
        """GET /metadata should return 200."""
        status, body = _make_request(server, "GET", "/metadata")
        assert "200" in status
        assert body["name"] == "mscm"

    def test_metadata_has_actions(self, server):
        """GET /metadata should include actions."""
        status, body = _make_request(server, "GET", "/metadata")
        assert "actions" in body
        assert "query" in body["actions"]


class TestQueryEndpoint:
    """Tests for POST /query."""

    def test_query_missing_body(self, server):
        """POST /query without body should return 400."""
        status, body = _make_request(server, "POST", "/query")
        assert "400" in status
        assert body["status"] == "error"

    def test_query_missing_system_id(self, server):
        """POST /query without system_id should return 400."""
        status, body = _make_request(
            server, "POST", "/query", {"context": {"power_address": "10.0.0.1"}}
        )
        assert "400" in status
        assert body["error_type"] == "invalid_parameters"

    def test_query_missing_context(self, server):
        """POST /query without context should return 400."""
        status, body = _make_request(server, "POST", "/query", {"system_id": "abc"})
        assert "400" in status


class TestPowerEndpoints:
    """Tests for POST /on, /off, /cycle, /reset."""

    @pytest.mark.parametrize("path", ["/on", "/off", "/cycle", "/reset"])
    def test_power_endpoint_missing_body(self, server, path):
        """POST to power endpoints without body should return 400."""
        status, body = _make_request(server, "POST", path)
        assert "400" in status
        assert body["status"] == "error"


class TestUnknownPath:
    """Tests for unknown paths."""

    def test_unknown_get_path(self, server):
        """GET to unknown path should return 404."""
        status, body = _make_request(server, "GET", "/unknown")
        assert "404" in status

    def test_unknown_post_path(self, server):
        """POST to unknown path should return 404."""
        status, body = _make_request(server, "POST", "/unknown")
        assert "404" in status
