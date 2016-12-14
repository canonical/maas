# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `RAID`."""

from maasserver.api.support import OperationsHandler
from maasserver.enum import (
    FILESYSTEM_TYPE,
    NODE_PERMISSION,
    NODE_STATUS,
)
from maasserver.exceptions import (
    MAASAPIValidationError,
    NodeStateViolation,
)
from maasserver.forms import (
    CreateRaidForm,
    UpdateRaidForm,
)
from maasserver.models import (
    Machine,
    RAID,
)
from maasserver.utils.converters import human_readable_bytes
from piston3.utils import rc


DISPLAYED_RAID_FIELDS = (
    'system_id',
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
    """Manage all RAID devices on a machine."""
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

        Returns 404 if the machine is not found.
        Returns 409 if the machine is not Ready.
        """
        machine = Machine.objects.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.ADMIN)
        if machine.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot create RAID because the machine is not Ready.")
        form = CreateRaidForm(machine, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def read(self, request, system_id):
        """List all RAID devices belonging to a machine.

        Returns 404 if the machine is not found.
        """
        machine = Machine.objects.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.VIEW)
        return RAID.objects.filter_by_node(machine)


class RaidHandler(OperationsHandler):
    """Manage a specific RAID device on a machine."""
    api_doc_section_name = "RAID Device"
    create = None
    model = RAID
    fields = DISPLAYED_RAID_FIELDS

    @classmethod
    def resource_uri(cls, raid=None):
        # See the comment in NodeHandler.resource_uri.
        system_id = "system_id"
        raid_id = "id"
        if raid is not None:
            raid_id = raid.id
            node = raid.get_node()
            if node is not None:
                system_id = node.system_id
        return ('raid_device_handler', (system_id, raid_id))

    @classmethod
    def system_id(cls, raid):
        node = raid.get_node()
        return None if node is None else node.system_id

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

    def read(self, request, system_id, id):
        """Read RAID device on a machine.

        Returns 404 if the machine or RAID is not found.
        """
        return RAID.objects.get_object_or_404(
            system_id, id, request.user, NODE_PERMISSION.VIEW)

    def update(self, request, system_id, id):
        """Update RAID on a machine.

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

        Returns 404 if the machine or RAID is not found.
        Returns 409 if the machine is not Ready.
        """
        raid = RAID.objects.get_object_or_404(
            system_id, id, request.user, NODE_PERMISSION.ADMIN)
        node = raid.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot update RAID because the machine is not Ready.")
        form = UpdateRaidForm(raid, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, system_id, id):
        """Delete RAID on a machine.

        Returns 404 if the machine or RAID is not found.
        Returns 409 if the machine is not Ready.
        """
        raid = RAID.objects.get_object_or_404(
            system_id, id, request.user, NODE_PERMISSION.ADMIN)
        node = raid.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot delete RAID because the machine is not Ready.")
        raid.delete()
        return rc.DELETED
