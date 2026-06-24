# Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.exceptions.catalog import FIPSViolationException
from maasservicelayer.services.machines import MachinesService


@pytest.mark.asyncio
class TestMachinesServiceFIPSValidation:
    @pytest.fixture(autouse=True)
    def enable_fips(self, monkeypatch):
        monkeypatch.setattr(
            "maasservicelayer.services.machines.is_fips_enabled",
            lambda: True,
        )

    async def test_fips_rejects_unsupported_driver(self) -> None:
        with pytest.raises(FIPSViolationException):
            MachinesService.validate_power_parameters_fips("apc", {})

    async def test_fips_rejects_ipmi_cipher_3(self) -> None:
        with pytest.raises(FIPSViolationException):
            MachinesService.validate_power_parameters_fips(
                "ipmi", {"cipher_suite_id": "3"}
            )

    async def test_fips_rejects_ipmi_cipher_8(self) -> None:
        with pytest.raises(FIPSViolationException):
            MachinesService.validate_power_parameters_fips(
                "ipmi", {"cipher_suite_id": "8"}
            )

    async def test_fips_rejects_ipmi_cipher_12(self) -> None:
        with pytest.raises(FIPSViolationException):
            MachinesService.validate_power_parameters_fips(
                "ipmi", {"cipher_suite_id": "12"}
            )

    async def test_fips_default_cipher_is_accepted(self) -> None:
        # An empty cipher_suite_id means "use driver default". The IPMI
        # driver defaults to "17" in FIPS mode, which is on the
        # allow-list — so this must not raise.
        MachinesService.validate_power_parameters_fips(
            "ipmi", {"cipher_suite_id": ""}
        )

    async def test_fips_rejects_ipmi_unknown_cipher(self) -> None:
        with pytest.raises(FIPSViolationException):
            MachinesService.validate_power_parameters_fips(
                "ipmi", {"cipher_suite_id": "0"}
            )

    async def test_fips_rejects_webhook_verify_ssl_false(self) -> None:
        with pytest.raises(FIPSViolationException):
            MachinesService.validate_power_parameters_fips(
                "webhook", {"verify_ssl": False}
            )

    async def test_fips_rejects_proxmox_verify_ssl_false(self) -> None:
        with pytest.raises(FIPSViolationException):
            MachinesService.validate_power_parameters_fips(
                "proxmox", {"verify_ssl": False}
            )

    async def test_fips_allows_compliant_ipmi(self) -> None:
        MachinesService.validate_power_parameters_fips(
            "ipmi", {"cipher_suite_id": "17"}
        )

    async def test_fips_allows_ipmi_without_cipher_param(self) -> None:
        # No cipher_suite_id key at all — driver will default to "17"
        # in FIPS mode, which is allowed.
        MachinesService.validate_power_parameters_fips("ipmi", {})

    async def test_fips_allows_compliant_webhook(self) -> None:
        MachinesService.validate_power_parameters_fips(
            "webhook", {"verify_ssl": True}
        )


@pytest.mark.asyncio
class TestMachinesServiceNonFIPSValidation:
    async def test_non_fips_allows_unsupported_driver(self) -> None:
        MachinesService.validate_power_parameters_fips("apc", {})

    async def test_non_fips_allows_weak_ipmi_cipher(self) -> None:
        MachinesService.validate_power_parameters_fips(
            "ipmi", {"cipher_suite_id": "3"}
        )

    async def test_non_fips_allows_disabled_ssl_verification(self) -> None:
        MachinesService.validate_power_parameters_fips(
            "webhook", {"verify_ssl": False}
        )


@pytest.mark.asyncio
class TestMachinesServiceSetBmcFIPS:
    """Verify that MachinesService.set_bmc gates on FIPS compliance."""

    def _make_service(self, monkeypatch):
        """Build a MachinesService with all dependencies mocked."""
        monkeypatch.setattr(
            "maasservicelayer.services.machines.is_fips_enabled",
            lambda: True,
        )
        repo = Mock()
        repo.update_node_bmc = AsyncMock()
        service = MachinesService(
            context=Context(),
            secrets_service=Mock(),
            events_service=Mock(),
            scriptresults_service=Mock(),
            dnspublications_service=Mock(),
            machines_repository=repo,
        )
        return service, repo

    async def test_set_bmc_rejects_unsupported_driver_in_fips(
        self, monkeypatch
    ) -> None:
        service, repo = self._make_service(monkeypatch)
        with pytest.raises(FIPSViolationException):
            await service.set_bmc("abc123", "apc", {})
        repo.update_node_bmc.assert_not_called()

    async def test_set_bmc_rejects_bad_ipmi_cipher_in_fips(
        self, monkeypatch
    ) -> None:
        service, repo = self._make_service(monkeypatch)
        with pytest.raises(FIPSViolationException):
            await service.set_bmc("abc123", "ipmi", {"cipher_suite_id": "3"})
        repo.update_node_bmc.assert_not_called()

    async def test_set_bmc_calls_repository_on_compliant_params(
        self, monkeypatch
    ) -> None:
        service, repo = self._make_service(monkeypatch)
        await service.set_bmc("abc123", "ipmi", {"cipher_suite_id": "17"})
        repo.update_node_bmc.assert_called_once_with(
            "abc123", "ipmi", {"cipher_suite_id": "17"}
        )
