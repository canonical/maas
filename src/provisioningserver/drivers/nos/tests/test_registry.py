# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.nos.registry`."""


from unittest.mock import sentinel

from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.nos.registry import NOSDriverRegistry
from provisioningserver.drivers.nos.tests.test_base import make_nos_driver_base
from provisioningserver.utils.testing import RegistryFixture


class TestNOSDriverRegistry(MAASTestCase):
    def setUp(self):
        super().setUp()
        # Ensure the global registry is empty for each test run.
        self.useFixture(RegistryFixture())

    def test_registry(self):
        self.assertItemsEqual([], NOSDriverRegistry)
        NOSDriverRegistry.register_item("driver", sentinel.driver)
        self.assertIn(
            sentinel.driver, (item for name, item in NOSDriverRegistry)
        )

    def test_get_schema(self):
        fake_driver_one = make_nos_driver_base()
        fake_driver_two = make_nos_driver_base()
        NOSDriverRegistry.register_item(fake_driver_one.name, fake_driver_one)
        NOSDriverRegistry.register_item(fake_driver_two.name, fake_driver_two)
        self.assertItemsEqual(
            [
                {
                    "driver_type": "nos",
                    "name": fake_driver_one.name,
                    "description": fake_driver_one.description,
                    "fields": [],
                    "deployable": fake_driver_one.deployable,
                },
                {
                    "driver_type": "nos",
                    "name": fake_driver_two.name,
                    "description": fake_driver_two.description,
                    "fields": [],
                    "deployable": fake_driver_two.deployable,
                },
            ],
            NOSDriverRegistry.get_schema(),
        )
