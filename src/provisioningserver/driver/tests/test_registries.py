# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the driver registries."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.testcase import MAASTestCase
from mock import sentinel
from provisioningserver.driver import (
    Architecture,
    ArchitectureRegistry,
    BootResourceRegistry,
    OperatingSystemRegistry,
    PowerTypeRegistry,
    )
from provisioningserver.utils.testing import RegistryFixture


class TestRegistries(MAASTestCase):

    def setUp(self):
        super(TestRegistries, self).setUp()
        # Ensure the global registry is empty for each test run.
        self.useFixture(RegistryFixture())

    def test_bootresource_registry(self):
        self.assertItemsEqual([], BootResourceRegistry)
        BootResourceRegistry.register_item("resource", sentinel.resource)
        self.assertIn(
            sentinel.resource,
            (item for name, item in BootResourceRegistry))

    def test_architecture_registry(self):
        self.assertItemsEqual([], ArchitectureRegistry)
        ArchitectureRegistry.register_item("resource", sentinel.resource)
        self.assertIn(
            sentinel.resource,
            (item for name, item in ArchitectureRegistry))

    def test_get_by_pxealias_returns_valid_arch(self):
        arch1 = Architecture(
            name="arch1", description="arch1",
            pxealiases=["archibald", "reginald"])
        arch2 = Architecture(
            name="arch2", description="arch2",
            pxealiases=["fake", "foo"])
        ArchitectureRegistry.register_item("arch1", arch1)
        ArchitectureRegistry.register_item("arch2", arch2)
        self.assertEqual(
            arch1, ArchitectureRegistry.get_by_pxealias("archibald"))

    def test_get_by_pxealias_returns_None_if_none_matching(self):
        arch1 = Architecture(
            name="arch1", description="arch1",
            pxealiases=["archibald", "reginald"])
        arch2 = Architecture(name="arch2", description="arch2")
        ArchitectureRegistry.register_item("arch1", arch1)
        ArchitectureRegistry.register_item("arch2", arch2)
        self.assertEqual(
            None, ArchitectureRegistry.get_by_pxealias("stinkywinky"))

    def test_operating_system_registry(self):
        self.assertItemsEqual([], OperatingSystemRegistry)
        OperatingSystemRegistry.register_item("resource", sentinel.resource)
        self.assertIn(
            sentinel.resource,
            (item for name, item in OperatingSystemRegistry))

    def test_power_type_registry(self):
        self.assertItemsEqual([], PowerTypeRegistry)
        PowerTypeRegistry.register_item("resource", sentinel.resource)
        self.assertIn(
            sentinel.resource,
            (item for name, item in PowerTypeRegistry))
