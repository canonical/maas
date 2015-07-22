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
from maasserver.utils.orm import get_one


class VirtualBlockDeviceManager(BlockDeviceManager):
    """Manager for `VirtualBlockDevice` class."""

    def create_or_update_for(self, filesystem_group):
        """Create or update the `VirtualBlockDevice` that is linked to the
        `filesystem_group`.

        Note: Does nothing for LVM filesystem groups, since users add logical
            volumes to the filesystem groups as `VirtualBlockDevice`s.
        """
        # Do nothing for LVM.
        if filesystem_group.is_lvm():
            return None
        else:
            block_device = get_one(
                self.filter(filesystem_group=filesystem_group))
            if block_device is None:
                block_device = VirtualBlockDevice(
                    node=filesystem_group.get_node(),
                    name=filesystem_group.name,
                    filesystem_group=filesystem_group)
            # Keep the name, size, and block_size in sync with the
            # FilesystemGroup.
            block_device.name = filesystem_group.name
            block_device.size = filesystem_group.get_size()
            block_device.block_size = (
                filesystem_group.get_virtual_block_device_block_size())
            block_device.save()
            return block_device


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

    def get_name(self):
        """Return the name."""
        if self.filesystem_group.is_lvm():
            return "%s-%s" % (self.filesystem_group.name, self.name)
        else:
            return self.name

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
        # its filesystem group if its lvm.
        if (self.filesystem_group.is_lvm() and
                self.size > self.filesystem_group.get_lvm_free_space()):
            raise ValidationError(
                "There is not enough free space (%s) "
                "on volume group %s." % (
                    human_readable_bytes(self.size),
                    self.filesystem_group.name,
                    ))
        elif not self.filesystem_group.is_lvm():
            # If not a volume group the size of the virtual block device
            # must equal the size of the filesystem group.
            assert self.size == self.filesystem_group.get_size()

    def save(self, *args, **kwargs):
        if not self.uuid:
            self.uuid = uuid4()
        return super(VirtualBlockDevice, self).save(*args, **kwargs)
