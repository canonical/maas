#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import patch

from maasservicelayer.db.repositories.power_types import PowerTypeRepository


class TestPowerTypeRepository:
    def test_known_compliant_driver_is_fips_supported(self) -> None:
        entries = PowerTypeRepository().list()
        by_name = {entry["name"]: entry for entry in entries}
        assert by_name["ipmi"]["fips_supported"] is True
        assert by_name["ipmi"]["fips_unsupported_reason"] is None

    def test_known_unsupported_driver_is_not_fips_supported(self) -> None:
        entries = PowerTypeRepository().list()
        by_name = {entry["name"]: entry for entry in entries}
        assert by_name["apc"]["fips_supported"] is False
        assert by_name["apc"]["fips_unsupported_reason"]

    @patch("maasservicelayer.db.repositories.power_types.PowerDriverRegistry")
    def test_unknown_driver_fails_closed(self, mock_registry) -> None:
        # A driver present in the in-process registry but missing from
        # DRIVER_FIPS_REGISTRY must not be reported as FIPS-compliant:
        # get_fips_status_for_driver() is closed-world (fail-closed) and
        # the repository must not diverge from that default.
        mock_registry.get_schema.return_value = [
            {"name": "some-future-driver"}
        ]
        entries = PowerTypeRepository().list()
        assert len(entries) == 1
        assert entries[0]["fips_supported"] is False
        assert "Unknown driver" in entries[0]["fips_unsupported_reason"]
