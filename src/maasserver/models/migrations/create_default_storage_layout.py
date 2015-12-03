# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Migration to create the default storage layout on the boot disk.

WARNING: Although these methods will become obsolete very quickly, they
cannot be removed, since they are used by the
0181_initial_storage_layouts DataMigration. (changing them might also
be futile unless a customer restores from a backup, since any bugs that occur
will have already occurred, and this code will not be executed again.)

Note: Each helper must have its dependencies on any model classes injected,
since the migration environment is a skeletal replication of the 'real'
database model. So each function takes as parameters the model classes it
requires. Importing from the model is not allowed here. (but the unit tests
do it, to ensure that the migrations meet validation requirements.)
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "clear_full_storage_configuration",
    "create_lvm_layout",
]

from datetime import datetime
from uuid import uuid4

from maasserver.enum import (
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    PARTITION_TABLE_TYPE,
)
from maasserver.models.filesystemgroup import LVM_PE_SIZE
from maasserver.models.partition import (
    MAX_PARTITION_SIZE_FOR_MBR,
    MIN_PARTITION_SIZE,
    PARTITION_ALIGNMENT_SIZE,
)
from maasserver.models.partitiontable import PARTITION_TABLE_EXTRA_SPACE
from maasserver.utils.converters import round_size_to_nearest_block


def clear_full_storage_configuration(
        node,
        PhysicalBlockDevice, VirtualBlockDevice,
        PartitionTable, Filesystem, FilesystemGroup):
    """Clear's the full storage configuration for this node."""
    physical_block_devices = PhysicalBlockDevice.objects.filter(node=node)
    PartitionTable.objects.filter(
        block_device__in=physical_block_devices).delete()
    Filesystem.objects.filter(
        block_device__in=physical_block_devices).delete()
    for block_device in VirtualBlockDevice.objects.filter(node=node):
        try:
            block_device.filesystem_group.virtual_devices.all().delete()
            block_device.filesystem_group.delete()
        except FilesystemGroup.DoesNotExist:
            # When a filesystem group has multiple virtual block devices
            # it is possible that accessing `filesystem_group` will
            # result in it already being deleted.
            pass


def create_lvm_layout(
        node, boot_disk,
        PartitionTable, Partition, Filesystem, FilesystemGroup,
        VirtualBlockDevice):
    """Create the lvm layout for the boot disk."""
    # Create the partition table and root partition.
    now = datetime.now()
    partition_table = PartitionTable.objects.create(
        block_device=boot_disk, table_type=PARTITION_TABLE_TYPE.MBR,
        created=now, updated=now)
    total_size = 0
    available_size = boot_disk.size - PARTITION_TABLE_EXTRA_SPACE
    partition_size = round_size_to_nearest_block(
        available_size, PARTITION_ALIGNMENT_SIZE, False)
    max_mbr_size = round_size_to_nearest_block(
        MAX_PARTITION_SIZE_FOR_MBR, PARTITION_ALIGNMENT_SIZE, False)
    if partition_size > max_mbr_size:
        partition_size = max_mbr_size
    available_size -= partition_size
    total_size += partition_size
    root_partition = Partition.objects.create(
        partition_table=partition_table, size=partition_size, bootable=True,
        created=now, updated=now, uuid=uuid4())

    # Add the extra partitions if there is more space.
    partitions = [root_partition]
    while available_size > MIN_PARTITION_SIZE:
        size = round_size_to_nearest_block(
            available_size, PARTITION_ALIGNMENT_SIZE, False)
        if size > max_mbr_size:
            size = max_mbr_size
        partitions.append(
            Partition.objects.create(
                partition_table=partition_table, size=size, bootable=False,
                created=now, updated=now, uuid=uuid4()))
        available_size -= size
        total_size += size

    # Create the volume group and logical volume.
    volume_group = FilesystemGroup.objects.create(
        name="vgroot", group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
        created=now, updated=now, uuid=uuid4())
    for partition in partitions:
        Filesystem.objects.create(
            fstype=FILESYSTEM_TYPE.LVM_PV, partition=partition, uuid=uuid4(),
            filesystem_group=volume_group, created=now, updated=now)
    number_of_extents, _ = divmod(total_size, LVM_PE_SIZE)
    lv_size = (number_of_extents - len(partitions)) * LVM_PE_SIZE
    logical_volume = VirtualBlockDevice.objects.create(
        node=node, name="lvroot", size=lv_size, block_size=4096,
        filesystem_group=volume_group, created=now, updated=now, uuid=uuid4())
    Filesystem.objects.create(
        block_device=logical_volume,
        fstype=FILESYSTEM_TYPE.EXT4,
        label="root",
        mount_point="/",
        created=now,
        updated=now,
        uuid=uuid4())
