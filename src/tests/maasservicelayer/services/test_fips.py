#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import patch

import pytest

from maascommon.fips import FIPSStatus
from maascommon.logging.security import FIPS_MODE_DETECTED
from maasservicelayer.context import Context
from maasservicelayer.services.fips import FIPSService


class TestFIPSService:
    @pytest.fixture
    def fips_service(self) -> FIPSService:
        return FIPSService(context=Context())

    @pytest.mark.asyncio
    async def test_get_fips_status_when_enabled(self, fips_service):
        with patch(
            "maasservicelayer.services.fips.is_fips_enabled",
            return_value=True,
        ):
            status = await fips_service.get_fips_status()
        assert isinstance(status, FIPSStatus)
        assert status.fips_enabled is True
        assert status.detection_source == "/proc/sys/crypto/fips_enabled"

    @pytest.mark.asyncio
    async def test_get_fips_status_when_disabled(self, fips_service):
        with patch(
            "maasservicelayer.services.fips.is_fips_enabled",
            return_value=False,
        ):
            status = await fips_service.get_fips_status()
        assert isinstance(status, FIPSStatus)
        assert status.fips_enabled is False
        assert status.detection_source == "/proc/sys/crypto/fips_enabled"

    @pytest.mark.asyncio
    async def test_emit_startup_log_fips_enabled(self, fips_service):
        """FIPS_MODE_DETECTED is logged at INFO level when FIPS is active."""
        import structlog.testing

        with (
            patch(
                "maasservicelayer.services.fips.is_fips_enabled",
                return_value=True,
            ),
            structlog.testing.capture_logs() as log_events,
        ):
            await fips_service.emit_startup_log()

        assert any(
            event.get("event") == FIPS_MODE_DETECTED
            and event.get("fips_mode") is True
            and event.get("detection_source")
            == "/proc/sys/crypto/fips_enabled"
            for event in log_events
        ), f"Expected FIPS_MODE_DETECTED log event not found in: {log_events}"

    @pytest.mark.asyncio
    async def test_emit_startup_log_fips_disabled(self, fips_service):
        """FIPS_MODE_DETECTED is logged with fips_mode=False on non-FIPS host."""
        import structlog.testing

        with (
            patch(
                "maasservicelayer.services.fips.is_fips_enabled",
                return_value=False,
            ),
            structlog.testing.capture_logs() as log_events,
        ):
            await fips_service.emit_startup_log()

        assert any(
            event.get("event") == FIPS_MODE_DETECTED
            and event.get("fips_mode") is False
            and event.get("detection_source")
            == "/proc/sys/crypto/fips_enabled"
            for event in log_events
        ), f"Expected FIPS_MODE_DETECTED log event not found in: {log_events}"
