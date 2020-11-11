# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
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


from datetime import datetime
from uuid import uuid4

from maasserver.enum import FILESYSTEM_TYPE, PARTITION_TABLE_TYPE
from maasserver.models.partition import (
    MAX_PARTITION_SIZE_FOR_MBR,
    PARTITION_ALIGNMENT_SIZE,
)
from maasserver.models.partitiontable import PARTITION_TABLE_EXTRA_SPACE
from maasserver.utils.converters import round_size_to_nearest_block


def clear_full_storage_configuration(
    node,
    PhysicalBlockDevice,
    VirtualBlockDevice,
    PartitionTable,
    Filesystem,
    FilesystemGroup,
):
    """Clear's the full storage configuration for this node."""
    physical_block_devices = PhysicalBlockDevice.objects.filter(node=node)
    PartitionTable.objects.filter(
        block_device__in=physical_block_devices
    ).delete()
    Filesystem.objects.filter(block_device__in=physical_block_devices).delete()
    for block_device in VirtualBlockDevice.objects.filter(node=node):
        try:
            block_device.filesystem_group.virtual_devices.all().delete()
            block_device.filesystem_group.delete()
        except FilesystemGroup.DoesNotExist:
            # When a filesystem group has multiple virtual block devices
            # it is possible that accessing `filesystem_group` will
            # result in it already being deleted.
            pass


def create_flat_layout(node, boot_disk, PartitionTable, Partition, Filesystem):
    """Create the flat layout for the boot disk."""
    # Create the partition table and root partition.
    now = datetime.now()
    partition_table = PartitionTable.objects.create(
        block_device=boot_disk,
        table_type=PARTITION_TABLE_TYPE.MBR,
        created=now,
        updated=now,
    )
    total_size = 0
    available_size = boot_disk.size - PARTITION_TABLE_EXTRA_SPACE
    partition_size = round_size_to_nearest_block(
        available_size, PARTITION_ALIGNMENT_SIZE, False
    )
    max_mbr_size = round_size_to_nearest_block(
        MAX_PARTITION_SIZE_FOR_MBR, PARTITION_ALIGNMENT_SIZE, False
    )
    if partition_size > max_mbr_size:
        partition_size = max_mbr_size
    available_size -= partition_size
    total_size += partition_size
    root_partition = Partition.objects.create(
        partition_table=partition_table,
        size=partition_size,
        bootable=True,
        created=now,
        updated=now,
        uuid=uuid4(),
    )
    Filesystem.objects.create(
        partition=root_partition,
        fstype=FILESYSTEM_TYPE.EXT4,
        label="root",
        mount_point="/",
        created=now,
        updated=now,
        uuid=uuid4(),
    )
