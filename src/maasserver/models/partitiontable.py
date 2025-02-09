# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a block devices partition table."""

from django.core.exceptions import ValidationError
from django.db.models import CASCADE, CharField, ForeignKey

from maasserver.enum import PARTITION_TABLE_TYPE, PARTITION_TABLE_TYPE_CHOICES
from maasserver.models.blockdevice import BlockDevice
from maasserver.models.cleansave import CleanSave
from maasserver.models.partition import (
    get_max_mbr_partition_size,
    Partition,
    PARTITION_ALIGNMENT_SIZE,
)
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.converters import round_size_to_nearest_block

# The first 2MiB of the device are used by the partition table and grub. We'll
# reserve the first 4MiB to make sure all partitions stay aligned to 4MB across
# the device.
INITIAL_PARTITION_OFFSET = 4 * 1024 * 1024

# An additional 1MiB of space is left open at the end of the disk to allow for
# the extra MBR table.
END_OF_PARTITION_TABLE_SPACE = 1 * 1024 * 1024

# The amount of extra space a partition table will use.
PARTITION_TABLE_EXTRA_SPACE = (
    INITIAL_PARTITION_OFFSET + END_OF_PARTITION_TABLE_SPACE
)

# The amount of space required to be reserved for the prep partition. Prep
# partition is required by all ppc64el architectures. Because of the way the
# system boots it requires that a 8MiB prep partition exist with grub installed
# on that partition. Without this partition the installation of grub will fail
# on ppc64el and will fail to boot.
PREP_PARTITION_SIZE = 8 * 1024 * 1024  # 8MiB

# The amount of space required to be reserved for the bios_grub partition.
# bios_grub partition is required on amd64 architectures when grub is used
# on the boot disk with GPT.
BIOS_GRUB_PARTITION_SIZE = 1 * 1024 * 1024  # 1MiB


class PartitionTable(CleanSave, TimestampedModel):
    """A partition table on a block device.

    :ivar table_type: Type of partition table.
    :ivar block_device: `BlockDevice` this partition table belongs to.
    """

    table_type = CharField(
        max_length=20,
        choices=PARTITION_TABLE_TYPE_CHOICES,
        default=PARTITION_TABLE_TYPE.GPT,
    )

    block_device = ForeignKey(
        BlockDevice, null=False, blank=False, on_delete=CASCADE
    )

    def get_node(self):
        """`Node` this partition belongs to."""
        return self.block_device.get_node()

    def get_size(self):
        """Total usable size of partition table."""
        return round_size_to_nearest_block(
            self.block_device.size - self.get_overhead_size(),
            PARTITION_ALIGNMENT_SIZE,
            False,
        )

    def get_block_size(self):
        """Block size of partition table."""
        return self.block_device.block_size

    def get_overhead_size(self):
        """Return the total amount of extra space this partition table
        requires."""
        extra_space = PARTITION_TABLE_EXTRA_SPACE
        node_arch, _ = self.get_node().split_arch()
        if node_arch == "ppc64el":
            extra_space += PREP_PARTITION_SIZE
        elif (
            node_arch == "amd64" and self.get_node().bios_boot_method != "uefi"
        ):
            extra_space += BIOS_GRUB_PARTITION_SIZE
        return extra_space

    def get_used_size(self, ignore_partitions=None):
        """Return the used size of partitions on the table."""
        if ignore_partitions is None:
            ignore_partitions = []
        if self.pk is None:
            return self.get_overhead_size()
        ignore_ids = [
            partition.id
            for partition in ignore_partitions
            if partition.id is not None
        ]
        used_size = sum(
            partition.size
            for partition in self.partitions.all()
            if partition.id not in ignore_ids
        )
        # The extra space taken by the partition table header is used space.
        return used_size + self.get_overhead_size()

    def get_available_size(self, ignore_partitions=None):
        """Return the remaining size available for partitions."""
        if ignore_partitions is None:
            ignore_partitions = []
        used_size = self.get_used_size(ignore_partitions=ignore_partitions)
        # Only report 'alignable' space as available for new partitions
        return round_size_to_nearest_block(
            self.block_device.size - used_size, PARTITION_ALIGNMENT_SIZE, False
        )

    def add_partition(self, size=None, bootable=False, uuid=None):
        """Adds a partition to this partition table, returns the added
        partition.

        If size is omitted, the partition will extend to the end of the device.

        All partition sizes will be aligned down to PARTITION_ALIGNMENT_SIZE.
        """
        if size is None:
            size = self.get_available_size()
            if self.table_type == PARTITION_TABLE_TYPE.MBR:
                size = min(size, get_max_mbr_partition_size())
        size = round_size_to_nearest_block(
            size, PARTITION_ALIGNMENT_SIZE, False
        )
        return Partition.objects.create(
            partition_table=self, size=size, uuid=uuid, bootable=bootable
        )

    def delete_partition(self, partition):
        if partition.partition_table_id != self.id:
            raise ValidationError(
                "Partition doesn't belong to the partition table"
            )
        index = partition.index
        partition.delete()
        if self.pk is not None:
            # renumber partitions
            for partition in self.partitions.filter(index__gt=index).order_by(
                "index"
            ):
                partition.index -= 1
                partition.save()

    def __str__(self):
        return f"Partition table for {self.block_device}"

    def clean(self, *args, **kwargs):
        super().clean(*args, **kwargs)
        # Circular imports.
        from maasserver.models.virtualblockdevice import VirtualBlockDevice

        # Cannot place a partition table on a logical volume.
        if self.block_device is not None:
            block_device = self.block_device.actual_instance
            if isinstance(block_device, VirtualBlockDevice):
                if block_device.filesystem_group.is_lvm():
                    raise ValidationError(
                        {
                            "block_device": [
                                "Cannot create a partition table on a "
                                "logical volume."
                            ]
                        }
                    )
                elif block_device.filesystem_group.is_bcache():
                    raise ValidationError(
                        {
                            "block_device": [
                                "Cannot create a partition table on a "
                                "Bcache volume."
                            ]
                        }
                    )
