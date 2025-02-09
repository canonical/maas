# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from uuid import uuid4

from maasserver.enum import (
    CACHE_MODE_TYPE,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
)
from maasserver.forms import CreateBcacheForm, UpdateBcacheForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestCreateBcacheForm(MAASServerTestCase):
    def test_required_fields(self):
        node = factory.make_Node()
        form = CreateBcacheForm(node=node, data={})

        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            form.errors["cache_mode"], ["This field is required."]
        )

    def test_choices_are_being_populated_correctly(self):
        node = factory.make_Node(with_boot_disk=False)
        # Make 10 block devices.
        bds = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000**4)
            for _ in range(10)
        ]
        # Make 3 cache sets.
        cache_sets = [factory.make_CacheSet(node=node) for _ in range(3)]
        cache_set_choices = [cache_set.id for cache_set in cache_sets] + [
            cache_set.name for cache_set in cache_sets
        ]
        # Partition the last 5 devices with a single partition.
        partitions = [
            factory.make_PartitionTable(block_device=bd).add_partition()
            for bd in bds[5:]
        ]
        partition_choices = [partition.id for partition in partitions] + [
            partition.name for partition in partitions
        ]
        # Get the IDs of the non-partitioned devices.
        block_devices = [
            bd.id for bd in bds if bd.get_partitiontable() is None
        ] + [bd.name for bd in bds if bd.get_partitiontable() is None]
        form = CreateBcacheForm(node=node, data={})
        self.assertCountEqual(
            cache_set_choices,
            [k for (k, v) in form.fields["cache_set"].choices],
        )
        self.assertCountEqual(
            block_devices,
            [k for (k, v) in form.fields["backing_device"].choices],
        )
        self.assertCountEqual(
            partition_choices,
            [k for (k, v) in form.fields["backing_partition"].choices],
        )

    def test_bcache_creation_on_save(self):
        node = factory.make_Node()
        backing_size = 10 * 1000**4
        cache_set = factory.make_CacheSet(node=node)
        backing_device = factory.make_PhysicalBlockDevice(
            node=node, size=backing_size
        )
        uuid = str(uuid4())
        form = CreateBcacheForm(
            node=node,
            data={
                "name": "bcache0",
                "uuid": uuid,
                "cache_set": cache_set.id,
                "backing_device": backing_device.id,
                "cache_mode": CACHE_MODE_TYPE.WRITEBACK,
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        bcache = form.save()
        self.assertEqual("bcache0", bcache.name)
        self.assertEqual(uuid, bcache.uuid)
        self.assertEqual(cache_set, bcache.cache_set)
        self.assertEqual(
            backing_device.get_effective_filesystem(),
            bcache.filesystems.get(fstype=FILESYSTEM_TYPE.BCACHE_BACKING),
        )
        self.assertEqual(backing_size, bcache.get_size())
        self.assertEqual(FILESYSTEM_GROUP_TYPE.BCACHE, bcache.group_type)

    def test_bcache_creation_with_names(self):
        node = factory.make_Node()
        backing_size = 10 * 1000**4
        cache_set = factory.make_CacheSet(node=node)
        backing_device = factory.make_PhysicalBlockDevice(
            node=node, size=backing_size
        )
        backing_partition_table = factory.make_PartitionTable(
            block_device=backing_device
        )
        backing_partition = backing_partition_table.add_partition()
        uuid = str(uuid4())
        form = CreateBcacheForm(
            node=node,
            data={
                "name": "bcache0",
                "uuid": uuid,
                "cache_set": cache_set.name,
                "backing_partition": backing_partition.name,
                "cache_mode": CACHE_MODE_TYPE.WRITEBACK,
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        bcache = form.save()
        self.assertEqual("bcache0", bcache.name)
        self.assertEqual(uuid, bcache.uuid)
        self.assertEqual(cache_set, bcache.cache_set)
        self.assertEqual(
            backing_partition.get_effective_filesystem(),
            bcache.filesystems.get(fstype=FILESYSTEM_TYPE.BCACHE_BACKING),
        )
        self.assertEqual(FILESYSTEM_GROUP_TYPE.BCACHE, bcache.group_type)

    def test_bcache_creation_on_boot_disk(self):
        node = factory.make_Node(with_boot_disk=False)
        boot_disk = factory.make_PhysicalBlockDevice(node=node, bootable=True)
        cache_set = factory.make_CacheSet(node=node)
        form = CreateBcacheForm(
            node=node,
            data={
                "name": "bcache0",
                "cache_set": cache_set.id,
                "backing_device": boot_disk.id,
                "cache_mode": CACHE_MODE_TYPE.WRITEBACK,
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        bcache = form.save()
        self.assertEqual("bcache0", bcache.name)
        self.assertEqual(cache_set, bcache.cache_set)
        self.assertEqual(FILESYSTEM_GROUP_TYPE.BCACHE, bcache.group_type)
        boot_partition = boot_disk.get_partitiontable().partitions.first()
        self.assertEqual(
            boot_partition.get_effective_filesystem(),
            bcache.filesystems.get(fstype=FILESYSTEM_TYPE.BCACHE_BACKING),
        )

    def test_bcache_creation_with_invalid_names_fails(self):
        node = factory.make_Node()
        uuid = str(uuid4())
        form = CreateBcacheForm(
            node=node,
            data={
                "name": "bcache0",
                "uuid": uuid,
                "cache_set": "sdapart1",
                "backing_partition": "sda-partXD",
                "cache_mode": CACHE_MODE_TYPE.WRITEBACK,
            },
        )

        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {
                "cache_set": [
                    "Select a valid choice. sdapart1 is not one of the "
                    "available choices."
                ],
                "backing_partition": [
                    "Select a valid choice. sda-partXD is not one of the "
                    "available choices."
                ],
                "__all__": ["Bcache requires a cache_set."],
            },
            form.errors,
        )

    def test_bcache_creation_without_storage_fails(self):
        node = factory.make_Node()
        form = CreateBcacheForm(
            node=node, data={"cache_mode": CACHE_MODE_TYPE.WRITEAROUND}
        )

        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(form.errors["cache_set"], ["This field is required."])

    def test_bcache_creation_without_cache_set_fails(self):
        node = factory.make_Node()
        backing_size = 10 * 1000**4
        backing_device = factory.make_PhysicalBlockDevice(
            node=node, size=backing_size
        )
        form = CreateBcacheForm(
            node=node,
            data={
                "cache_mode": CACHE_MODE_TYPE.WRITEAROUND,
                "backing_device": backing_device.id,
            },
        )

        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(form.errors["cache_set"], ["This field is required."])

    def test_bcache_creation_without_backing_fails(self):
        node = factory.make_Node()
        cache_set = factory.make_CacheSet(node=node)
        form = CreateBcacheForm(
            node=node,
            data={
                "cache_mode": CACHE_MODE_TYPE.WRITEAROUND,
                "cache_set": cache_set.id,
            },
        )

        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            form.errors["__all__"],
            ["Either backing_device or backing_partition must be specified."],
        )


class TestUpdateBcacheForm(MAASServerTestCase):
    def test_choices_are_being_populated_correctly(self):
        node = factory.make_Node(with_boot_disk=False)
        device_size = 1 * 1000**4
        # Make 10 block devices.
        bds = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        # Make 3 cache sets.
        cache_sets = [factory.make_CacheSet(node=node) for _ in range(3)]
        cache_set_choices = [cache_set.id for cache_set in cache_sets] + [
            cache_set.name for cache_set in cache_sets
        ]
        # Partition the last 5 devices with a single partition.
        partitions = [
            factory.make_PartitionTable(block_device=bd).add_partition()
            for bd in bds[5:]
        ]
        partition_choices = [p.id for p in partitions] + [
            p.name for p in partitions
        ]
        # Get the chocies of the non-partitioned devices.
        block_device_choices = [
            bd.id for bd in bds if bd.get_partitiontable() is None
        ] + [bd.name for bd in bds if bd.get_partitiontable() is None]
        # Use one of the cache sets and one of the backing devices.
        filesystems = [
            factory.make_Filesystem(
                partition=partitions[0], fstype=FILESYSTEM_TYPE.BCACHE_BACKING
            )
        ]
        bcache = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_set=cache_sets[0],
            filesystems=filesystems,
        )
        form = UpdateBcacheForm(bcache=bcache, data={})
        # Should allow all devices and partitions, including the ones currently
        # allocated for bcache.
        self.assertCountEqual(
            cache_set_choices,
            [k for (k, v) in form.fields["cache_set"].choices],
        )
        self.assertCountEqual(
            block_device_choices,
            [k for (k, v) in form.fields["backing_device"].choices],
        )
        self.assertCountEqual(
            partition_choices,
            [k for (k, v) in form.fields["backing_partition"].choices],
        )

    def test_lookup_by_name(self):
        node = factory.make_Node(with_boot_disk=True)
        disk = factory.make_PhysicalBlockDevice(node=node)
        cache_set = factory.make_CacheSet(node=node)
        filesystems = [
            factory.make_Filesystem(
                partition=factory.make_PartitionTable(
                    block_device=factory.make_PhysicalBlockDevice(node=node)
                ).add_partition(),
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
            )
        ]
        bcache = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_set=cache_set,
            filesystems=filesystems,
        )

        # create a disk with same name on another machine
        factory.make_PhysicalBlockDevice(
            node=factory.make_Node(with_boot_disk=False),
            name=disk.name,
        )

        form = UpdateBcacheForm(
            bcache=bcache, data={"backing_device": disk.name}
        )
        self.assertTrue(form.is_valid(), form.errors)
        bcache = form.save()
        self.assertEqual(
            disk.get_effective_filesystem(),
            bcache.filesystems.get(fstype=FILESYSTEM_TYPE.BCACHE_BACKING),
        )

    def test_bcache_update_with_invalid_mode(self):
        """Tests the mode field validation."""
        node = factory.make_Node()
        cache_set = factory.make_CacheSet(node=node)
        filesystems = [
            factory.make_Filesystem(
                partition=factory.make_PartitionTable(
                    block_device=factory.make_PhysicalBlockDevice(node=node)
                ).add_partition(),
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
            )
        ]
        bcache = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_set=cache_set,
            filesystems=filesystems,
        )
        form = UpdateBcacheForm(
            bcache=bcache, data={"cache_mode": "Writeonly"}
        )
        self.assertFalse(form.is_valid(), form.errors)
        self.assertIn("Select a valid choice.", form.errors["cache_mode"][0])
        self.assertIn(
            "is not one of the available choices.",
            form.errors["cache_mode"][0],
        )

    def test_bcache_with_invalid_block_device_fails(self):
        """Tests allowable device list validation."""
        node = factory.make_Node()
        cache_set = factory.make_CacheSet(node=node)
        filesystems = [
            factory.make_Filesystem(
                partition=factory.make_PartitionTable(
                    block_device=factory.make_PhysicalBlockDevice(node=node)
                ).add_partition(),
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
            )
        ]
        backing_device = factory.make_PhysicalBlockDevice()
        bcache = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_set=cache_set,
            filesystems=filesystems,
        )
        form = UpdateBcacheForm(
            bcache=bcache, data={"backing_device": backing_device.id}
        )
        self.assertFalse(form.is_valid(), form.errors)
        self.assertIn(
            "Select a valid choice.", form.errors["backing_device"][0]
        )
        self.assertIn(
            "is not one of the available choices.",
            form.errors["backing_device"][0],
        )

    def test_bcache_update_with_boot_disk(self):
        node = factory.make_Node(with_boot_disk=False)
        boot_disk = factory.make_PhysicalBlockDevice(node=node, bootable=True)
        cache_set = factory.make_CacheSet(node=node)
        filesystems = [
            factory.make_Filesystem(
                partition=factory.make_PartitionTable(
                    block_device=factory.make_PhysicalBlockDevice(node=node)
                ).add_partition(),
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
            )
        ]
        bcache = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_set=cache_set,
            filesystems=filesystems,
        )
        form = UpdateBcacheForm(
            bcache=bcache, data={"backing_device": boot_disk.id}
        )
        self.assertTrue(form.is_valid(), form.errors)
        bcache = form.save()
        boot_partition = boot_disk.get_partitiontable().partitions.first()
        self.assertEqual(
            boot_partition.get_effective_filesystem(),
            bcache.filesystems.get(fstype=FILESYSTEM_TYPE.BCACHE_BACKING),
        )
