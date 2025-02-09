# Copyright 2015-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a nodes virtual block device."""

from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db.models import CASCADE, ForeignKey, TextField

from maasserver.models.blockdevice import BlockDevice, BlockDeviceManager
from maasserver.models.filesystemgroup import FilesystemGroup
from maasserver.models.partition import PARTITION_ALIGNMENT_SIZE
from maasserver.utils.converters import (
    human_readable_bytes,
    round_size_to_nearest_block,
)
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
                self.filter(filesystem_group=filesystem_group)
            )
            if block_device is None:
                block_device = VirtualBlockDevice(
                    node_config=filesystem_group.get_node().current_config,
                    name=filesystem_group.name,
                    filesystem_group=filesystem_group,
                )
            # Keep the name, size, and block_size in sync with the
            # FilesystemGroup.
            block_device.name = filesystem_group.name
            block_device.size = filesystem_group.get_size()
            block_device.block_size = (
                filesystem_group.get_virtual_block_device_block_size()
            )
            block_device.save()
            return block_device


class VirtualBlockDevice(BlockDevice):
    """A virtual block device attached to a node."""

    objects = VirtualBlockDeviceManager()

    uuid = TextField(default=uuid4)

    filesystem_group = ForeignKey(
        FilesystemGroup,
        related_name="virtual_devices",
        on_delete=CASCADE,
    )

    def get_name(self):
        """Return the name."""
        if self.filesystem_group.is_lvm():
            return f"{self.filesystem_group.name}-{self.name}"
        else:
            return self.name

    def clean(self, *args, **kwargs):
        super().clean(*args, **kwargs)

        if self.node_config != self.filesystem_group.get_node().current_config:
            raise ValidationError(
                "Node config must be the same as the filesystem_group one."
            )

        # Check if the size of this is not larger than the free size of
        # its filesystem group if its lvm.
        if self.filesystem_group.is_lvm():
            # align virtual partition to partition alignment size
            # otherwise on creation it may be rounded up, overfilling group
            self.size = round_size_to_nearest_block(
                self.size, PARTITION_ALIGNMENT_SIZE, False
            )

            if self.size > self.filesystem_group.get_lvm_free_space(
                skip_volumes=[self]
            ):
                raise ValidationError(
                    "There is not enough free space (%s) "
                    "on volume group %s."
                    % (
                        human_readable_bytes(self.size),
                        self.filesystem_group.name,
                    )
                )
        else:
            # If not a volume group the size of the virtual block device
            # must equal the size of the filesystem group.
            assert self.size == self.filesystem_group.get_size()

    def save(self, *args, **kwargs):
        # XXX this is needed because tests pass uuid=None by default
        if not self.uuid:
            self.uuid = uuid4()
        return super().save(*args, **kwargs)

    def get_parents(self):
        """Return the blockdevices and partition which make up this device."""

        def check_fs_group(obj):
            fs = obj.get_effective_filesystem()
            if fs is None:
                return False
            if fs.filesystem_group is not None:
                fs_group = fs.filesystem_group
            elif fs.cache_set is not None:
                # A block device/partition can only have one cache_set
                fs_group = fs.cache_set.filesystemgroup_set.first()
                # bcache devices only show up in cache_set.filesystemgroup_set,
                # not in fs.filesystem_group. However if only a cache_set has
                # been created and not a bcache device
                # cache_set.filesystemgroup_set will be empty.
                if fs_group is None:
                    return False
            else:
                return False

            # whether the device is part of the filesystem group
            return fs_group.virtual_devices.filter(id=self.id).exists()

        parents = []
        # We need to check all of the nodes block devices in case
        # we have nested virtual block devices.
        for block_device in self.node_config.blockdevice_set.all():
            if block_device.id == self.id:
                continue
            if check_fs_group(block_device):
                parents.append(block_device)
            pt = block_device.get_partitiontable()
            if pt is None:
                continue
            for partition in pt.partitions.all():
                if check_fs_group(partition):
                    parents.append(partition)
        return parents
