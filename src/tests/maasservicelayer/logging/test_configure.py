from datetime import datetime
import io
import json
import logging

import pytest
import structlog

from maasservicelayer.logging.configure import (
    configure_logging,
    CustomJsonFormatter,
)

logger = structlog.getLogger()


@pytest.fixture
def logging_mock():
    configure_logging()
    buffer = io.StringIO()
    buf_handler = logging.StreamHandler(stream=buffer)
    buf_handler.setFormatter(CustomJsonFormatter())
    logging.getLogger().addHandler(buf_handler)
    yield buffer
    structlog.reset_defaults()
    logging.getLogger().removeHandler(buf_handler)


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
