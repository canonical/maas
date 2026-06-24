#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.fips`."""

from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power.fips import (
    DRIVER_FIPS_REGISTRY,
    DriverFIPSStatus,
    get_fips_compliant_alternatives,
    get_fips_status_for_driver,
)


class TestDriverFIPSRegistry(MAASTestCase):
    def test_known_compliant_driver_returns_true_no_reason(self):
        supported, reason = get_fips_status_for_driver("ipmi")
        self.assertTrue(supported)
        self.assertIsNone(reason)

    def test_known_unsupported_driver_returns_false_with_reason(self):
        supported, reason = get_fips_status_for_driver("apc")
        self.assertFalse(supported)
        self.assertIsNotNone(reason)
        self.assertIn("FIPS", reason)

    def test_unknown_driver_defaults_to_compliant(self):
        # Drivers not in the registry are assumed compliant (open-world).
        supported, reason = get_fips_status_for_driver("unknown_driver")
        self.assertTrue(supported)
        self.assertIsNone(reason)

    def test_all_registry_entries_have_reason_iff_unsupported(self):
        for name, (status, reason) in DRIVER_FIPS_REGISTRY.items():
            if status == DriverFIPSStatus.UNSUPPORTED:
                self.assertIsNotNone(
                    reason,
                    f"driver {name!r} is UNSUPPORTED but has no reason",
                )
            else:
                self.assertIsNone(
                    reason,
                    f"driver {name!r} is COMPLIANT but has a reason set",
                )

    def test_unsupported_drivers_include_known_non_fips(self):
        for driver in ("apc", "dli", "eaton", "raritan", "recs_box"):
            supported, _ = get_fips_status_for_driver(driver)
            self.assertFalse(
                supported, f"expected {driver!r} to be FIPS-unsupported"
            )

    def test_every_registry_key_matches_a_registered_driver_name(self):
        # A key that does not correspond to a real power driver `name`
        # (e.g. "seamicro" instead of "sm15k") would silently fall through
        # to the COMPLIANT default and fail to block an unsupported driver.
        from provisioningserver.drivers.power.registry import (
            PowerDriverRegistry,
        )

        driver_names = {name for name, _ in PowerDriverRegistry}
        for key in DRIVER_FIPS_REGISTRY:
            self.assertIn(
                key,
                driver_names,
                f"registry key {key!r} does not match any power driver name",
            )


class TestGetFipsCompliantAlternatives(MAASTestCase):
    def test_returns_only_compliant_drivers(self):
        alternatives = get_fips_compliant_alternatives()
        for name in alternatives:
            status, _ = DRIVER_FIPS_REGISTRY.get(
                name, (DriverFIPSStatus.COMPLIANT, None)
            )
            self.assertEqual(
                status,
                DriverFIPSStatus.COMPLIANT,
                f"alternative {name!r} is not COMPLIANT in registry",
            )

    def test_does_not_include_unsupported_drivers(self):
        alternatives = get_fips_compliant_alternatives()
        for name, (status, _) in DRIVER_FIPS_REGISTRY.items():
            if status == DriverFIPSStatus.UNSUPPORTED:
                self.assertNotIn(
                    name,
                    alternatives,
                    f"unsupported driver {name!r} should not appear in alternatives",
                )

    def test_returns_nonempty_list(self):
        self.assertGreater(len(get_fips_compliant_alternatives()), 0)
