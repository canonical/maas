# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Registry"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.testcase import MAASTestCase
from mock import (
    Mock,
    sentinel,
    )
from provisioningserver.driver.registry import _registry
from provisioningserver.driver import (
    ArchitectureRegistry,
    BootResourceRegistry,
    Registry,
    PowerTypeRegistry,
    )


class TestRegistry(MAASTestCase):

    def setUp(self):
        # Ensure the registry global is empty for each test run.
        global _registry
        super(TestRegistry, self).setUp()
        self.saved_registry = _registry.copy()
        _registry.clear()

    def tearDown(self):
        global _registry
        super(TestRegistry, self).tearDown()
        _registry.clear()
        _registry.update(self.saved_registry)

    def test_is_singleton_over_multiple_imports(self):
        resource = Mock()
        Registry.registry_name = sentinel.registry_name
        Registry.register_item(resource, "resource")
        from provisioningserver.driver import Registry as Registry2
        Registry2.registry_name = sentinel.registry_name
        resource2 = Mock()
        Registry2.register_item(resource2, "resource2")
        self.assertItemsEqual(
            [resource, resource2],
            Registry2.get_items().values())

    def test_bootresource_registry(self):
        resource = Mock()
        self.assertEqual({}, BootResourceRegistry.get_items())
        BootResourceRegistry.register_item(resource, "resource")
        self.assertIn(resource, BootResourceRegistry.get_items().values())

    def test_architecture_registry(self):
        resource = Mock()
        self.assertEqual({}, ArchitectureRegistry.get_items())
        ArchitectureRegistry.register_item(resource, "resource")
        self.assertIn(resource, ArchitectureRegistry.get_items().values())

    def test_power_type_registry(self):
        resource = Mock()
        self.assertEqual({}, PowerTypeRegistry.get_items())
        PowerTypeRegistry.register_item(resource, "resource")
        self.assertIn(resource, PowerTypeRegistry.get_items().values())
