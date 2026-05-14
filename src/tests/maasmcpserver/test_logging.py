# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
import hashlib
import io
import json
import logging
from unittest.mock import patch

import structlog

from maasmcpserver import logging_events


def assert_iso8601(timestamp):
    datetime.fromisoformat(timestamp)


def capture_log(func, *args, **kwargs):
    """Call a logging function and return the raw output and parsed lines."""
    buffer = io.StringIO()

    try:
        with patch("sys.stdout", buffer):
            logging_events.configure_logging("INFO")
            func(*args, **kwargs)
    finally:
        logging.getLogger().handlers.clear()
        structlog.reset_defaults()

    output = buffer.getvalue()
    lines = [line for line in output.splitlines() if line.strip()]
    return output, [json.loads(line) for line in lines]


def test_configure_logging_sets_root_logger_level():
    try:
        with patch("sys.stdout", io.StringIO()):
            logging_events.configure_logging("DEBUG")
            root_logger = logging.getLogger()
            assert root_logger.level == logging.DEBUG
            assert len(root_logger.handlers) == 1
            assert isinstance(root_logger.handlers[0], logging.StreamHandler)
    finally:
        logging.getLogger().handlers.clear()
        structlog.reset_defaults()


def test_log_session_opened_hashes_token_and_writes_one_json_line():
    api_key = "secret-token"

    output, lines = capture_log(
        logging_events.log_session_opened,
        "session-1",
        api_key,
    )

    assert output.endswith("\n")
    assert len(lines) == 1
    assert "secret-token" not in output
    assert lines[0]["event"] == "session.opened"
    assert lines[0]["session_id"] == "session-1"
    assert (
        lines[0]["user_token_hash"]
        == hashlib.sha256(api_key.encode()).hexdigest()
    )
    assert_iso8601(lines[0]["timestamp"])


def test_log_tool_received_writes_one_json_line_and_redacts_tokens():
    output, lines = capture_log(
        logging_events.log_tool_received,
        "session-1",
        "allocate",
        {
            "api_key": "secret-token",
            "headers": {"Authorization": "Bearer secret-token"},
        },
    )

    assert output.endswith("\n")
    assert len(lines) == 1
    assert "secret-token" not in output
    assert lines[0]["event"] == "tool.received"
    assert lines[0]["params"] == {
        "api_key": "[REDACTED]",
        "headers": {"Authorization": "[REDACTED]"},
    }
    assert_iso8601(lines[0]["timestamp"])


def test_log_maas_request_writes_one_json_line():
    output, lines = capture_log(
        logging_events.log_maas_request,
        "session-1",
        "GET",
        "/machines/{id}",
    )

    assert output.endswith("\n")
    assert len(lines) == 1
    assert lines[0]["event"] == "maas.request"
    assert lines[0]["method"] == "GET"
    assert lines[0]["url_pattern"] == "/machines/{id}"
    assert_iso8601(lines[0]["timestamp"])


def test_log_maas_response_timeout_uses_zero_status_and_error():
    output, lines = capture_log(
        logging_events.log_maas_response,
        "session-1",
        503,
        12,
        error="maas_unreachable",
    )

    assert output.endswith("\n")
    assert len(lines) == 1
    assert lines[0]["event"] == "maas.response"
    assert lines[0]["session_id"] == "session-1"
    assert lines[0]["http_status"] == 0
    assert lines[0]["duration_ms"] == 12
    assert lines[0]["error"] == "maas_unreachable"
    assert_iso8601(lines[0]["timestamp"])


def test_log_tool_outcome_success_omits_error_code():
    output, lines = capture_log(
        logging_events.log_tool_outcome,
        "session-1",
        "allocate",
        "success",
    )

    assert output.endswith("\n")
    assert len(lines) == 1
    assert lines[0]["event"] == "tool.outcome"
    assert lines[0]["status"] == "success"
    assert "error_code" not in lines[0]
    assert_iso8601(lines[0]["timestamp"])


def test_log_tool_outcome_error_includes_error_code():
    output, lines = capture_log(
        logging_events.log_tool_outcome,
        "session-1",
        "allocate",
        "error",
        error_code="permission_denied",
    )

    assert output.endswith("\n")
    assert len(lines) == 1
    assert lines[0]["error_code"] == "permission_denied"
    assert_iso8601(lines[0]["timestamp"])


def test_log_session_closed_writes_one_json_line():
    output, lines = capture_log(
        logging_events.log_session_closed,
        "session-1",
    )

    assert output.endswith("\n")
    assert len(lines) == 1
    assert lines[0]["event"] == "session.closed"
    assert lines[0]["session_id"] == "session-1"
    assert_iso8601(lines[0]["timestamp"])
