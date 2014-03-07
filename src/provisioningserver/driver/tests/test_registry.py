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
from provisioningserver import driver
from provisioningserver.driver import (
    BootResourceRegistry,
    Registry,
    )


class TestRegistry(MAASTestCase):

    def tearDown(self):
        # Clear out the registry global for the next test.
        super(TestRegistry, self).tearDown()
        driver._registry = {}

    def test_is_singleton_over_multiple_imports(self):
        resource = Mock()
        Registry.registry_name = sentinel.registry_name
        Registry.register_item(resource)
        from provisioningserver.driver import Registry as Registry2
        Registry2.registry_name = sentinel.registry_name
        resource2 = Mock()
        Registry2.register_item(resource2)
        self.assertItemsEqual(
            [resource, resource2],
            Registry2.get_items())

    def test_bootresource_registry(self):
        resource = Mock()
        BootResourceRegistry.register_item(resource)
        self.assertIn(resource, BootResourceRegistry.get_items())
