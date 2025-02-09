# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to block device changes."""

from django.db.models.signals import post_delete, post_save

from maasserver.enum import FILESYSTEM_GROUP_TYPE
from maasserver.models.blockdevice import BlockDevice
from maasserver.models.filesystemgroup import FilesystemGroup
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.virtualblockdevice import VirtualBlockDevice
from maasserver.utils.signals import SignalsManager

signals = SignalsManager()

senders = {BlockDevice, PhysicalBlockDevice, VirtualBlockDevice}


def update_filesystem_group(sender, instance, **kwargs):
    """Update all filesystem groups that this block device belongs to.
    Also if a virtual block device name has does not equal its filesystem
    group then update its filesystem group with the new name.
    """
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
        if (
            filesystem_group.group_type != FILESYSTEM_GROUP_TYPE.LVM_VG
            and filesystem_group.name != block_device.name
        ):
            filesystem_group.name = block_device.name
            filesystem_group.save()


for sender in senders:
    signals.watch(post_save, update_filesystem_group, sender)


def delete_filesystem_group(sender, instance, **kwargs):
    """Delete the attached `FilesystemGroup` when it is not LVM."""
    block_device = instance.actual_instance
    if isinstance(block_device, VirtualBlockDevice):
        try:
            filesystem_group = block_device.filesystem_group
        except FilesystemGroup.DoesNotExist:
            # Possible that it was deleted the same time this
            # virtual block device was deleted.
            return
        not_volume_group = (
            filesystem_group.group_type != FILESYSTEM_GROUP_TYPE.LVM_VG
        )
        if filesystem_group.id is not None and not_volume_group:
            filesystem_group.delete()


for sender in senders:
    signals.watch(post_delete, delete_filesystem_group, sender)


# Enable all signals by default.
signals.enable()
