# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `ISCSIBlockDevice`."""


import random

from django.core.exceptions import ValidationError

from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.iscsiblockdevice import (
    ISCSIBlockDevice,
    validate_iscsi_target,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.testcase import MAASTestCase


class TestValidateISCSITarget(MAASTestCase):
    """Tests for the `validate_iscsi_target`."""

    def test_raises_no_errors_with_iscsi_prefix(self):
        host = factory.make_ipv4_address()
        target_name = factory.make_name("target")
        validate_iscsi_target("iscsi:%s::::%s" % (host, target_name))

    def test_raises_no_errors_without_iscsi_prefix(self):
        host = factory.make_ipv4_address()
        target_name = factory.make_name("target")
        validate_iscsi_target("%s::::%s" % (host, target_name))

    def test_raises_error_when_invalid(self):
        host = factory.make_ipv4_address()
        self.assertRaises(
            ValidationError, validate_iscsi_target, "%s::::" % host
        )


class TestISCSIBlockDeviceManager(MAASServerTestCase):
    """Tests for the `ISCSIBlockDevice` manager."""

    def test_total_size_of_iscsi_devices_for_returns_sum_of_size(self):
        node = factory.make_Node(with_boot_disk=False)
        sizes = [
            random.randint(MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE * 2)
            for _ in range(3)
        ]
        for size in sizes:
            factory.make_ISCSIBlockDevice(node=node, size=size)
        self.assertEqual(
            sum(sizes),
            ISCSIBlockDevice.objects.total_size_of_iscsi_devices_for(node),
        )

    def test_total_size_of_iscsi_devices_for_filters_on_node(self):
        node = factory.make_Node(with_boot_disk=False)
        sizes = [
            random.randint(MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE * 2)
            for _ in range(3)
        ]
        for size in sizes:
            factory.make_ISCSIBlockDevice(node=node, size=size)
        for _ in range(3):
            factory.make_ISCSIBlockDevice()
        self.assertEqual(
            sum(sizes),
            ISCSIBlockDevice.objects.total_size_of_iscsi_devices_for(node),
        )


class TestISCSIBlockDevice(MAASServerTestCase):
    """Tests for `ISCSIBlockDevice`."""

    def test_normalises_target(self):
        host = factory.make_ipv4_address()
        target_name = factory.make_name("target")
        target = "%s::::%s" % (host, target_name)
        node = factory.make_Node()
        block_device = ISCSIBlockDevice.objects.create(
            name=factory.make_name("iscsi"),
            node=node,
            size=random.randint(1024 ** 3, 1024 ** 4),
            block_size=512,
            target=target,
        )
        self.assertEquals("iscsi:%s" % target, block_device.target)
