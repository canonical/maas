# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.chassis.registry`."""

__all__ = []

from unittest.mock import sentinel

from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.chassis.registry import ChassisDriverRegistry
from provisioningserver.drivers.chassis.tests.test_base import (
    make_chassis_driver_base,
)
from provisioningserver.utils.testing import RegistryFixture


class TestChassisDriverRegistry(MAASTestCase):

    def setUp(self):
        super(TestChassisDriverRegistry, self).setUp()
        # Ensure the global registry is empty for each test run.
        self.useFixture(RegistryFixture())

    def test_registry(self):
        self.assertItemsEqual([], ChassisDriverRegistry)
        ChassisDriverRegistry.register_item("driver", sentinel.driver)
        self.assertIn(
            sentinel.driver,
            (item for name, item in ChassisDriverRegistry))

    def test_get_schema(self):
        fake_driver_one = make_chassis_driver_base()
        fake_driver_two = make_chassis_driver_base()
        ChassisDriverRegistry.register_item(
            fake_driver_one.name, fake_driver_one)
        ChassisDriverRegistry.register_item(
            fake_driver_two.name, fake_driver_two)
        self.assertItemsEqual([
            {
                'name': fake_driver_one.name,
                'description': fake_driver_one.description,
                'fields': [],
                'queryable': fake_driver_one.queryable,
                'missing_packages': fake_driver_one.detect_missing_packages(),
                'composable': fake_driver_one.composable,
            },
            {
                'name': fake_driver_two.name,
                'description': fake_driver_two.description,
                'fields': [],
                'queryable': fake_driver_two.queryable,
                'missing_packages': fake_driver_two.detect_missing_packages(),
                'composable': fake_driver_two.composable,
            }],
            ChassisDriverRegistry.get_schema())
