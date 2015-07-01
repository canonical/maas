# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a nodes virtual block device."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'VirtualBlockDevice',
    ]

from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db.models import (
    CharField,
    ForeignKey,
)
from maasserver import DefaultMeta
from maasserver.models.blockdevice import (
    BlockDevice,
    BlockDeviceManager,
)
from maasserver.models.filesystemgroup import FilesystemGroup
from maasserver.models.node import Node
from maasserver.utils.converters import human_readable_bytes


class VirtualBlockDeviceManager(BlockDeviceManager):
    """Manager for `VirtualBlockDevice` class."""


class VirtualBlockDevice(BlockDevice):
    """A virtual block device attached to a node."""

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = VirtualBlockDeviceManager()

    uuid = CharField(
        max_length=36, unique=True, null=False, blank=False, editable=False)

    filesystem_group = ForeignKey(
        FilesystemGroup, null=False, blank=False,
        related_name="virtual_devices")

    def clean(self, *args, **kwargs):
        super(VirtualBlockDevice, self).clean(*args, **kwargs)

        # First time called the node might not be set, so we handle the
        # DoesNotExist exception accordingly.
        try:
            node = self.node
        except Node.DoesNotExist:
            # Set the node of this virtual block device, to the same node from
            # the attached filesystem group.
            fsgroup_node = self.filesystem_group.get_node()
            if fsgroup_node is not None:
                self.node = fsgroup_node
        else:
            # The node on the virtual block device must be the same node from
            # the attached filesystem group.
            if node != self.filesystem_group.get_node():
                raise ValidationError(
                    "Node must be the same node as the filesystem_group.")

        # Check if the size of this is not larger than the free size of
        # its filesystem group.
        if self.size > self.filesystem_group.get_lvm_free_space():
            raise ValidationError(
                "There is not enough free space (%s) "
                "on filesystem_group %s." % (human_readable_bytes(self.size),
                                             self.filesystem_group.name))

    def save(self, *args, **kwargs):
        if not self.uuid:
            self.uuid = uuid4()
        return super(VirtualBlockDevice, self).save(*args, **kwargs)
