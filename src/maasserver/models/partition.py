# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a partition in a partition table."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'Partition',
    ]

from uuid import uuid4

from django.db.models import (
    BigIntegerField,
    BooleanField,
    CharField,
    ForeignKey,
)
from maasserver import DefaultMeta
from maasserver.enum import PARTITION_TABLE_TYPE
from maasserver.models.cleansave import CleanSave
from maasserver.models.partitiontable import PartitionTable
from maasserver.models.timestampedmodel import TimestampedModel


class Partition(CleanSave, TimestampedModel):
    """A partition in a partition table.

    :ivar partition_table: `PartitionTable` this partition belongs to.
    :ivar uuid: UUID of the partition if it's part of a GPT partition.
    :ivar start_offset: Offset in bytes the partition is from the start of
        the disk.
    :ivar size: Size of the partition in bytes.
    :ivar bootable: Whether the partition is set as bootable.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    partition_table = ForeignKey(
        PartitionTable, null=False, blank=False, related_name="partitions")

    uuid = CharField(
        max_length=36, unique=True, null=True, blank=True)

    start_offset = BigIntegerField(null=False)

    size = BigIntegerField(null=False)

    bootable = BooleanField(default=False)

    def get_node(self):
        """`Node` this partition belongs to."""
        return self.partition_table.get_node()

    def get_block_size(self):
        """Block size of partition."""
        return self.partition_table.get_block_size()

    def save(self, *args, **kwargs):
        """Save partition."""
        if (self.partition_table.table_type == PARTITION_TABLE_TYPE.GPT and
                not self.uuid):
            # Partition is part of a GPT partition table and doesn't have
            # a UUID set. Set the UUID so MAAS will know the UUID of the
            # partition on the created machine.
            self.uuid = uuid4()
        return super(Partition, self).save(*args, **kwargs)
