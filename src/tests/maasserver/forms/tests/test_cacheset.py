# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for all forms that are used with `CacheSet`."""

from maasserver.forms import CreateCacheSetForm, UpdateCacheSetForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestCreateCacheSetForm(MAASServerTestCase):
    def test_required_fields(self):
        node = factory.make_Node()
        form = CreateCacheSetForm(node=node, data={})

        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            form.errors["__all__"],
            ["Either cache_device or cache_partition must be specified."],
        )

    def test_choices_are_being_populated_correctly(self):
        node = factory.make_Node(with_boot_disk=False)
        # Make 10 block devices.
        bds = [
            factory.make_PhysicalBlockDevice(node=node, bootable=True)
            for _ in range(10)
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
        form = CreateCacheSetForm(node=node, data={})
        self.assertCountEqual(
            block_devices,
            [k for (k, v) in form.fields["cache_device"].choices],
        )
        self.assertCountEqual(
            partition_choices,
            [k for (k, v) in form.fields["cache_partition"].choices],
        )

    def test_cache_set_creation_with_block_device(self):
        node = factory.make_Node()
        cache_device = factory.make_PhysicalBlockDevice(node=node)
        form = CreateCacheSetForm(
            node=node, data={"cache_device": cache_device.id}
        )

        self.assertTrue(form.is_valid(), form.errors)
        cache_set = form.save()
        self.assertEqual(cache_device, cache_set.get_device())

    def test_cache_set_creation_with_boot_disk(self):
        node = factory.make_Node(with_boot_disk=False)
        boot_disk = factory.make_PhysicalBlockDevice(node=node, bootable=True)
        form = CreateCacheSetForm(
            node=node, data={"cache_device": boot_disk.id}
        )

        self.assertTrue(form.is_valid(), form.errors)
        cache_set = form.save()
        boot_partition = boot_disk.get_partitiontable().partitions.first()
        self.assertEqual(boot_partition, cache_set.get_device())

    def test_cache_set_creation_with_partition(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = factory.make_Partition(partition_table=partition_table)
        form = CreateCacheSetForm(
            node=node, data={"cache_partition": partition.id}
        )

        self.assertTrue(form.is_valid(), form.errors)
        cache_set = form.save()
        self.assertEqual(partition, cache_set.get_device())

    def test_bcache_creation_fails_with_both_set(self):
        node = factory.make_Node()
        cache_device = factory.make_PhysicalBlockDevice(node=node)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = factory.make_Partition(partition_table=partition_table)
        form = CreateCacheSetForm(
            node=node,
            data={
                "cache_device": cache_device.id,
                "cache_partition": partition.id,
            },
        )

        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            form.errors["__all__"],
            ["Cannot set both cache_device and cache_partition."],
        )


class TestUpdateCacheSetForm(MAASServerTestCase):
    def test_choices_are_being_populated_correctly(self):
        node = factory.make_Node(with_boot_disk=False)
        # Make 10 block devices.
        bds = [
            factory.make_PhysicalBlockDevice(node=node, bootable=True)
            for _ in range(10)
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
        cache_set = factory.make_CacheSet(block_device=bds[1])
        form = UpdateCacheSetForm(cache_set=cache_set, data={})
        # Should allow all devices and partitions, including the one currently
        # in use on the cache set.
        self.assertCountEqual(
            block_device_choices,
            [k for (k, v) in form.fields["cache_device"].choices],
        )
        self.assertCountEqual(
            partition_choices,
            [k for (k, v) in form.fields["cache_partition"].choices],
        )

    def test_save_updates_the_cache_set_with_block_device(self):
        node = factory.make_Node()
        partition = factory.make_Partition(node=node)
        cache_set = factory.make_CacheSet(partition=partition)
        new_cache_device = factory.make_PhysicalBlockDevice(node=node)
        form = UpdateCacheSetForm(
            cache_set=cache_set, data={"cache_device": new_cache_device.id}
        )
        self.assertTrue(form.is_valid(), form.errors)
        cache_set = form.save()
        self.assertEqual(new_cache_device, cache_set.get_device())
        self.assertIsNone(partition.get_effective_filesystem())

    def test_save_updates_the_cache_set_with_boot_disk(self):
        node = factory.make_Node(with_boot_disk=False)
        boot_disk = factory.make_PhysicalBlockDevice(node=node, bootable=True)
        partition = factory.make_Partition(node=node)
        cache_set = factory.make_CacheSet(partition=partition)
        form = UpdateCacheSetForm(
            cache_set=cache_set, data={"cache_device": boot_disk.id}
        )
        self.assertTrue(form.is_valid(), form.errors)
        cache_set = form.save()
        boot_partition = boot_disk.get_partitiontable().partitions.first()
        self.assertEqual(boot_partition, cache_set.get_device())
        self.assertIsNone(partition.get_effective_filesystem())

    def test_save_updates_the_cache_set_with_partition(self):
        node = factory.make_Node()
        cache_device = factory.make_PhysicalBlockDevice(node=node)
        cache_set = factory.make_CacheSet(block_device=cache_device)
        new_partition = factory.make_Partition(node=node)
        form = UpdateCacheSetForm(
            cache_set=cache_set, data={"cache_partition": new_partition.id}
        )
        self.assertTrue(form.is_valid(), form.errors)
        cache_set = form.save()
        self.assertEqual(new_partition, cache_set.get_device())
        self.assertIsNone(cache_device.get_effective_filesystem())
