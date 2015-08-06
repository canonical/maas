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

from uuid import uuid4

from maasserver.enum import (
    CACHE_MODE_TYPE,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
)
from maasserver.forms import (
    CreateBcacheForm,
    UpdateBcacheForm,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestCreateBcacheForm(MAASServerTestCase):

    def test_required_fields(self):
        node = factory.make_Node()
        form = CreateBcacheForm(node=node, data={})

        self.assertFalse(form.is_valid(), form.errors)
        self.assertDictContainsSubset(
            {'cache_mode': [u'This field is required.']}, form.errors)

    def test_choices_are_being_populated_correctly(self):
        node = factory.make_Node()
        # Make 10 block devices.
        bds = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000 ** 4)
            for _ in range(10)
        ]
        # Partition the last 5 devices with a single partition.
        partitions = [
            factory.make_PartitionTable(block_device=bd).add_partition()
            for bd in bds[5:]
        ]
        partition_choices = [
            partition.id
            for partition in partitions
        ] + [
            partition.name
            for partition in partitions
        ]
        # Get the IDs of the non-partitioned devices.
        block_devices = [
            bd.id
            for bd in bds
            if bd.get_partitiontable() is None
        ] + [
            bd.name
            for bd in bds
            if bd.get_partitiontable() is None
        ]
        form = CreateBcacheForm(node=node, data={})
        self.assertItemsEqual(
            block_devices,
            [k for (k, v) in form.fields['cache_device'].choices])
        self.assertItemsEqual(
            partition_choices,
            [k for (k, v) in form.fields['cache_partition'].choices])
        self.assertItemsEqual(
            block_devices,
            [k for (k, v) in form.fields['backing_device'].choices])
        self.assertItemsEqual(
            partition_choices,
            [k for (k, v) in form.fields['backing_partition'].choices])

    def test_bcache_creation_on_save(self):
        node = factory.make_Node()
        backing_size = 10 * 1000 ** 4
        cache_size = 1000 ** 4
        cache_device = factory.make_PhysicalBlockDevice(
            node=node, size=cache_size)
        backing_device = factory.make_PhysicalBlockDevice(
            node=node, size=backing_size)
        uuid = unicode(uuid4())
        form = CreateBcacheForm(node=node, data={
            'name': 'bcache0',
            'uuid': uuid,
            'cache_device': cache_device.id,
            'backing_device': backing_device.id,
            'cache_mode': CACHE_MODE_TYPE.WRITEBACK,
        })

        self.assertTrue(form.is_valid(), form.errors)
        bcache = form.save()
        self.assertEqual('bcache0', bcache.name)
        self.assertEqual(uuid, bcache.uuid)
        self.assertEqual(
            cache_device.filesystem,
            bcache.filesystems.get(fstype=FILESYSTEM_TYPE.BCACHE_CACHE))
        self.assertEqual(
            backing_device.filesystem,
            bcache.filesystems.get(fstype=FILESYSTEM_TYPE.BCACHE_BACKING))
        self.assertEqual(backing_size, bcache.get_size())
        self.assertEqual(FILESYSTEM_GROUP_TYPE.BCACHE, bcache.group_type)

    def test_bcache_creation_with_names(self):
        node = factory.make_Node()
        backing_size = 10 * 1000 ** 4
        cache_size = 1000 ** 4
        cache_device = factory.make_PhysicalBlockDevice(
            node=node, size=cache_size)
        backing_device = factory.make_PhysicalBlockDevice(
            node=node, size=backing_size)
        backing_partition_table = factory.make_PartitionTable(
            block_device=backing_device)
        backing_partition = backing_partition_table.add_partition()
        uuid = unicode(uuid4())
        form = CreateBcacheForm(node=node, data={
            'name': 'bcache0',
            'uuid': uuid,
            'cache_device': cache_device.name,
            'backing_partition': backing_partition.name,
            'cache_mode': CACHE_MODE_TYPE.WRITEBACK,
        })

        self.assertTrue(form.is_valid(), form.errors)
        bcache = form.save()
        self.assertEqual('bcache0', bcache.name)
        self.assertEqual(uuid, bcache.uuid)
        self.assertEqual(
            cache_device.filesystem,
            bcache.filesystems.get(fstype=FILESYSTEM_TYPE.BCACHE_CACHE))
        self.assertEqual(
            backing_partition.filesystem,
            bcache.filesystems.get(fstype=FILESYSTEM_TYPE.BCACHE_BACKING))
        self.assertEqual(FILESYSTEM_GROUP_TYPE.BCACHE, bcache.group_type)

    def test_bcache_creation_with_invalid_names_fails(self):
        node = factory.make_Node()
        uuid = unicode(uuid4())
        form = CreateBcacheForm(node=node, data={
            'name': 'bcache0',
            'uuid': uuid,
            'cache_partition': "sdapart1",
            'backing_partition': "sda-partXD",
            'cache_mode': CACHE_MODE_TYPE.WRITEBACK,
        })

        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "cache_partition": [
                "Select a valid choice. sdapart1 is not one of the "
                "available choices."],
            "backing_partition": [
                "Select a valid choice. sda-partXD is not one of the "
                "available choices."],
            "__all__": [
                "Either cache_device or cache_partition must be specified."],
            }, form.errors)

    def test_bcache_creation_without_storage_fails(self):
        node = factory.make_Node()
        form = CreateBcacheForm(node=node, data={
            'cache_mode': CACHE_MODE_TYPE.WRITEAROUND
        })

        self.assertFalse(form.is_valid(), form.errors)
        self.assertDictContainsSubset(
            {
                '__all__':
                ['Either cache_device or cache_partition must be '
                 'specified.']
            },
            form.errors)

    def test_bcache_creation_without_cache_fails(self):
        node = factory.make_Node()
        backing_size = 10 * 1000 ** 4
        backing_device = factory.make_PhysicalBlockDevice(
            node=node, size=backing_size)
        form = CreateBcacheForm(node=node, data={
            'cache_mode': CACHE_MODE_TYPE.WRITEAROUND,
            'backing_device': backing_device.id
        })

        self.assertFalse(form.is_valid(), form.errors)
        self.assertDictContainsSubset(
            {
                '__all__':
                ['Either cache_device or cache_partition must be '
                 'specified.']
            },
            form.errors)

    def test_bcache_creation_without_backing_fails(self):
        node = factory.make_Node()
        cache_size = 1000 ** 4
        cache_device = factory.make_PhysicalBlockDevice(
            node=node, size=cache_size)
        form = CreateBcacheForm(node=node, data={
            'cache_mode': CACHE_MODE_TYPE.WRITEAROUND,
            'cache_device': cache_device.id
        })

        self.assertFalse(form.is_valid(), form.errors)
        self.assertDictContainsSubset(
            {'__all__': ['Either backing_device or backing_partition must be '
                         'specified.']},
            form.errors)


