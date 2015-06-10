# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `BlockDevice`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type

from django.core.exceptions import PermissionDenied
from maasserver.api.support import (
    operation,
    OperationsHandler,
)
from maasserver.api.utils import get_mandatory_param
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPIValidationError,
)
from maasserver.forms import (
    FormatBlockDeviceForm,
    MountBlockDeviceForm,
)
from maasserver.models import (
    BlockDevice,
    Node,
    PhysicalBlockDevice,
)
from piston.utils import rc


DISPLAYED_BLOCKDEVICE_FIELDS = (
    'id',
    'name',
    'type',
    'path',
    'id_path',
    'size',
    'block_size',
    'tags',
    ('filesystem', (
        'fstype',
        'uuid',
        'mount_point',
    )),
)


class BlockDevicesHandler(OperationsHandler):
    """Manage block devices on a node."""
    api_doc_section_name = "Block devices"
    create = replace = update = delete = None
    model = BlockDevice
    fields = DISPLAYED_BLOCKDEVICE_FIELDS

    def read(self, request, system_id):
        """List all block devices belonging to node.

        Returns 404 if the node is not found.
        """
        node = Node.nodes.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.VIEW)
        return node.blockdevice_set.all()


class BlockDeviceHandler(OperationsHandler):
    """Manage a block device on a node."""
    api_doc_section_name = "Block device"
    create = replace = update = None
    model = BlockDevice
    fields = DISPLAYED_BLOCKDEVICE_FIELDS

    def read(self, request, system_id, device_id):
        """Read block device on node.

        Returns 404 if the node or block device is not found.
        """
        return BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NODE_PERMISSION.VIEW)

    def delete(self, request, system_id, device_id):
        """Delete block device on node.

        Returns 404 if the node or block device is not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NODE_PERMISSION.EDIT)
        # Standard user cannot delete a physical block device.
        cannot_delete = (
            not request.user.is_superuser and
            isinstance(device, PhysicalBlockDevice))
        if cannot_delete:
            raise PermissionDenied()
        device.delete()
        return rc.DELETED

    @operation(idempotent=True)
    def add_tag(self, request, system_id, device_id):
        """Add a tag to a BlockDevice.

        :param tag: The tag being added.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NODE_PERMISSION.EDIT)
        # Standard user cannot add a tag to a physical block device.
        cannot_delete = (
            not request.user.is_superuser and
            isinstance(device, PhysicalBlockDevice))
        if cannot_delete:
            raise PermissionDenied()
        device.add_tag(get_mandatory_param(request.GET, 'tag'))
        device.save()
        return device

    @operation(idempotent=True)
    def remove_tag(self, request, system_id, device_id):
        """Remove a tag from a BlockDevice.

        :param tag: The tag being removed.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NODE_PERMISSION.EDIT)
        # Standard user cannot remove a tag from a physical block device.
        cannot_delete = (
            not request.user.is_superuser and
            isinstance(device, PhysicalBlockDevice))
        if cannot_delete:
            raise PermissionDenied()
        device.remove_tag(get_mandatory_param(request.GET, 'tag'))
        device.save()
        return device

    @operation(idempotent=False)
    def format(self, request, system_id, device_id):
        """Format block device with filesystem.

        :param fstype: Type of filesystem.
        :param uuid: UUID of the filesystem.

        Returns 403 when the user doesn't have the ability to format the block
            device.
        Returns 404 if the node or block device is not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NODE_PERMISSION.EDIT)
        form = FormatBlockDeviceForm(device, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def unformat(self, request, system_id, device_id):
        """Unformat block device with filesystem.

        Returns 400 if the block device is not formatted, currently mounted,
            or part of a filesystem group.
        Returns 403 when the user doesn't have the ability to unformat the
            block device.
        Returns 404 if the node or block device is not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NODE_PERMISSION.EDIT)
        filesystem = device.filesystem
        if filesystem is None:
            raise MAASAPIBadRequest("Block device is not formatted.")
        if filesystem.mount_point:
            raise MAASAPIBadRequest(
                "Filesystem is mounted and cannot be unformatted. Unmount the "
                "filesystem before unformatting the block device.")
        if filesystem.filesystem_group is not None:
            raise MAASAPIBadRequest(
                "Filesystem is part of a filesystem group, and cannot be "
                "unformatted. Remove block device from filesystem group "
                "before unformatting the block device.")
        filesystem.delete()
        return device

    @operation(idempotent=False)
    def mount(self, request, system_id, device_id):
        """Mount the filesystem on block device.

        :param mount_point: Path on the filesystem to mount.

        Returns 403 when the user doesn't have the ability to format the block
            device.
        Returns 404 if the node or block device is not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NODE_PERMISSION.EDIT)
        form = MountBlockDeviceForm(device, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def unmount(self, request, system_id, device_id):
        """Unmount the filesystem on block device.

        Returns 400 if the block device is not formatted or not currently
            mounted.
        Returns 403 when the user doesn't have the ability to unformat the
            block device.
        Returns 404 if the node or block device is not found.
        """
        device = BlockDevice.objects.get_block_device_or_404(
            system_id, device_id, request.user, NODE_PERMISSION.EDIT)
        filesystem = device.filesystem
        if filesystem is None:
            raise MAASAPIBadRequest("Block device is not formatted.")
        if not filesystem.mount_point:
            raise MAASAPIBadRequest("Filesystem is already unmounted.")
        filesystem.mount_point = None
        filesystem.save()
        return device
