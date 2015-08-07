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

from operator import attrgetter
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import IntegrityError
from django.db.models import (
    BigIntegerField,
    BooleanField,
    CharField,
    ForeignKey,
    Manager,
)
from maasserver import DefaultMeta
from maasserver.enum import PARTITION_TABLE_TYPE
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.converters import (
    human_readable_bytes,
    round_size_to_nearest_block,
)
from maasserver.utils.orm import get_one


MIN_PARTITION_SIZE = MIN_BLOCK_DEVICE_SIZE


class PartitionManager(Manager):
    """Manager for `Partition` class."""

    def get_free_partitions_for_node(self, node):
        """Return `Partition`s for node that have no filesystems or
        partition table."""
        return self.filter(
            partition_table__block_device__node=node, filesystem=None)

    def get_partitions_in_filesystem_group(self, filesystem_group):
        """Return `Partition`s for the belong to the filesystem group."""
        return self.filter(filesystem__filesystem_group=filesystem_group)

    def get_partition_by_id_or_name(
            self, partition_id_or_name, partition_table=None):
        """Return `Partition` based on its ID or name."""
        try:
            partition_id = int(partition_id_or_name)
        except ValueError:
            name_split = partition_id_or_name.split('-part')
            if len(name_split) != 2:
                # Invalid name.
                raise self.model.DoesNotExist()
            device_name, partition_number = name_split
            try:
                partition_number = int(partition_number)
            except ValueError:
                # Invalid partition number.
                raise self.model.DoesNotExist()
            partition = self.get_partition_by_device_name_and_number(
                device_name, partition_number)
            if (partition_table is not None and
                    partition.partition_table_id != partition_table.id):
                # No partition with that name on that partition table.
                raise self.model.DoesNotExist()
            return partition
        kwargs = {
            "id": partition_id,
        }
        if partition_table is not None:
            kwargs["partition_table"] = partition_table
        return self.get(**kwargs)

    def get_partition_by_device_name_and_number(
            self, device_name, partition_number):
        """Return `Partition` for the block device and partition_number."""
        partitions = self.filter(
            partition_table__block_device__name=device_name).prefetch_related(
            'partition_table__partitions').all()
        for partition in partitions:
            if partition.get_partition_number() == partition_number:
                return partition
        raise self.model.DoesNotExist()


class Partition(CleanSave, TimestampedModel):
    """A partition in a partition table.

    :ivar partition_table: `PartitionTable` this partition belongs to.
    :ivar uuid: UUID of the partition if it's part of a GPT partition.
    :ivar size: Size of the partition in bytes.
    :ivar bootable: Whether the partition is set as bootable.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = PartitionManager()

    partition_table = ForeignKey(
        'maasserver.PartitionTable', null=False, blank=False,
        related_name="partitions")

    uuid = CharField(
        max_length=36, unique=True, null=True, blank=True)

    size = BigIntegerField(
        null=False, validators=[MinValueValidator(MIN_PARTITION_SIZE)])

    bootable = BooleanField(default=False)

    @property
    def name(self):
        return self.get_name()

    @property
    def path(self):
        return "%s-part%s" % (
            self.partition_table.block_device.path,
            self.get_partition_number())

    @property
    def type(self):
        """Return the type."""
        return "partition"

    @property
    def filesystem(self):
        """Returns the filesystem that's using this partition."""
        return get_one(self.filesystem_set.all())

    def get_name(self):
        """Return the name of the partition."""
        return "%s-part%s" % (
            self.partition_table.block_device.get_name(),
            self.get_partition_number())

    def get_node(self):
        """`Node` this partition belongs to."""
        return self.partition_table.get_node()

    def get_block_size(self):
        """Block size of partition."""
        return self.partition_table.get_block_size()

    def get_partition_number(self):
        """Return the partition number in the table."""
        # Sort manually instead of with `order_by`, this will prevent django
        # from making a query if the partitions are already cached.
        partitions_in_table = self.partition_table.partitions.all()
        partitions_in_table = sorted(partitions_in_table, key=attrgetter('id'))
        idx = partitions_in_table.index(self)
        if self.partition_table.table_type == PARTITION_TABLE_TYPE.GPT:
            return idx + 1
        elif self.partition_table.table_type == PARTITION_TABLE_TYPE.MBR:
            # If more than 4 partitions then the 4th partition number is
            # skipped because that is used for the extended partition.
            if len(partitions_in_table) > 4 and idx > 2:
                return idx + 2
            else:
                return idx + 1
        else:
            raise ValueError("Unknown partition table type.")

    def save(self, *args, **kwargs):
        """Save partition."""
        if not self.uuid:
            self.uuid = uuid4()
        return super(Partition, self).save(*args, **kwargs)

    def clean(self, *args, **kwargs):
        self._round_size()
        self._validate_enough_space()
        super(Partition, self).clean(*args, **kwargs)

    def __unicode__(self):
        return "{size} partition on {bd}".format(
            size=human_readable_bytes(self.size),
            bd=self.partition_table.block_device.__unicode__())

    def _round_size(self):
        """Round the size of this partition to the nearest block."""
        if self.size is not None and self.partition_table is not None:
            self.size = round_size_to_nearest_block(
                self.size, self.partition_table.get_block_size())

    def _validate_enough_space(self):
        """Validate that the partition table has enough space for this
        partition."""
        if self.partition_table is not None:
            available_size = self.partition_table.get_available_size(
                ignore_partitions=[self])
            if available_size < self.size:
                # Adjust the size by one block down to see if it will fit.
                # This is a nice to have because we don't want to block
                # users from saving partitions if the size is only a one
                # block off.
                adjusted_size = self.size - self.get_block_size()
                if available_size < adjusted_size:
                    if self.id is not None:
                        raise ValidationError({
                            "size": [
                                "Partition %s cannot be resized to fit on the "
                                "block device; not enough free space." % (
                                    self.id)],
                            })
                    else:
                        raise ValidationError({
                            "size": [
                                "Partition cannot be saved; not enough free "
                                "space on the block device."],
                            })
                else:
                    self.size = adjusted_size

    def add_filesystem(
            self, uuid=None, fstype=None, label=None, create_params=None,
            mount_point=None, mount_params=None):
        """Creates a filesystem directly on this partition and returns it."""
        # Avoid a circular import.
        from maasserver.models.filesystem import Filesystem
        return Filesystem.objects.create(
            uuid=uuid, fstype=fstype, label=label,
            create_params=create_params, mount_point=mount_point,
            mount_params=mount_params, partition=self)

    def remove_filesystem(self):
        """Deletes any filesystem on this partition. Do nothing if there is no
        filesystem on this partition."""
        filesystem = self.filesystem
        if filesystem is None:
            return
        elif filesystem.filesystem_group is not None:
            raise IntegrityError('This filesystem is in use by a volume group')
        elif filesystem.mount_point is not None:
            raise IntegrityError('This filesystem is in use ')
        else:
            self.filesystem.delete()

    def delete(self):
        """Delete the partition.

        If this partition is part of a filesystem group then it cannot be
        deleted.
        """
        if self.filesystem is not None:
            filesystem_group = self.filesystem.filesystem_group
            if filesystem_group is not None:
                raise ValidationError(
                    "Cannot delete partition because its part of "
                    "a %s." % filesystem_group.get_nice_name())
        super(Partition, self).delete()
