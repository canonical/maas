# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.registry`."""

from unittest.mock import sentinel

from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.pod.tests.test_base import make_pod_driver_base
from provisioningserver.drivers.power.registry import PowerDriverRegistry
from provisioningserver.drivers.power.tests.test_base import (
    make_power_driver_base,
)
from provisioningserver.utils.testing import RegistryFixture


class TestPowerDriverRegistry(MAASTestCase):
    def setUp(self):
        super().setUp()
        # Ensure the global registry is empty for each test run.
        self.useFixture(RegistryFixture())

    def test_registry(self):
        self.assertEqual([], list(PowerDriverRegistry))
        PowerDriverRegistry.register_item("driver", sentinel.driver)
        self.assertIn(
            sentinel.driver, (item for name, item in PowerDriverRegistry)
        )

    def test_get_schema(self):
        fake_driver_one = make_power_driver_base()
        fake_driver_two = make_power_driver_base()
        fake_pod_driver = make_pod_driver_base()
        PowerDriverRegistry.register_item(
            fake_driver_one.name, fake_driver_one
        )
        PowerDriverRegistry.register_item(
            fake_driver_two.name, fake_driver_two
        )
        PowerDriverRegistry.register_item(
            fake_pod_driver.name, fake_pod_driver
        )
        self.assertEqual(
            [
                {
                    "driver_type": "power",
                    "name": fake_driver_one.name,
                    "description": fake_driver_one.description,
                    "chassis": fake_driver_one.chassis,
                    "can_probe": fake_driver_one.can_probe,
                    "fields": [],
                    "queryable": fake_driver_one.queryable,
                    "missing_packages": fake_driver_one.detect_missing_packages(),
                },
                {
                    "driver_type": "power",
                    "name": fake_driver_two.name,
                    "description": fake_driver_two.description,
                    "chassis": fake_driver_two.chassis,
                    "can_probe": fake_driver_two.can_probe,
                    "fields": [],
                    "queryable": fake_driver_two.queryable,
                    "missing_packages": fake_driver_two.detect_missing_packages(),
                },
                {
                    "driver_type": "pod",
                    "name": fake_pod_driver.name,
                    "description": fake_pod_driver.description,
                    "chassis": fake_pod_driver.chassis,
                    "can_probe": fake_pod_driver.can_probe,
                    "fields": [],
                    "queryable": fake_pod_driver.queryable,
                    "missing_packages": fake_pod_driver.detect_missing_packages(),
                },
            ],
            PowerDriverRegistry.get_schema(),
        )
