# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.pod.registry`."""

from unittest.mock import sentinel

from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.pod.registry import PodDriverRegistry
from provisioningserver.drivers.pod.tests.test_base import make_pod_driver_base
from provisioningserver.utils.testing import RegistryFixture


class TestPodDriverRegistry(MAASTestCase):
    def setUp(self):
        super().setUp()
        # Ensure the global registry is empty for each test run.
        self.useFixture(RegistryFixture())

    def test_registry(self):
        self.assertEqual([], list(PodDriverRegistry))
        PodDriverRegistry.register_item("driver", sentinel.driver)
        self.assertIn(
            sentinel.driver, (item for name, item in PodDriverRegistry)
        )

    def test_get_schema(self):
        fake_driver_one = make_pod_driver_base()
        fake_driver_two = make_pod_driver_base()
        PodDriverRegistry.register_item(fake_driver_one.name, fake_driver_one)
        PodDriverRegistry.register_item(fake_driver_two.name, fake_driver_two)
        self.assertEqual(
            [
                {
                    "driver_type": "pod",
                    "name": fake_driver_one.name,
                    "description": fake_driver_one.description,
                    "fields": [],
                    "queryable": fake_driver_one.queryable,
                    "missing_packages": fake_driver_one.detect_missing_packages(),
                    "chassis": True,
                    "can_probe": True,
                },
                {
                    "driver_type": "pod",
                    "name": fake_driver_two.name,
                    "description": fake_driver_two.description,
                    "fields": [],
                    "queryable": fake_driver_two.queryable,
                    "missing_packages": fake_driver_two.detect_missing_packages(),
                    "chassis": True,
                    "can_probe": True,
                },
            ],
            PodDriverRegistry.get_schema(),
        )
