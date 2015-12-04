# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a filesystem on a partition or a block device."""

__all__ = [
    'Filesystem',
    ]


from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db.models import (
    BooleanField,
    CharField,
    ForeignKey,
    Manager,
    Q,
)
from maasserver import DefaultMeta
from maasserver.enum import (
    FILESYSTEM_FORMAT_TYPE_CHOICES_DICT,
    FILESYSTEM_TYPE,
    FILESYSTEM_TYPE_CHOICES,
)
from maasserver.models.blockdevice import BlockDevice
from maasserver.models.cacheset import CacheSet
from maasserver.models.cleansave import CleanSave
from maasserver.models.filesystemgroup import FilesystemGroup
from maasserver.models.partition import Partition
from maasserver.models.timestampedmodel import TimestampedModel


class FilesystemManager(Manager):
    """Manager for `Filesystem` class."""

    def filter_by_node(self, node):
        """Return all filesystems on this node."""
        return self.filter(
            Q(block_device__node=node) |
            Q(partition__partition_table__block_device__node=node))


class Filesystem(CleanSave, TimestampedModel):
    """A filesystem on partition or a block device.

    :ivar uuid: UUID of the filesystem.
    :ivar fstype: Type of filesystem. This can even be filesystems that
        cannot be mounted directly, e.g. LVM.
    :ivar partition: `Partition` this filesystem is on. If empty the filesystem
        must be directly on a `BlockDevice`.
    :ivar block_device: `BlockDevice` this filesystem is on. If empty the
        filesystem must be on a `Partition`.
    :ivar filesystem_group: `FilesystemGroup` this filesystem belongs to.
    :ivar create_params: Parameters that can be passed during the `mkfs`
        command when the filesystem is created.
    :ivar mount_point: Path to where this filesystem is mounted on the deployed
        operating system.
    :ivar mount_params: Parameters that are used to mount this filesystem
        on the deployed operating system.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""
        unique_together = (
            ("partition", "acquired"),
            ("block_device", "acquired"),
            )

    objects = FilesystemManager()

    uuid = CharField(
        max_length=36, unique=False, null=False, blank=False, editable=False)

    fstype = CharField(
        max_length=20, choices=FILESYSTEM_TYPE_CHOICES,
        default=FILESYSTEM_TYPE.EXT4)

    partition = ForeignKey(
        Partition, unique=False, null=True, blank=True)

    block_device = ForeignKey(
        BlockDevice, unique=False, null=True, blank=True)

    label = CharField(
        max_length=255, null=True, blank=True)

    filesystem_group = ForeignKey(
        FilesystemGroup, null=True, blank=True, related_name='filesystems')

    create_params = CharField(
        max_length=255, null=True, blank=True)

    mount_point = CharField(
        max_length=255, null=True, blank=True)

    mount_params = CharField(
        max_length=255, null=True, blank=True)

    cache_set = ForeignKey(
        CacheSet, null=True, blank=True, related_name='filesystems')

    # When a node is allocated all Filesystem objects assigned to that node
    # with mountable filesystems will be duplicated with this field set to
    # True. This allows a standard user to change this object as they want
    # and format other free devices. Once the node is released these objects
    # will be delete.
    acquired = BooleanField(default=False)

    def get_node(self):
        """`Node` this filesystem belongs to."""
        if self.partition is not None:
            return self.partition.get_node()
        elif self.block_device is not None:
            return self.block_device.node
        else:
            return None

    def get_size(self):
        """Size of filesystem."""
        if self.partition is not None:
            return self.partition.size
        elif self.block_device is not None:
            return self.block_device.size
        else:
            return 0

    def get_block_size(self):
        """Block size of partition table."""
        if self.partition is not None:
            return self.partition.get_block_size()
        elif self.block_device is not None:
            return self.block_device.block_size
        else:
            return 0

    def get_parent(self):
        """Return linked `BlockDevice` or linked `Partition`."""
        if self.block_device is None:
            return self.partition
        else:
            return self.block_device.actual_instance

    def is_mountable(self):
        """Return True if this is a mountable filesystem."""
        return self.fstype in FILESYSTEM_FORMAT_TYPE_CHOICES_DICT

    def clean(self, *args, **kwargs):
        super(Filesystem, self).clean(*args, **kwargs)

        # You have to specify either a partition or a block device.
        if self.partition is None and self.block_device is None:
            raise ValidationError(
                "One of partition or block_device must be specified.")

        # You can have only one of partition or block device; not both.
        if self.partition is not None and self.block_device is not None:
            raise ValidationError(
                "Only one of partition or block_device can be specified.")

        # If fstype is for a bcache as a cache device it needs to be in a
        # cache_set.
        if (self.fstype == FILESYSTEM_TYPE.BCACHE_CACHE and
                self.cache_set is None):
            raise ValidationError(
                "BCACHE_CACHE must be inside of a cache_set.")

        # You cannot place a filesystem directly on the boot_disk. It requires
        # a partition to be used.
        if self.block_device is not None:
            node = self.block_device.node
            boot_disk = node.get_boot_disk()
            if boot_disk is not None and boot_disk.id == self.block_device.id:
                # This is the boot disk for the node.
                raise ValidationError(
                    "Cannot place filesystem directly on the boot disk. "
                    "Create a partition on the boot disk first and then "
                    "format the partition.")

    def save(self, *args, **kwargs):
        if not self.uuid:
            self.uuid = uuid4()
        super(Filesystem, self).save(*args, **kwargs)
