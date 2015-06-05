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

from django.shortcuts import get_object_or_404
from maasserver.api.support import (
    admin_method,
    operation,
    OperationsHandler,
)
from maasserver.api.utils import get_mandatory_param
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import MAASAPINotFound
from maasserver.models import (
    BlockDevice,
    Node,
)


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
        node = Node.nodes.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.VIEW)
        device = get_object_or_404(BlockDevice, id=device_id)
        if device.node != node:
            raise MAASAPINotFound()
        return device

    @admin_method
    @operation(idempotent=True)
    def add_tag(self, request, system_id, device_id):
        """Add a tag to a BlockDevice.

        :param tag: The tag being added.
        """
        node = Node.nodes.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.ADMIN)
        device = get_object_or_404(BlockDevice, id=device_id)
        if device.node != node:
            raise MAASAPINotFound()
        device.add_tag(get_mandatory_param(request.GET, 'tag'))
        device.save()
        return device

    @admin_method
    @operation(idempotent=True)
    def remove_tag(self, request, system_id, device_id):
        """Remove a tag from a BlockDevice.

        :param tag: The tag being removed.
        """
        node = Node.nodes.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.ADMIN)
        device = get_object_or_404(BlockDevice, id=device_id)
        if device.node != node:
            raise MAASAPINotFound()
        device.remove_tag(get_mandatory_param(request.GET, 'tag'))
        device.save()
        return device
