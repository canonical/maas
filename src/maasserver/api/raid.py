# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `RAID`."""

from piston3.utils import rc

from maasserver.api.support import OperationsHandler
from maasserver.enum import FILESYSTEM_TYPE, NODE_STATUS
from maasserver.exceptions import MAASAPIValidationError, NodeStateViolation
from maasserver.forms import CreateRaidForm, UpdateRaidForm
from maasserver.models import Machine, RAID
from maasserver.permissions import NodePermission
from maasserver.utils.converters import human_readable_bytes

DISPLAYED_RAID_FIELDS = (
    "system_id",
    "id",
    "uuid",
    "name",
    "level",
    "devices",
    "spare_devices",
    "size",
    "human_size",
    "virtual_device",
)


class RaidsHandler(OperationsHandler):
    """Manage all RAIDs (Redundant Array of Independent Disks) on a machine."""

    api_doc_section_name = "RAID Devices"
    update = delete = None
    fields = DISPLAYED_RAID_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ("raid_devices_handler", ["system_id"])

    def create(self, request, system_id):
        """@description-title Set up a RAID
        @description Set up a RAID on a machine with the given system_id.

        @param (string) "{system_id}" [required=true] The system_id of the
        machine on which to set up the RAID.

        @param (string) "name" [required=false] Name of the RAID.

        @param (string) "uuid" [required=false] UUID of the RAID.

        @param (int) "level" [required=true] RAID level.

        @param (string) "block_devices" [required=false] Block devices to add
        to the RAID.

        @param (string) "spare_devices" [required=false] Spare block devices to
        add to the RAID.

        @param (string) "partitions" [required=false] Partitions to add to the
        RAID.

        @param (string) "spare_partitions" [required=false] Spare partitions to
        add to the RAID.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the new RAID.
        @success-example "success-json" [exkey=raids-placeholder] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            Not Found

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        @error-example "not-ready"
            Cannot create RAID because the machine is not Ready.
        """
        machine = Machine.objects.get_node_or_404(
            system_id, request.user, NodePermission.admin
        )
        if machine.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot create RAID because the machine is not Ready."
            )
        form = CreateRaidForm(machine, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def read(self, request, system_id):
        """@description-title List all RAIDs
        @description List all RAIDs belonging to a machine with the given
        system_id.

        @param (string) "{system_id}" [required=true] The system_id of the
        machine containing the RAIDs.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a list of
        available RAIDs.
        @success-example "success-json" [exkey=raids-placeholder] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            Not Found
        """
        machine = Machine.objects.get_node_or_404(
            system_id, request.user, NodePermission.view
        )
        return RAID.objects.filter_by_node(machine)


class RaidHandler(OperationsHandler):
    """
    Manage a specific RAID (Redundant Array of Independent Disks) on a
    machine.
    """

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
        return ("raid_device_handler", (system_id, raid_id))

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
            filesystem.get_device()
            for filesystem in raid.filesystems.filter(
                fstype=FILESYSTEM_TYPE.RAID
            )
        ]

    @classmethod
    def spare_devices(cls, raid):
        """Return the spare devices in this RAID."""
        return [
            filesystem.get_device()
            for filesystem in raid.filesystems.filter(
                fstype=FILESYSTEM_TYPE.RAID_SPARE
            )
        ]

    def read(self, request, system_id, id):
        """@description-title Read a RAID
        @description Read RAID with the given id on a machine with the
        given system_id.

        @param (string) "{system_id}" [required=true] The system_id of the
        machine containing the RAID.
        @param (int) "{id}" [required=true] A RAID id.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing the requested
        RAID.
        @success-example "success-json" [exkey=raids-placeholder] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or RAID is not
        found.
        @error-example "not-found"
            Not Found
        """
        return RAID.objects.get_object_or_404(
            system_id, id, request.user, NodePermission.view
        )

    def update(self, request, system_id, id):
        """@description-title Update a RAID
        @description Update a RAID with the given id on a machine with the
        given system_id.

        @param (string) "{system_id}" [required=true] The system_id of the
        machine containing the RAID.
        @param (int) "{id}" [required=true] A RAID id.

        @param (string) "name" [required=false] Name of the RAID.

        @param (string) "uuid" [required=false] UUID of the RAID.

        @param (string) "add_block_devices" [required=false] Block devices to
        add to the RAID.

        @param (string) "remove_block_devices" [required=false] Block devices
        to remove from the RAID.

        @param (string) "add_spare_devices" [required=false] Spare block
        devices to add to the RAID.

        @param (string) "remove_spare_devices" [required=false] Spare block
        devices to remove from the RAID.

        @param (string) "add_partitions" [required=false] Partitions to add to
        the RAID.

        @param (string) "remove_partitions" [required=false] Partitions to
        remove from the RAID.

        @param (string) "add_spare_partitions" [required=false] Spare
        partitions to add to the RAID.

        @param (string) "remove_spare_partitions" [required=false] Spare
        partitions to remove from the RAID.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing the updated
        RAID.
        @success-example "success-json" [exkey=raids-placeholder] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or RAID id is not
        found.
        @error-example "not-found"
            Not Found

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        raid = RAID.objects.get_object_or_404(
            system_id, id, request.user, NodePermission.admin
        )
        node = raid.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot update RAID because the machine is not Ready."
            )
        form = UpdateRaidForm(raid, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, system_id, id):
        """@description-title Delete a RAID
        @description Delete a RAID with the given id on a machine with the
        given system_id.

        @param (string) "{system_id}" [required=true] The system_id of the
        machine containing the RAID.
        @param (int) "{id}" [required=true] A RAID id.

        @success (http-status-code) "204" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or RAID is not
        found.
        @error-example "not-found"
            Not Found

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        raid = RAID.objects.get_object_or_404(
            system_id, id, request.user, NodePermission.admin
        )
        node = raid.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot delete RAID because the machine is not Ready."
            )
        raid.delete()
        return rc.DELETED
