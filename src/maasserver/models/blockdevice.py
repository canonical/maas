# Copyright 2014-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a nodes block device."""

from collections.abc import Iterable
from contextlib import suppress
import re
import string

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import MinValueValidator
from django.db.models import (
    BigIntegerField,
    CASCADE,
    CharField,
    ForeignKey,
    IntegerField,
    Manager,
    TextField,
)
from django.shortcuts import get_object_or_404

from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.converters import human_readable_bytes
from maasserver.utils.orm import psql_array
from maasserver.utils.storage import get_effective_filesystem, used_for

MIN_BLOCK_DEVICE_SIZE = 4 * 1024 * 1024  # 4MiB
MIN_BLOCK_DEVICE_BLOCK_SIZE = 512  # A ProDOS block


class BlockDeviceManager(Manager):
    """Manager for `BlockDevice` class."""

    def get_block_device_or_404(self, system_id, blockdevice_id, user, perm):
        """Fetch a `BlockDevice` by its `Node`'s system_id and its id.  Raise
        exceptions if no `BlockDevice` with this id exist, if the `Node` with
        system_id doesn't exist, if the `BlockDevice` doesn't exist on the
        `Node`, or if the provided user has not the required permission on
        this `Node` and `BlockDevice`.

        :param system_id: The system_id.
        :type system_id: string
        :param blockdevice_id: The blockdevice_id.
        :type blockdevice_id: int
        :param user: The user that should be used in the permission check.
        :type user: django.contrib.auth.models.User
        :param perm: The permission to assert that the user has on the node.
        :type perm: unicode
        :raises: django.http.Http404_,
            :class:`maasserver.exceptions.PermissionDenied`.

        .. _django.http.Http404: https://
           docs.djangoproject.com/en/dev/topics/http/views/
           #the-http404-exception
        """
        kwargs = {"node_config__node__system_id": system_id}
        try:
            blockdevice_id = int(blockdevice_id)
        except ValueError:
            # Not an integer, we will use the name of the device instead.
            kwargs["name"] = blockdevice_id
        else:
            # It is an integer use it for the block device id.
            kwargs["id"] = blockdevice_id
        block_device = get_object_or_404(BlockDevice, **kwargs)
        block_device = block_device.actual_instance
        if user.has_perm(perm, block_device):
            return block_device
        else:
            raise PermissionDenied()

    def get_free_block_devices_for_node(self, node):
        """Return `BlockDevice`s for node that have no filesystems or
        partition table."""
        return self.filter(
            node_config=node.current_config,
            partitiontable=None,
            filesystem=None,
        )

    def get_block_devices_in_filesystem_group(self, filesystem_group):
        """Return `BlockDevice`s for the belong to the filesystem group."""
        return self.filter(filesystem__filesystem_group=filesystem_group)

    def filter_by_tags(self, tags):
        if not isinstance(tags, list):
            if isinstance(tags, str) or not isinstance(tags, Iterable):
                raise ValueError("Requires iterable object to filter.")
            tags = list(tags)
        tags_where, tags_params = psql_array(tags, sql_type="text")
        where_contains = (
            '"maasserver_blockdevice"."tags"::text[] @> %s' % tags_where
        )
        return self.extra(where=[where_contains], params=tags_params)


