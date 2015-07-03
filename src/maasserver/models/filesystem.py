# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a filesystem on a partition or a block device."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'Filesystem',
    ]


from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db.models import (
    CharField,
    ForeignKey,
)
from maasserver import DefaultMeta
from maasserver.enum import (
    FILESYSTEM_TYPE,
    FILESYSTEM_TYPE_CHOICES,
)
from maasserver.models.blockdevice import BlockDevice
from maasserver.models.cleansave import CleanSave
from maasserver.models.filesystemgroup import FilesystemGroup
from maasserver.models.partition import Partition
from maasserver.models.timestampedmodel import TimestampedModel


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

    uuid = CharField(
        max_length=36, unique=True, null=False, blank=False, editable=False)

    fstype = CharField(
        max_length=20, choices=FILESYSTEM_TYPE_CHOICES,
        default=FILESYSTEM_TYPE.EXT4)

    partition = ForeignKey(
        Partition, unique=True, null=True, blank=True)

    block_device = ForeignKey(
        BlockDevice, unique=True, null=True, blank=True)

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

    def save(self, *args, **kwargs):
        if not self.uuid:
            self.uuid = uuid4()
        super(Filesystem, self).save(*args, **kwargs)
