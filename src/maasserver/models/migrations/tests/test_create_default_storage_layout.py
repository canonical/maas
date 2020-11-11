# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `0181_initial_storage_layouts` migration.

WARNING: These tests will become obsolete very quickly, as they are testing
migrations against fields that may be removed. When these tests become
obsolete, they should be skipped. The tests should be kept until at least
the next release cycle (through MAAS 1.9) in case any bugs with this migration
occur.
"""


from testtools.matchers import Is, MatchesStructure, Not

from maasserver.enum import FILESYSTEM_GROUP_TYPE, FILESYSTEM_TYPE
from maasserver.models import (
    Filesystem,
    FilesystemGroup,
    Partition,
    PartitionTable,
    PhysicalBlockDevice,
    VirtualBlockDevice,
)
from maasserver.models.migrations.create_default_storage_layout import (
    clear_full_storage_configuration,
    create_flat_layout,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestClearFullStorageConfigration(MAASServerTestCase):
    def test_clears_all_objects(self):
        node = factory.make_Node()
        physical_block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000 ** 3)
            for _ in range(3)
        ]
        filesystem = factory.make_Filesystem(
            block_device=physical_block_devices[0]
        )
        partition_table = factory.make_PartitionTable(
            block_device=physical_block_devices[1]
        )
        partition = factory.make_Partition(partition_table=partition_table)
        fslvm = factory.make_Filesystem(
            block_device=physical_block_devices[2],
            fstype=FILESYSTEM_TYPE.LVM_PV,
        )
        vgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, filesystems=[fslvm]
        )
        vbd1 = factory.make_VirtualBlockDevice(
            filesystem_group=vgroup, size=2 * 1000 ** 3
        )
        vbd2 = factory.make_VirtualBlockDevice(
            filesystem_group=vgroup, size=3 * 1000 ** 3
        )
        filesystem_on_vbd1 = factory.make_Filesystem(
            block_device=vbd1, fstype=FILESYSTEM_TYPE.LVM_PV
        )
        vgroup_on_vgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            filesystems=[filesystem_on_vbd1],
        )
        vbd3_on_vbd1 = factory.make_VirtualBlockDevice(
            filesystem_group=vgroup_on_vgroup, size=1 * 1000 ** 3
        )
        clear_full_storage_configuration(
            node,
            PhysicalBlockDevice=PhysicalBlockDevice,
            VirtualBlockDevice=VirtualBlockDevice,
            PartitionTable=PartitionTable,
            Filesystem=Filesystem,
            FilesystemGroup=FilesystemGroup,
        )
        for pbd in physical_block_devices:
            self.expectThat(
                reload_object(pbd),
                Not(Is(None)),
                "Physical block device should not have been deleted.",
            )
        self.expectThat(
            reload_object(filesystem),
            Is(None),
            "Filesystem should have been removed.",
        )
        self.expectThat(
            reload_object(partition_table),
            Is(None),
            "PartitionTable should have been removed.",
        )
        self.expectThat(
            reload_object(partition),
            Is(None),
            "Partition should have been removed.",
        )
        self.expectThat(
            reload_object(fslvm),
            Is(None),
            "LVM PV Filesystem should have been removed.",
        )
        self.expectThat(
            reload_object(vgroup),
            Is(None),
            "Volume group should have been removed.",
        )
        self.expectThat(
            reload_object(vbd1),
            Is(None),
            "Virtual block device should have been removed.",
        )
        self.expectThat(
            reload_object(vbd2),
            Is(None),
            "Virtual block device should have been removed.",
        )
        self.expectThat(
            reload_object(filesystem_on_vbd1),
            Is(None),
            "Filesystem on virtual block device should have been removed.",
        )
        self.expectThat(
            reload_object(vgroup_on_vgroup),
            Is(None),
            "Volume group on virtual block device should have been removed.",
        )
        self.expectThat(
            reload_object(vbd3_on_vbd1),
            Is(None),
            "Virtual block device on another virtual block device should have "
            "been removed.",
        )


class TestCreateFlatLayout(MAASServerTestCase):
    def test_creates_layout_for_1TiB_disk(self):
        node = factory.make_Node(with_boot_disk=False)
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=1024 ** 4, block_size=512
        )
        create_flat_layout(
            node,
            boot_disk,
            PartitionTable=PartitionTable,
            Partition=Partition,
            Filesystem=Filesystem,
        )

        # Validate the filesystem on the root partition.
        partition_table = boot_disk.get_partitiontable()
        partitions = partition_table.partitions.order_by("id").all()
        root_partition = partitions[0]
        self.assertThat(
            root_partition.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="root", mount_point="/"
            ),
        )
