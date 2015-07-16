# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a block devices partition table."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'PartitionTable',
    ]

from math import ceil

from django.db.models import (
    CharField,
    ForeignKey,
)
from maasserver import DefaultMeta
from maasserver.enum import (
    PARTITION_TABLE_TYPE,
    PARTITION_TABLE_TYPE_CHOICES,
)
from maasserver.models.blockdevice import BlockDevice
from maasserver.models.cleansave import CleanSave
from maasserver.models.partition import Partition
from maasserver.models.timestampedmodel import TimestampedModel


class PartitionTable(CleanSave, TimestampedModel):
    """A partition table on a block device.

    :ivar table_type: Type of partition table.
    :ivar block_device: `BlockDevice` this partition table belongs to.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    table_type = CharField(
        max_length=20, choices=PARTITION_TABLE_TYPE_CHOICES,
        default=PARTITION_TABLE_TYPE.GPT)

    block_device = ForeignKey(
        BlockDevice, null=False, blank=False)

    def get_node(self):
        """`Node` this partition belongs to."""
        return self.block_device.node

    def get_size(self):
        """Size of partition table."""
        return self.block_device.size

    def get_block_size(self):
        """Block size of partition table."""
        return self.block_device.block_size

    def is_region_free(self, start_offset, size):
        """Returns True if no partitions collide with this offset/size"""
        start_block = int(float(start_offset) / self.get_block_size())
        size_blocks = int(ceil(float(size) / self.get_block_size()))
        end_block = (start_block + size_blocks) - 1

        for p in self.partitions.all():
            st, end = p.start_block, p.end_block
            if st <= start_block <= end or st <= end_block <= end:
                return False

        return True

    def add_partition(self, start_offset=None, size=None, uuid=None,
                      bootable=False, partition_number=None):
        """Adds a partition to this partition table, returns the added
        partition.

        If the partition starts in the middle of a block, it'll be created as
        starting in the beginning of the block (done in the Partition model).

        If start_offset is not specified, the partition will be created
        starting on the first block after the last partition.

        If size is omitted, the partition will extend to the end of the device.

        If size is not a multiple of the device's block size, the size will be
        rounded up to the next multiple (done in the Partition model).

        If the provided values conflict with existing partitions, a ValueError
        will be raised.
        """
        if start_offset is None:
            # Place the partition starting at the first available block after
            # the last partition already allocated. If no partition is found,
            # start at block 0.
            try:
                start_offset = self.get_block_size() * \
                    (max([p.end_block for p in self.partitions.all()]) + 1)

            except ValueError:
                # calling max on an empty sequence (no other partitions) causes
                # a ValueError, so we can allocate this one on block 0
                start_offset = 0

        if size is None:
            # Try to extend the partition until the end of the block
            # device. Fail if there is a collision.
            size = self.block_device.size - start_offset

        partition = Partition(partition_table=self, start_offset=start_offset,
                              size=size, uuid=uuid, bootable=bootable,
                              partition_number=partition_number)
        partition.save()
        return partition

    def __unicode__(self):
        return "Partition table for {bd}".format(
            bd=self.block_device.__unicode__())
