# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a partition in a partition table."""


from collections.abc import Iterable
from uuid import uuid4

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db.models import (
    BigIntegerField,
    BooleanField,
    CASCADE,
    ForeignKey,
    IntegerField,
    Manager,
    Max,
    TextField,
)
from django.db.models.functions import Coalesce

from maasserver.enum import PARTITION_TABLE_TYPE
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.converters import (
    human_readable_bytes,
    round_size_to_nearest_block,
)
from maasserver.utils.orm import psql_array
from maasserver.utils.storage import get_effective_filesystem, used_for

MAX_PARTITION_SIZE_FOR_MBR = (((2**32) - 1) * 512) - (1024**2)  # 2 TiB
# All partitions are aligned down to 4MiB blocks for performance (lp:1513085)
PARTITION_ALIGNMENT_SIZE = 4 * 1024 * 1024
MIN_PARTITION_SIZE = PARTITION_ALIGNMENT_SIZE


def get_max_mbr_partition_size():
    """Get the maximum size for an MBR partition."""
    return round_size_to_nearest_block(
        MAX_PARTITION_SIZE_FOR_MBR, PARTITION_ALIGNMENT_SIZE, False
    )


class PartitionManager(Manager):
    """Manager for `Partition` class."""

    def get_free_partitions_for_node(self, node):
        """Return `Partition`s for node that have no filesystems or
        partition table."""
        return self.filter(
            partition_table__block_device__node_config=node.current_config,
            filesystem=None,
        )

    def get_partitions_in_filesystem_group(self, filesystem_group):
        """Return `Partition`s for the belong to the filesystem group."""
        return self.filter(filesystem__filesystem_group=filesystem_group)

    def get_partition_by_id_or_name(self, node_config, partition_id_or_name):
        """Return `Partition` based on its ID or name."""

        def criteria_by_id(partition_id):
            try:
                return {"id": int(partition_id)}
            except ValueError:
                return None

        def criteria_by_name(partition_id):
            try:
                device_name, partition_index = partition_id.split("-part", 1)
                return {
                    "partition_table__block_device__name": device_name,
                    "index": int(partition_index),
                }
            except ValueError:
                return None

        criteria = criteria_by_id(partition_id_or_name)
        if not criteria:
            criteria = criteria_by_name(partition_id_or_name)
        if not criteria:
            raise self.model.DoesNotExist()

        return self.get(
            partition_table__block_device__node_config=node_config,
            **criteria,
        )

    def filter_by_tags(self, tags):
        if not isinstance(tags, list):
            if isinstance(tags, str) or not isinstance(tags, Iterable):
                raise TypeError(
                    "`tags` is not iterable, it is: %s" % type(tags).__name__
                )
            tags = list(tags)
        tags_where, tags_params = psql_array(tags, sql_type="text")
        where_contains = (
            '"maasserver_partition"."tags"::text[] @> %s' % tags_where
        )
        return self.extra(where=[where_contains], params=tags_params)


