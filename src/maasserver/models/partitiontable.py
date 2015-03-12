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