class BlockDevice(CleanSave, TimestampedModel):
    """A block device attached to a node."""

    class Meta:
        unique_together = ("node_config", "name")
        ordering = ["id"]

    objects = BlockDeviceManager()

    node_config = ForeignKey("NodeConfig", on_delete=CASCADE)

    name = CharField(
        max_length=255,
        blank=False,
        help_text="Name of block device. (e.g. sda)",
    )

    id_path = CharField(
        blank=True,
        null=True,
        max_length=4096,
        help_text="Path of by-id alias. (e.g. /dev/disk/by-id/wwn-0x50004...)",
    )

    size = BigIntegerField(
        blank=False,
        null=False,
        validators=[MinValueValidator(MIN_BLOCK_DEVICE_SIZE)],
        help_text="Size of block device in bytes.",
    )

    block_size = IntegerField(
        blank=False,
        null=False,
        validators=[MinValueValidator(MIN_BLOCK_DEVICE_BLOCK_SIZE)],
        help_text="Size of a block on the device in bytes.",
    )

    tags = ArrayField(TextField(), blank=True, null=True, default=list)

    def get_name(self):
        """Return the name.

        This exists so `VirtualBlockDevice` can override this method.
        """
        return self.name

    def get_node(self):
        """Return the node for the device."""
        return self.node_config.node

    @property
    def path(self):
        # Path is persistent and set by curtin on deploy.
        return f"/dev/disk/by-dname/{self.get_name()}"

    @property
    def type(self):
        from maasserver.models.physicalblockdevice import PhysicalBlockDevice
        from maasserver.models.virtualblockdevice import VirtualBlockDevice

        actual_instance = self.actual_instance
        if isinstance(actual_instance, PhysicalBlockDevice):
            return "physical"
        elif isinstance(actual_instance, VirtualBlockDevice):
            return "virtual"
        else:
            raise ValueError(
                "BlockDevice is not a subclass of "
                "PhysicalBlockDevice or VirtualBlockDevice"
            )

    @property
    def actual_instance(self):
        """Return the instance as its correct type.

        By default all references from Django will be to `BlockDevice`, when
        the native type PhysicalBlockDevice` or `VirtualBlockDevice` is needed
        use this property to get its actual instance.

        """
        from maasserver.models.physicalblockdevice import PhysicalBlockDevice
        from maasserver.models.virtualblockdevice import VirtualBlockDevice

        if isinstance(self, (PhysicalBlockDevice, VirtualBlockDevice)):
            return self
        with suppress(PhysicalBlockDevice.DoesNotExist):
            return self.physicalblockdevice
        with suppress(VirtualBlockDevice.DoesNotExist):
            return self.virtualblockdevice
        return self

    def get_effective_filesystem(self):
        """Return the filesystem that is placed on this block device."""
        return get_effective_filesystem(self)

    def get_partitiontable(self):
        """Returns this device's partition table (or None, if none exists."""
        if self.pk is None:
            return None
        try:
            return list(self.partitiontable_set.all())[0]
        except IndexError:
            return None

    def display_size(self, include_suffix=True):
        return human_readable_bytes(self.size, include_suffix=include_suffix)

    def add_tag(self, tag):
        """Add tag to block device."""
        if tag not in self.tags:
            self.tags = self.tags + [tag]

    def remove_tag(self, tag):
        """Remove tag from block device."""
        if tag in self.tags:
            tags = self.tags.copy()
            tags.remove(tag)
            self.tags = tags

    @property
    def used_size(self):
        """Return the used size on the block device."""
        return self.get_used_size()

    @property
    def available_size(self):
        """Return the available size on the block device."""
        return self.get_available_size()

    @property
    def used_for(self):
        """Return what the block device is being used for."""
        return used_for(self)

    def serialize(self):
        """Serialize the model so it can be detected outside of MAAS."""
        return {
            "id": self.id,
            "name": self.name,
            "id_path": self.id_path,
        }

    def __str__(self):
        return "{size} attached to {node}".format(
            size=human_readable_bytes(self.size), node=self.get_node()
        )

    def get_block_size(self):
        """Return the block size for the block device."""
        return self.block_size

    def get_used_size(self):
        """Return the used size on the block device."""
        filesystem = self.get_effective_filesystem()
        if filesystem is not None:
            return self.size
        partitiontable = self.get_partitiontable()
        if partitiontable is not None:
            return partitiontable.get_used_size()
        return 0

    def get_available_size(self):
        """Return the available size on the block device."""
        filesystem = self.get_effective_filesystem()
        if filesystem is not None:
            return 0

        partitiontable = self.get_partitiontable()
        if partitiontable is None:
            # if there's no partition table, create one without saving it, for
            # the purpose of calculating the availble size for a partition
            # (thus excluding the space used by the table itself).
            from maasserver.models.partitiontable import PartitionTable

            partitiontable = PartitionTable(block_device=self)

        return partitiontable.get_available_size()

    def is_boot_disk(self):
        """Return true if block device is the boot disk."""
        boot_disk = self.get_node().get_boot_disk()
        return boot_disk.id == self.id if boot_disk else False

    def create_partition(self):
        """Creates a partition that uses the whole disk."""
        if self.get_partitiontable() is not None:
            raise ValueError(
                "Cannot call create_partition_if_boot_disk when a "
                "partition table already exists on the block device."
            )
        # Circular imports.
        from maasserver.models.partitiontable import PartitionTable

        partition_table = PartitionTable.objects.create(block_device=self)
        return partition_table.add_partition()

    def create_partition_if_boot_disk(self):
        """Creates a partition that uses the whole disk if this block device
        is the boot disk."""
        if self.is_boot_disk():
            return self.create_partition()
        else:
            return None

    def delete(self):
        """Delete the block device.

        If this block device is part of a filesystem group then it cannot be
        deleted.
        """
        filesystem = self.get_effective_filesystem()
        if filesystem is not None:
            filesystem_group = filesystem.filesystem_group
            if filesystem_group is not None:
                raise ValidationError(
                    "Cannot delete block device because its part of "
                    "a %s." % filesystem_group.get_nice_name()
                )
        super().delete()

    @staticmethod
    def _get_block_name_from_idx(idx, prefix="sd"):
        """Calculate a block name based on the `idx`.

        Drive#  Name
        0       sda
        25      sdz
        26      sdaa
        27      sdab
        51      sdaz
        52      sdba
        53      sdbb
        701     sdzz
        702     sdaaa
        703     sdaab
        18277   sdzzz
        """
        name = ""
        while idx >= 0:
            name = string.ascii_lowercase[idx % 26] + name
            idx = (idx // 26) - 1
        return prefix + name

    @staticmethod
    def _get_idx_from_block_name(name, prefix="sd"):
        """Calculate a idx based on `name`.

        Name   Drive#
        sda    0
        sdz    25
        sdaa   26
        sdab   27
        sdaz   51
        sdba   52
        sdbb   53
        sdzz   701
        sdaaa  702
        sdaab  703
        sdzzz  18277
        """
        match = re.match("%s([a-z]+)" % prefix, name)
        if match is None:
            return None
        else:
            idx = 0
            suffix = match.group(1)
            for col, char in enumerate(reversed(suffix)):
                digit = ord(char) + (0 if col == 0 else 1) - ord("a")
                idx += digit * (26**col)
            return idx