class Partition(CleanSave, TimestampedModel):
    """A partition in a partition table.

    :ivar partition_table: `PartitionTable` this partition belongs to.
    :ivar uuid: UUID of the partition if it's part of a GPT partition.
    :ivar size: Size of the partition in bytes.
    :ivar bootable: Whether the partition is set as bootable.
    """

    objects = PartitionManager()

    partition_table = ForeignKey(
        "maasserver.PartitionTable",
        null=False,
        blank=False,
        related_name="partitions",
        on_delete=CASCADE,
    )

    # the partition number in the partition table
    index = IntegerField()

    uuid = TextField(null=True, blank=True, default=uuid4)

    size = BigIntegerField(
        null=False, validators=[MinValueValidator(MIN_PARTITION_SIZE)]
    )

    bootable = BooleanField(default=False)

    tags = ArrayField(TextField(), blank=True, null=True, default=list)

    class Meta:
        unique_together = ("partition_table", "index")

    @property
    def name(self):
        return self.get_name()

    @property
    def path(self):
        return f"{self.partition_table.block_device.path}-part{self.index}"

    @property
    def type(self):
        """Return the type."""
        return "partition"

    def get_effective_filesystem(self):
        """Return the filesystem that is placed on this partition."""
        return get_effective_filesystem(self)

    def get_name(self):
        """Return the name of the partition."""
        return (
            f"{self.partition_table.block_device.get_name()}-part{self.index}"
        )

    def get_node(self):
        """`Node` this partition belongs to."""
        return self.partition_table.get_node()

    def get_used_size(self):
        """Return the used size for this partition."""
        filesystem = self.get_effective_filesystem()
        if filesystem is not None:
            return self.size
        else:
            return 0

    def get_available_size(self):
        """Return the available size for this partition."""
        return self.size - self.get_used_size()

    @property
    def used_for(self):
        """Return what the block device is being used for."""
        return used_for(self)

    def get_block_size(self):
        """Block size of partition."""
        return self.partition_table.get_block_size()

    def _get_partition_number(self):
        """Return the partition number in the table for a new partition."""
        max_index = self.partition_table.partitions.aggregate(
            max_index=Coalesce(Max("index"), 0)
        )["max_index"]
        ptable_type = self.partition_table.table_type
        index = max_index + 1
        if index == 4 and ptable_type == PARTITION_TABLE_TYPE.MBR:
            # The 4th MBR partition is used for the extended partitions.
            index = 5
        elif index == 1 and ptable_type == PARTITION_TABLE_TYPE.GPT:
            node = self.get_node()
            arch, _ = node.split_arch()
            boot_disk = node.get_boot_disk()
            bios_boot_method = node.get_bios_boot_method()
            block_device = self.partition_table.block_device

            need_prep_partition = (
                arch == "ppc64el" and block_device.id == boot_disk.id
            )
            need_bios_grub = (
                arch == "amd64"
                and bios_boot_method != "uefi"
                and block_device.type == "physical"
            )
            if need_prep_partition or need_bios_grub:
                index = 2
        return index

    def save(self, *args, **kwargs):
        """Save partition."""
        # XXX this is needed because tests pass uuid=None by default
        if not self.uuid:
            self.uuid = uuid4()
        if not self.index:
            self.index = self._get_partition_number()
        return super().save(*args, **kwargs)

    def clean(self, *args, **kwargs):
        self._round_size()
        self._validate_enough_space()
        super().clean(*args, **kwargs)

    def __str__(self):
        return "{size} partition on {bd}".format(
            size=human_readable_bytes(self.size),
            bd=self.partition_table.block_device.__str__(),
        )

    def _round_size(self):
        """Round the size of this partition down for alignment."""
        if self.size is not None and self.partition_table is not None:
            self.size = round_size_to_nearest_block(
                self.size, PARTITION_ALIGNMENT_SIZE, False
            )

    def _validate_enough_space(self):
        """Validate that the partition table has enough space for this
        partition."""
        if self.partition_table is not None:
            available_size = self.partition_table.get_available_size(
                ignore_partitions=[self]
            )
            if available_size < self.size:
                # Adjust the size by one block down to see if it will fit.
                # This is a nice to have because we don't want to block
                # users from saving partitions if the size is only a one
                # block off.
                adjusted_size = self.size - self.get_block_size()
                if available_size < adjusted_size:
                    if self.id is not None:
                        raise ValidationError(
                            {
                                "size": [
                                    "Partition %s cannot be resized to fit on the "
                                    "block device; not enough free space."
                                    % (self.id)
                                ]
                            }
                        )
                    else:
                        raise ValidationError(
                            {
                                "size": [
                                    "Partition cannot be saved; not enough free "
                                    "space on the block device."
                                ]
                            }
                        )
                else:
                    self.size = adjusted_size

            # Check that the size is not larger than MBR allows.
            if (
                self.partition_table.table_type == PARTITION_TABLE_TYPE.MBR
                and self.size > get_max_mbr_partition_size()
            ):
                if self.id is not None:
                    raise ValidationError(
                        {
                            "size": [
                                "Partition %s cannot be resized to fit on the "
                                "block device; size is larger than the MBR "
                                "2TiB maximum." % (self.id)
                            ]
                        }
                    )
                else:
                    raise ValidationError(
                        {
                            "size": [
                                "Partition cannot be saved; size is larger than "
                                "the MBR 2TiB maximum."
                            ]
                        }
                    )

    def is_vmfs_partition(self):
        # Avoid circular imports.
        from maasserver.storage_layouts import (
            VMFS6StorageLayout,
            VMFS7StorageLayout,
        )

        node = self.get_node()
        part_blk_dev_id = self.partition_table.block_device_id
        for layout_class in (VMFS7StorageLayout, VMFS6StorageLayout):
            vmfs_layout = layout_class(node)
            vmfs_bd = vmfs_layout.is_layout()
            if vmfs_bd is None or vmfs_bd.id != part_blk_dev_id:
                continue
            if self.index <= vmfs_layout.last_base_partition_index:
                # A user may apply the VMFS layout and leave space at the end of
                # the disk for additional VMFS datastores. Those partitions may be
                # deleted, the base partitions may not as they are part of the DD.
                return True
        return False

    def delete(self):
        """Delete the partition.

        If this partition is part of a filesystem group then it cannot be
        deleted.
        """
        filesystem = self.get_effective_filesystem()
        if filesystem is not None:
            filesystem_group = filesystem.filesystem_group
            if filesystem_group is not None:
                raise ValidationError(
                    "Cannot delete partition because its part of "
                    "a %s." % filesystem_group.get_nice_name()
                )
        if self.is_vmfs_partition():
            raise ValidationError(
                "VMware ESXi partitions may not be removed. To remove select "
                "a different storage layout."
            )
        super().delete()

    def add_tag(self, tag):
        """Add tag to partition."""
        if tag not in self.tags:
            self.tags = self.tags + [tag]

    def remove_tag(self, tag):
        """Remove tag from partition."""
        if tag in self.tags:
            tags = self.tags.copy()
            tags.remove(tag)
            self.tags = tags
