# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for all forms that are used with `RAID`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.enum import FILESYSTEM_GROUP_TYPE
from maasserver.forms import CreateRaidForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestCreateRaidForm(MAASServerTestCase):

    def test_requires_fields(self):
        node = factory.make_Node()
        form = CreateRaidForm(node=node, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertDictContainsSubset(
            {
                'level': ['This field is required.'],
                'name': ['This field is required.']
            },
            form.errors)

    def test_choices_are_being_populated_correctly(self):
        node = factory.make_Node()
        bds = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000 ** 4)
            for _ in range(10)
        ]
        for bd in bds[5:]:
            factory.make_PartitionTable(block_device=bd)
        block_devices = [
            bd.id
            for bd in bds
            if bd.get_partitiontable() is None
        ]
        partitions = [
            bd.get_partitiontable().add_partition().id
            for bd in bds[5:]
        ]
        form = CreateRaidForm(node=node, data={})
        self.assertItemsEqual(
            block_devices,
            [k for (k, v) in form.fields['block_devices'].choices])
        self.assertItemsEqual(
            partitions,
            [k for (k, v) in form.fields['partitions'].choices])
        self.assertItemsEqual(
            block_devices,
            [k for (k, v) in form.fields['spare_devices'].choices])
        self.assertItemsEqual(
            partitions,
            [k for (k, v) in form.fields['spare_partitions'].choices])

    def test_raid_creation_on_save(self):
        node = factory.make_Node()
        bds = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000 ** 4)
            for _ in range(10)
        ]
        for bd in bds[5:]:
            factory.make_PartitionTable(block_device=bd)
        block_devices = [
            bd.id
            for bd in bds
            if bd.get_partitiontable() is None
        ]
        partitions = [
            bd.get_partitiontable().add_partition().id
            for bd in bds[5:]
        ]
        form = CreateRaidForm(node=node, data={
            'name': 'md1',
            'level': FILESYSTEM_GROUP_TYPE.RAID_6,
            'block_devices': block_devices,
            'partitions': partitions,
        })
        self.assertTrue(form.is_valid(), form.errors)
        raid = form.save()
        self.assertEqual('md1', raid.name)
        self.assertEqual(8 * 10 * 1000 ** 4, raid.get_size())
        self.assertEqual(FILESYSTEM_GROUP_TYPE.RAID_6, raid.group_type)
        self.assertItemsEqual(
            block_devices,
            [fs.block_device.id
             for fs in raid.filesystems.exclude(block_device=None)])
        self.assertItemsEqual(
            partitions,
            [fs.partition.id
             for fs in raid.filesystems.exclude(partition=None)])

    def test_raid_creation_without_storage_fails(self):
        node = factory.make_Node()
        for level in [
                FILESYSTEM_GROUP_TYPE.RAID_0,
                FILESYSTEM_GROUP_TYPE.RAID_1,
                FILESYSTEM_GROUP_TYPE.RAID_4,
                FILESYSTEM_GROUP_TYPE.RAID_5,
                FILESYSTEM_GROUP_TYPE.RAID_6,
        ]:
            form = CreateRaidForm(node=node, data={
                'name': 'md1',
                'level': level,
                'block_devices': [],
                'partitions': [],
            })
            self.assertFalse(form.is_valid())
            self.assertDictContainsSubset(
                {
                    u'__all__': ['At least one block device or partition must '
                                 'be added to the array.']
                },
                form.errors)
