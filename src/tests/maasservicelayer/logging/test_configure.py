from datetime import datetime
import io
import json
import logging
import sys

import pytest
import structlog

from maasservicelayer.logging.configure import configure_logging

logger = structlog.getLogger()


@pytest.fixture
def logging_mock():
    configure_logging()

    buffer = io.StringIO()
    logger = logging.getLogger()

    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            if handler.stream is sys.stdout:
                handler.stream = buffer

    yield buffer

    structlog.reset_defaults()


class TestStructlogConfiguration:
    @pytest.mark.asyncio
    async def test_structlog_output_formatting(self, logging_mock):
        logger.info("Event message")

        log = logging_mock.getvalue().strip()
        log_object = json.loads(log)

        assert isinstance(log_object, dict), "Log object not JSON compatible"

        assert "timestamp" in log_object, f"Expected 'timestamp' in {log}"

        timestamp_str = log_object["timestamp"]
        try:
            datetime.fromisoformat(timestamp_str)
        except ValueError:
            raise AssertionError(f"Invalid ISO 8601 timestamp {timestamp_str}")  # noqa: B904
