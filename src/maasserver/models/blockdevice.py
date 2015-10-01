# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a nodes block device."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'BlockDevice',
    ]

from collections import Iterable

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.core.validators import MinValueValidator
from django.db.models import (
    BigIntegerField,
    CharField,
    FilePathField,
    ForeignKey,
    IntegerField,
    Manager,
)
from django.db.models.signals import (
    post_delete,
    post_save,
)
from django.dispatch import receiver
from django.shortcuts import get_object_or_404
from djorm_pgarray.fields import ArrayField
from maasserver import DefaultMeta
from maasserver.enum import FILESYSTEM_GROUP_TYPE
from maasserver.models.cleansave import CleanSave
from maasserver.models.filesystemgroup import FilesystemGroup
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.converters import human_readable_bytes
from maasserver.utils.orm import psql_array
from maasserver.utils.storage import (
    get_effective_filesystem,
    used_for,
)


MIN_BLOCK_DEVICE_SIZE = 2 * 1024 * 1024  # 2MiB
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
        kwargs = {
            "node__system_id": system_id,
        }
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
        return self.filter(node=node, partitiontable=None, filesystem=None)

    def get_block_devices_in_filesystem_group(self, filesystem_group):
        """Return `BlockDevice`s for the belong to the filesystem group."""
        return self.filter(filesystem__filesystem_group=filesystem_group)

    def filter_by_tags(self, tags):
        if not isinstance(tags, list):
            if isinstance(tags, unicode) or not isinstance(tags, Iterable):
                raise ValueError("Requires iterable object to filter.")
            tags = list(tags)
        tags_where, tags_params = psql_array(tags, sql_type="text")
        where_contains = (
            '"maasserver_blockdevice"."tags"::text[] @> %s' % tags_where)
        return self.extra(
            where=[where_contains], params=tags_params)


class BlockDevice(CleanSave, TimestampedModel):
    """A block device attached to a node."""

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""
        unique_together = ("node", "name")
        ordering = ["id"]

    objects = BlockDeviceManager()

    node = ForeignKey('Node', null=False, editable=False)

    name = CharField(
        max_length=255, blank=False,
        help_text="Name of block device. (e.g. sda)")

    id_path = FilePathField(
        blank=True, null=True,
        help_text="Path of by-id alias. (e.g. /dev/disk/by-id/wwn-0x50004...)")

    size = BigIntegerField(
        blank=False, null=False,
        validators=[MinValueValidator(MIN_BLOCK_DEVICE_SIZE)],
        help_text="Size of block device in bytes.")

    block_size = IntegerField(
        blank=False, null=False,
        validators=[MinValueValidator(MIN_BLOCK_DEVICE_BLOCK_SIZE)],
        help_text="Size of a block on the device in bytes.")

    tags = ArrayField(
        dbtype="text", blank=True, null=False, default=[])

    def get_name(self):
        """Return the name.

        This exists so `VirtualBlockDevice` can override this method.
        """
        return self.name

    def get_node(self):
        """Return the name."""
        return self.node

    @property
    def path(self):
        # Path is persistent and set by curtin on deploy.
        return "/dev/disk/by-dname/%s" % self.get_name()

    @property
    def type(self):
        # Circular imports, since PhysicalBlockDevice and VirtualBlockDevice
        # extend from this calss.
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
                "PhysicalBlockDevice or VirtualBlockDevice")

    @property
    def actual_instance(self):
        """Return the instance as its correct type.

        By default all references from Django will be to `BlockDevice`, when
        the native type `PhysicalBlockDevice` or `VirtualBlockDevice` is needed
        use this property to get its actual instance.
        """
        # Circular imports, since PhysicalBlockDevice and VirtualBlockDevice
        # extend from this calss.
        from maasserver.models.physicalblockdevice import PhysicalBlockDevice
        from maasserver.models.virtualblockdevice import VirtualBlockDevice
        if (isinstance(self, PhysicalBlockDevice) or
                isinstance(self, VirtualBlockDevice)):
            return self
        try:
            return self.physicalblockdevice
        except PhysicalBlockDevice.DoesNotExist:
            try:
                return self.virtualblockdevice
            except VirtualBlockDevice.DoesNotExist:
                pass
        return self

    def get_effective_filesystem(self):
        """Return the filesystem that is placed on this block device."""
        return get_effective_filesystem(self)

    def get_partitiontable(self):
        """Returns this device's partition table (or None, if none exists."""
        return self.partitiontable_set.first()

    def display_size(self, include_suffix=True):
        return human_readable_bytes(self.size, include_suffix=include_suffix)

    def add_tag(self, tag):
        """Add tag to block device."""
        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag):
        """Remove tag from block device."""
        if tag in self.tags:
            self.tags.remove(tag)

    @property
    def used_size(self):
        """Return the used size on the block device."""
        filesystem = self.get_effective_filesystem()
        if filesystem is not None:
            return self.size
        partitiontable = self.get_partitiontable()
        if partitiontable is not None:
            return partitiontable.get_used_size()
        return 0

    @property
    def available_size(self):
        """Return the available size on the block device."""
        return self.size - self.used_size

    @property
    def used_for(self):
        """Return what the block device is being used for."""
        return used_for(self)

    def __unicode__(self):
        return '{size} attached to {node}'.format(
            size=human_readable_bytes(self.size),
            node=self.node)

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
                    "a %s." % filesystem_group.get_nice_name())
        super(BlockDevice, self).delete()


@receiver(post_save)
def update_filesystem_group(sender, instance, **kwargs):
    """Update all filesystem groups that this block device belongs to.
    Also if a virtual block device name has does not equal its filesystem
    group then update its filesystem group with the new name.
    """
    # Circular imports.
    from maasserver.models.virtualblockdevice import VirtualBlockDevice
    if isinstance(instance, BlockDevice):
        block_device = instance.actual_instance
        groups = FilesystemGroup.objects.filter_by_block_device(block_device)
        for group in groups:
            # Re-save the group so the VirtualBlockDevice is updated. This will
            # fix the size of the VirtualBlockDevice if the size of this block
            # device has changed.
            group.save()

        if isinstance(block_device, VirtualBlockDevice):
            # When not LVM the name of the block devices should stay in sync
            # with the name of the filesystem group.
            filesystem_group = block_device.filesystem_group
            if (filesystem_group.group_type != FILESYSTEM_GROUP_TYPE.LVM_VG and
                    filesystem_group.name != block_device.name):
                filesystem_group.name = block_device.name
                filesystem_group.save()


@receiver(post_delete)
def delete_filesystem_group(sender, instance, **kwargs):
    """Delete the attached `FilesystemGroup` when it is not LVM."""
    # Circular imports.
    from maasserver.models.virtualblockdevice import VirtualBlockDevice
    if isinstance(instance, BlockDevice):
        block_device = instance.actual_instance
        if isinstance(block_device, VirtualBlockDevice):
            try:
                filesystem_group = block_device.filesystem_group
            except FilesystemGroup.DoesNotExist:
                # Possible that it was deleted the same time this
                # virtual block device was deleted.
                return
            not_volume_group = (
                filesystem_group.group_type != FILESYSTEM_GROUP_TYPE.LVM_VG)
            if filesystem_group.id is not None and not_volume_group:
                filesystem_group.delete()
