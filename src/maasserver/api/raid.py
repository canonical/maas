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
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import (
    CreateRaidForm,
    UpdateRaidForm,
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


class RaidsHandler(OperationsHandler):
    """Manage all RAID devices on a node."""
    api_doc_section_name = "RAID Devices"
    update = delete = None
    fields = DISPLAYED_RAID_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ('raid_devices_handler', ["system_id"])

    def create(self, request, system_id):
        """Creates a RAID

        :param name: Name of the RAID.
        :param uuid: UUID of the RAID.
        :param level: RAID level.
        :param block_devices: Block devices to add to the RAID.
        :param spare_devices: Spare block devices to add to the RAID.
        :param partitions: Partitions to add to the RAID.
        :param spare_partitions: Spare partitions to add to the RAID.

        Returns 404 if the node is not found.
        """
        node = Node.nodes.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.EDIT)
        form = CreateRaidForm(node, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def read(self, request, system_id):
        """List all RAID devices belonging to node.

        Returns 404 if the node is not found.
        """
        node = Node.nodes.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.VIEW)
        return RAID.objects.filter_by_node(node)


class RaidHandler(OperationsHandler):
    """Manage a specific RAID device on a node."""
    api_doc_section_name = "RAID Device"
    create = None
    model = RAID
    fields = DISPLAYED_RAID_FIELDS

    @classmethod
    def resource_uri(cls, raid=None):
        # See the comment in NodeHandler.resource_uri.
        system_id = "system_id"
        raid_id = "raid_id"
        if raid is not None:
            raid_id = raid.id
            node = raid.get_node()
            if node is not None:
                system_id = node.system_id
        return ('raid_device_handler', (system_id, raid_id))

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

    def update(self, request, system_id, raid_id):
        """Update RAID on node.

        :param name: Name of the RAID.
        :param uuid: UUID of the RAID.
        :param add_block_devices: Block devices to add to the RAID.
        :param remove_block_devices: Block devices to remove from the RAID.
        :param add_spare_devices: Spare block devices to add to the RAID.
        :param remove_spare_devices: Spare block devices to remove
               from the RAID.
        :param add_partitions: Partitions to add to the RAID.
        :param remove_partitions: Partitions to remove from the RAID.
        :param add_spare_partitions: Spare partitions to add to the RAID.
        :param remove_spare_partitions: Spare partitions to remove from the
               RAID.

        Returns 404 if the node or RAID is not found.
        """
        raid = RAID.objects.get_object_or_404(
            system_id, raid_id, request.user, NODE_PERMISSION.EDIT)
        form = UpdateRaidForm(raid, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, system_id, raid_id):
        """Delete RAID on node.

        Returns 404 if the node or RAID is not found.
        """
        raid = RAID.objects.get_object_or_404(
            system_id, raid_id, request.user, NODE_PERMISSION.EDIT)
        raid.delete()
        return rc.DELETED
