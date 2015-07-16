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
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
)
from django.db import IntegrityError
from django.db.models import (
    BigIntegerField,
    BooleanField,
    CharField,
    ForeignKey,
    IntegerField,
    Manager,
)
from maasserver import DefaultMeta
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.converters import human_readable_bytes
from maasserver.utils.orm import get_one


MIN_PARTITION_SIZE = MIN_BLOCK_DEVICE_SIZE


class PartitionManager(Manager):
    """Manager for `Partition` class."""

    def get_free_partitions_for_node(self, node):
        """Return `Partition`s for node that have no filesystems or
        partition table."""
        return self.filter(
            partition_table__block_device__node=node, filesystem=None)

    def get_next_partition_number_for_table(self, partition_table):
        """Return the next available partition number for the partition
        table."""
        used_partition_numbers = self.filter(
            partition_table=partition_table).order_by(
            'partition_number').values_list('partition_number', flat=True)
        i = 1
        while i in used_partition_numbers:
            i += 1
        return i

    def get_partitions_in_filesystem_group(self, filesystem_group):
        """Return `Partition`s for the belong to the filesystem group."""
        return self.filter(filesystem__filesystem_group=filesystem_group)


class Partition(CleanSave, TimestampedModel):
    """A partition in a partition table.

    :ivar partition_table: `PartitionTable` this partition belongs to.
    :ivar uuid: UUID of the partition if it's part of a GPT partition.
    :ivar start_offset: Offset in bytes the partition is from the start of
        the disk.
    :ivar size: Size of the partition in bytes.
    :ivar bootable: Whether the partition is set as bootable.
    :ivar partition_number: Partition number in the partition table. This is
        only used for GPT partition tables.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""
        unique_together = ("partition_table", "partition_number")

    objects = PartitionManager()

    partition_table = ForeignKey(
        'maasserver.PartitionTable', null=False, blank=False,
        related_name="partitions")

    uuid = CharField(
        max_length=36, unique=True, null=True, blank=True)

    start_offset = BigIntegerField(
        null=False, validators=[MinValueValidator(0)])

    size = BigIntegerField(
        null=False, validators=[MinValueValidator(MIN_PARTITION_SIZE)])

    bootable = BooleanField(default=False)

    partition_number = IntegerField(
        null=False, blank=False,
        validators=[MinValueValidator(1), MaxValueValidator(256)])

    @property
    def name(self):
        return "%s-part%s" % (
            self.partition_table.block_device.name,
            self.get_partition_number())

    @property
    def path(self):
        return "%s-part%s" % (
            self.partition_table.block_device.path,
            self.get_partition_number())

    def get_node(self):
        """`Node` this partition belongs to."""
        return self.partition_table.get_node()

    def get_block_size(self):
        """Block size of partition."""
        return self.partition_table.get_block_size()

    def get_partition_number(self):
        """Return the partition number.

        This changes based on if the partition table this partition belongs to
        is MBR or GPT.
        """
        # Circular imports.
        from maasserver.models.partitiontable import PARTITION_TABLE_TYPE
        if self.partition_table.table_type == PARTITION_TABLE_TYPE.GPT:
            # Partition number for GPT is set on the partition itself, since
            # GPT allows you to create a partition with any number.
            return self.partition_number
        elif self.partition_table.table_type == PARTITION_TABLE_TYPE.MBR:
            # Partition number is based on how it is ordered on the disk. We
            # order the partition number based on the start_offset of each
            # partition. If there is more than 4 partitions partition_number
            # 4 will be skipped as that will become an extended partition.
            all_partition_ids = list(Partition.objects.filter(
                partition_table=self.partition_table).order_by(
                'start_offset').values_list('id', flat=True))
            partitions_count = len(all_partition_ids)
            partition_number = all_partition_ids.index(self.id) + 1
            if partition_number > 3 and partitions_count > 4:
                partition_number += 1
            return partition_number
        else:
            raise ValueError("Unknown partition table type.")

    def save(self, *args, **kwargs):
        """Save partition."""
        if not self.uuid:
            self.uuid = uuid4()
        if self.partition_number is None and self.partition_table is not None:
            self.partition_number = (
                Partition.objects.get_next_partition_number_for_table(
                    self.partition_table))
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

    def __unicode__(self):
        return "{size} partition on {bd}".format(
            size=human_readable_bytes(self.size),
            bd=self.partition_table.block_device.__unicode__())

    @property
    def type(self):
        """Return the type."""
        return "partition"

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

    def add_filesystem(
            self, uuid=None, fstype=None, label=None, create_params=None,
            mount_point=None, mount_params=None):
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