class TestUpdateBcacheForm(MAASServerTestCase):

    def test_choices_are_being_populated_correctly(self):
        node = factory.make_Node()
        device_size = 1 * 1000 ** 4
        # Make 10 block devices.
        bds = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        # Partition the last 5 devices with a single partition.
        partitions = [
            factory.make_PartitionTable(block_device=bd).add_partition()
            for bd in bds[5:]
        ]
        partition_choices = [
            p.id
            for p in partitions
        ] + [
            p.name
            for p in partitions
        ]
        # Get the chocies of the non-partitioned devices.
        block_device_choices = [
            bd.id
            for bd in bds
            if bd.get_partitiontable() is None
        ] + [
            bd.name
            for bd in bds
            if bd.get_partitiontable() is None
        ]
        # Make 2 filesystems to be used on the bcache to be edited, one on a
        # device, the other on a partition.
        filesystems = [
            factory.make_Filesystem(
                block_device=bds[0], fstype=FILESYSTEM_TYPE.BCACHE_CACHE),
            factory.make_Filesystem(
                partition=partitions[0], fstype=FILESYSTEM_TYPE.BCACHE_BACKING)
            ]
        # Create a bcache with one device and one partition.
        bcache = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE, filesystems=filesystems)
        form = UpdateBcacheForm(bcache=bcache, data={})
        # Should allow all devices and partitions, including the ones currently
        # allocated for bcache.
        self.assertItemsEqual(
            block_device_choices,
            [k for (k, v) in form.fields['cache_device'].choices])
        self.assertItemsEqual(
            partition_choices,
            [k for (k, v) in form.fields['cache_partition'].choices])
        self.assertItemsEqual(
            block_device_choices,
            [k for (k, v) in form.fields['backing_device'].choices])
        self.assertItemsEqual(
            partition_choices,
            [k for (k, v) in form.fields['backing_partition'].choices])

    def test_bcache_update_with_invalid_mode(self):
        """Tests the mode field validation."""
        node = factory.make_Node()
        # Make 2 filesystems to be used on the bcache to be edited, one on a
        # device, the other on a partition.
        filesystems = [
            factory.make_Filesystem(
                block_device=factory.make_PhysicalBlockDevice(node=node),
                fstype=FILESYSTEM_TYPE.BCACHE_CACHE),
            factory.make_Filesystem(
                partition=factory.make_PartitionTable(
                    block_device=factory.make_PhysicalBlockDevice(
                        node=node)).add_partition(),
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING)
            ]
        # Create a bcache with one device and one partition.
        bcache = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE, filesystems=filesystems)
        form = UpdateBcacheForm(bcache=bcache, data={
            'cache_mode': 'Writeonly'
        })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertIn(
            'Select a valid choice.', form.errors['cache_mode'][0])
        self.assertIn(
            'is not one of the available choices.',
            form.errors['cache_mode'][0])

    def test_bcache_with_invalid_block_device_fails(self):
        """Tests allowable device list validation."""
        node = factory.make_Node()
        # Make 2 filesystems to be used on the bcache to be edited, one on a
        # device, the other on a partition on another node.
        filesystems = [
            factory.make_Filesystem(
                block_device=factory.make_PhysicalBlockDevice(node=node),
                fstype=FILESYSTEM_TYPE.BCACHE_CACHE),
            factory.make_Filesystem(
                partition=factory.make_PartitionTable(
                    block_device=factory.make_PhysicalBlockDevice(
                        node=node)).add_partition(),
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING)
            ]
        backing_device = factory.make_PhysicalBlockDevice()
        # Create a bcache with one device and one partition.
        bcache = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE, filesystems=filesystems)
        form = UpdateBcacheForm(bcache=bcache, data={
            'backing_device': backing_device.id
        })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertIn(
            'Select a valid choice.', form.errors['backing_device'][0])
        self.assertIn(
            'is not one of the available choices.',
            form.errors['backing_device'][0])
