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

from math import ceil
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import IntegrityError
from django.db.models import (
    BigIntegerField,
    BooleanField,
    CharField,
    ForeignKey,
)
from maasserver import DefaultMeta
from maasserver.enum import PARTITION_TABLE_TYPE
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import get_one


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
        'maasserver.PartitionTable', null=False, blank=False,
        related_name="partitions")

    uuid = CharField(
        max_length=36, unique=True, null=True, blank=True)

    start_offset = BigIntegerField(null=False,
                                   validators=[MinValueValidator(0)])

    size = BigIntegerField(null=False, validators=[MinValueValidator(1)])

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

    def clean(self):
        """Do additional validation and round start_offset and size to block
        boundaries."""

        # Lines start_block and size to block boundaries.
        self.start_offset = self.start_block * self.get_block_size()
        self.size = self.size_blocks * self.get_block_size()

        # Ensure partitions never extend beyond device boundaries
        end = self.start_offset + self.size
        device_size = self.partition_table.block_device.size
        if end > device_size:
            raise ValidationError(
                "Partition (%d-%d) extends %d bytes past the device end (%d)."
                % (self.start_block, self.end_block, end - device_size,
                   device_size))

        # Prevents overlapping partitions.
        for p in self.partition_table.partitions.exclude(id=self.id):
            st, end = p.start_block, p.end_block
            if st <= self.start_block <= end or st <= self.end_block <= end:
                raise ValidationError(
                    "Partition (%d-%d) overlaps with partition %s (%d-%d)." %
                    (self.start_block, self.end_block,
                     p.id, p.start_block, p.end_block))

    @property
    def start_block(self):
        """Returns the first block of this partition."""
        return int(float(self.start_offset) / self.get_block_size())

    @property
    def end_block(self):
        """Returns the last block of this partition."""
        return (self.start_block + self.size_blocks) - 1

    @property
    def size_blocks(self):
        """Returns the size of the partition, in blocks."""
        return int(ceil(float(self.size) / self.get_block_size()))

    @property
    def filesystem(self):
        """Returns the filesystem that's using this partition."""
        return get_one(self.filesystem_set.all())

    def add_filesystem(self, uuid=None, fstype=None, label=None,
                       create_params=None, mount_point=None,
                       mount_params=None):
        """Creates a filesystem directly on this partition and returns it."""

        # Avoid a circular import.
        from maasserver.models.filesystem import Filesystem

        filesystem = Filesystem(uuid=uuid, fstype=fstype, label=label,
                                create_params=create_params,
                                mount_point=mount_point,
                                mount_params=mount_params,
                                partition=self)
        filesystem.save()
        return filesystem

    def remove_filesystem(self):
        """Deletes any filesystem on this partition. Do nothing if there is no
        filesystem on this partition."""

        filesystem = self.filesystem
        if filesystem is None:
            return None
        elif filesystem.filesystem_group is not None:
            raise IntegrityError('This filesystem is in use by a volume group')
        elif filesystem.mount_point is not None:
            raise IntegrityError('This filesystem is in use ')
        else:
            self.filesystem.delete()
