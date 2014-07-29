# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.osystem`."""

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
from provisioningserver.drivers.osystem import OperatingSystemRegistry
from provisioningserver.utils.testing import RegistryFixture


class TestOperatingSystemRegistry(MAASTestCase):

    def setUp(self):
        super(TestOperatingSystemRegistry, self).setUp()
        # Ensure the global registry is empty for each test run.
        self.useFixture(RegistryFixture())

    def test_operating_system_registry(self):
        self.assertItemsEqual([], OperatingSystemRegistry)
        OperatingSystemRegistry.register_item("resource", sentinel.resource)
        self.assertIn(
            sentinel.resource,
            (item for name, item in OperatingSystemRegistry))
