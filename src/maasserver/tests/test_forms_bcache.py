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
from maasserver.forms import CreateBcacheForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestCreateRaidForm(MAASServerTestCase):

    def test_required_fields(self):
        node = factory.make_Node()
        form = CreateBcacheForm(node=node, data={})

        self.assertFalse(form.is_valid(), form.errors)
        self.assertDictContainsSubset(
            {'cache_mode': [u'This field is required.']}, form.errors)

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
        form = CreateBcacheForm(node=node, data={})
        self.assertItemsEqual(
            block_devices,
            [k for (k, v) in form.fields['cache_device'].choices])
        self.assertItemsEqual(
            partitions,
            [k for (k, v) in form.fields['cache_partition'].choices])
        self.assertItemsEqual(
            block_devices,
            [k for (k, v) in form.fields['backing_device'].choices])
        self.assertItemsEqual(
            partitions,
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
