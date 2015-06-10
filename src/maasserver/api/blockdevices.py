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
