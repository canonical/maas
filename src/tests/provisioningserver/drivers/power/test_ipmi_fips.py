#  Copyright 2026 Canonical Ltd.  This software is licensed under the GNU Affero General Public License version 3 (see the file LICENSE).

"""Unit tests for IPMI FIPS cipher suite enforcement."""

from unittest.mock import patch

import pytest

from provisioningserver.drivers.power import PowerFatalError
from provisioningserver.drivers.power.ipmi import IPMIPowerDriver


class TestIPMICipherSuiteFIPS:
    @pytest.fixture
    def driver(self) -> IPMIPowerDriver:
        return IPMIPowerDriver()

    @pytest.mark.parametrize(
        "cipher_suite_id", ["3", "8", "12", "6", "11", "0"]
    )
    def test_rejects_non_fips_cipher_suites(
        self, driver: IPMIPowerDriver, cipher_suite_id: str
    ) -> None:
        with (
            patch(
                "provisioningserver.drivers.power.ipmi.is_fips_enabled",
                return_value=True,
            ),
            pytest.raises(
                PowerFatalError,
                match=f"IPMI cipher suite {cipher_suite_id} is not permitted",
            ),
        ):
            driver._get_cipher_suite_args(cipher_suite_id)

    def test_accepts_cipher_suite_17_in_fips_mode(
        self, driver: IPMIPowerDriver
    ) -> None:
        with patch(
            "provisioningserver.drivers.power.ipmi.is_fips_enabled",
            return_value=True,
        ):
            assert driver._get_cipher_suite_args("17") == ["-I", "17"]

    def test_defaults_to_cipher_suite_17_in_fips_mode(
        self, driver: IPMIPowerDriver
    ) -> None:
        with patch(
            "provisioningserver.drivers.power.ipmi.is_fips_enabled",
            return_value=True,
        ):
            assert driver._get_cipher_suite_args("") == ["-I", "17"]

    def test_no_enforcement_when_fips_disabled(
        self, driver: IPMIPowerDriver
    ) -> None:
        with patch(
            "provisioningserver.drivers.power.ipmi.is_fips_enabled",
            return_value=False,
        ):
            assert driver._get_cipher_suite_args("3") == ["-I", "3"]
