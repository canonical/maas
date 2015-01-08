# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `PhysicalBlockDevice`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random

from maasserver.models import PhysicalBlockDevice
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestPhysicalBlockDeviceManager(MAASServerTestCase):
    """Tests for the `PhysicalBlockDevice` manager."""

    def test_number_of_physical_devices_for_returns_correct_count(self):
        node = factory.make_Node()
        num_of_devices = random.randint(2, 4)
        for _ in range(num_of_devices):
            factory.make_PhysicalBlockDevice(node=node)
        self.assertEquals(
            num_of_devices,
            PhysicalBlockDevice.objects.number_of_physical_devices_for(node))

    def test_number_of_physical_devices_for_filters_on_node(self):
        node = factory.make_Node()
        num_of_devices = random.randint(2, 4)
        for _ in range(num_of_devices):
            factory.make_PhysicalBlockDevice(node=node)
        for _ in range(3):
            factory.make_PhysicalBlockDevice()
        self.assertEquals(
            num_of_devices,
            PhysicalBlockDevice.objects.number_of_physical_devices_for(node))

    def test_total_size_of_physical_devices_for_returns_sum_of_size(self):
        node = factory.make_Node()
        sizes = [
            random.randint(1000 * 1000, 1000 * 1000 * 1000)
            for _ in range(3)
            ]
        for size in sizes:
            factory.make_PhysicalBlockDevice(node=node, size=size)
        self.assertEquals(
            sum(sizes),
            PhysicalBlockDevice.objects.total_size_of_physical_devices_for(
                node))

    def test_total_size_of_physical_devices_for_filters_on_node(self):
        node = factory.make_Node()
        sizes = [
            random.randint(1000 * 1000, 1000 * 1000 * 1000)
            for _ in range(3)
            ]
        for size in sizes:
            factory.make_PhysicalBlockDevice(node=node, size=size)
        for _ in range(3):
            factory.make_PhysicalBlockDevice()
        self.assertEquals(
            sum(sizes),
            PhysicalBlockDevice.objects.total_size_of_physical_devices_for(
                node))
