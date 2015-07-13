# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `RAID`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type

from maasserver.api.support import OperationsHandler
from maasserver.enum import (
    FILESYSTEM_TYPE,
    NODE_PERMISSION,
)
from maasserver.models import (
    Node,
    RAID,
)
from maasserver.utils.converters import human_readable_bytes
from piston.utils import rc


DISPLAYED_RAID_FIELDS = (
    'id',
    'uuid',
    'name',
    'level',
    'devices',
    'spare_devices',
    'size',
    'human_size',
    'virtual_device',
)


class RAIDDevicesHandler(OperationsHandler):
    """Manage RAID devices on a node."""
    api_doc_section_name = "RAID Devices"
    create = update = delete = None
    fields = DISPLAYED_RAID_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ('raid_devices_handler', ["node_system_id"])

    def read(self, request, system_id):
        """List all RAID devices belonging to node.

        Returns 404 if the node is not found.
        """
        node = Node.nodes.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.VIEW)
        return RAID.objects.filter_by_node(node)


class RAIDDeviceHandler(OperationsHandler):
    """Manage RAID device on a node."""
    api_doc_section_name = "RAID Device"
    create = update = None
    model = RAID
    fields = DISPLAYED_RAID_FIELDS

    @classmethod
    def resource_uri(cls, raid=None):
        # See the comment in NodeHandler.resource_uri.
        node_system_id = "node_system_id"
        raid_id = "raid_id"
        if raid is not None:
            raid_id = raid.id
            node = raid.get_node()
            if node is not None:
                node_system_id = node.system_id
        return ('raid_device_handler', (node_system_id, raid_id))

    @classmethod
    def level(cls, raid):
        """Return the level of RAID for device."""
        # group_type holds the raid level, we just expose it over the API
        # as level.
        return raid.group_type

    @classmethod
    def size(cls, raid):
        return raid.get_size()

    @classmethod
    def human_size(cls, raid):
        return human_readable_bytes(raid.get_size())

    @classmethod
    def virtual_device(cls, raid):
        """Return the `VirtualBlockDevice` of RAID device."""
        return raid.virtual_device

    @classmethod
    def devices(cls, raid):
        """Return the devices that make up this RAID."""
        return [
            filesystem.get_parent()
            for filesystem in raid.filesystems.filter(
                fstype=FILESYSTEM_TYPE.RAID)
        ]

    @classmethod
    def spare_devices(cls, raid):
        """Return the spare devices in this RAID."""
        return [
            filesystem.get_parent()
            for filesystem in raid.filesystems.filter(
                fstype=FILESYSTEM_TYPE.RAID_SPARE)
        ]

    def read(self, request, system_id, raid_id):
        """Read RAID device on node.

        Returns 404 if the node or RAID is not found.
        """
        return RAID.objects.get_object_or_404(
            system_id, raid_id, request.user, NODE_PERMISSION.VIEW)

    def delete(self, request, system_id, raid_id):
        """Delete RAID on node.

        Returns 404 if the node or RAID is not found.
        """
        raid = RAID.objects.get_object_or_404(
            system_id, raid_id, request.user, NODE_PERMISSION.EDIT)
        raid.delete()
        return rc.DELETED
