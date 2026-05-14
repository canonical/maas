# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone
import hashlib
import json
import logging
import sys
from typing import Any

from pythonjsonlogger import jsonlogger
import structlog
from structlog.contextvars import merge_contextvars

_LOGGER = structlog.get_logger("maasmcpserver.logging_events")
_REDACTED = "[REDACTED]"
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "token",
)


class NDJSONFormatter(jsonlogger.JsonFormatter):
    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)

        event = log_record.pop("message", None)
        if event is not None:
            log_record.setdefault("event", event)

        log_record.setdefault("timestamp", _timestamp())
        log_record.setdefault("level", record.levelname)
        log_record.setdefault("logger", record.name)


def configure_logging(log_level: str) -> None:
    level = logging.getLevelNamesMapping().get(log_level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            merge_contextvars,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.render_to_log_kwargs,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(NDJSONFormatter(json_serializer=json.dumps))
    handler.setLevel(level)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)


def log_session_opened(session_id: str, api_key: str) -> None:
    _LOGGER.info(
        "session.opened",
        session_id=session_id,
        user_token_hash=hashlib.sha256(api_key.encode()).hexdigest(),
        timestamp=_timestamp(),
    )


def log_tool_received(
    session_id: str, tool_name: str, params: dict[str, Any]
) -> None:
    _LOGGER.info(
        "tool.received",
        session_id=session_id,
        tool_name=tool_name,
        params=_sanitize_params(params),
        timestamp=_timestamp(),
    )


def log_maas_request(session_id: str, method: str, url_pattern: str) -> None:
    _LOGGER.info(
        "maas.request",
        session_id=session_id,
        method=method,
        url_pattern=url_pattern,
        timestamp=_timestamp(),
    )


def log_maas_response(
    session_id: str,
    http_status: int,
    duration_ms: int,
    error: str | None = None,
) -> None:
    log_data: dict[str, Any] = {
        "session_id": session_id,
        "http_status": http_status,
        "duration_ms": duration_ms,
        "timestamp": _timestamp(),
    }

    if error == "maas_unreachable":
        log_data["http_status"] = 0
        log_data["error"] = error
    elif error is not None:
        log_data["error"] = error

    _LOGGER.info("maas.response", **log_data)


def log_tool_outcome(
    session_id: str,
    tool_name: str,
    status: str,
    error_code: str | None = None,
) -> None:
    log_data: dict[str, Any] = {
        "session_id": session_id,
        "tool_name": tool_name,
        "status": status,
        "timestamp": _timestamp(),
    }
    if status == "error" and error_code is not None:
        log_data["error_code"] = error_code

    _LOGGER.info("tool.outcome", **log_data)


def log_session_closed(session_id: str) -> None:
    _LOGGER.info(
        "session.closed",
        session_id=session_id,
        timestamp=_timestamp(),
    )


def _sanitize_params(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _REDACTED
            if _is_sensitive_key(key)
            else _sanitize_params(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_params(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_params(item) for item in value)
    if isinstance(value, str) and value.startswith("Bearer "):
        return _REDACTED
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered_key = key.lower()
    return any(part in lowered_key for part in _SENSITIVE_KEY_PARTS)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
