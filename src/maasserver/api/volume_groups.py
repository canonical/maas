# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `VolumeGroups`."""

from piston3.utils import rc

from maasserver.api.support import operation, OperationsHandler
from maasserver.api.utils import get_mandatory_param
from maasserver.enum import NODE_STATUS
from maasserver.exceptions import MAASAPIValidationError, NodeStateViolation
from maasserver.forms import (
    CreateLogicalVolumeForm,
    CreateVolumeGroupForm,
    UpdateVolumeGroupForm,
)
from maasserver.models import Machine, VirtualBlockDevice, VolumeGroup
from maasserver.permissions import NodePermission
from maasserver.utils.converters import human_readable_bytes

DISPLAYED_VOLUME_GROUP_FIELDS = (
    "system_id",
    "id",
    "uuid",
    "name",
    "devices",
    "size",
    "human_size",
    "available_size",
    "human_available_size",
    "used_size",
    "human_used_size",
    "logical_volumes",
)


class VolumeGroupsHandler(OperationsHandler):
    """Manage volume groups on a machine."""

    api_doc_section_name = "Volume groups"
    update = delete = None
    fields = DISPLAYED_VOLUME_GROUP_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ("volume_groups_handler", ["system_id"])

    def read(self, request, system_id):
        """@description-title List all volume groups
        @description List all volume groups belonging to a machine with the
        given system_id.

        @param (string) "{system_id}" [required=true] The machine system_id
        containing the volume groups.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of
        volume-group objects.
        @success-example "success-json" [exkey=vol-groups-read] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        machine = Machine.objects.get_node_or_404(
            system_id, request.user, NodePermission.view
        )
        return VolumeGroup.objects.filter_by_node(machine)

    def create(self, request, system_id):
        """@description-title Create a volume group
        @description Create a volume group belonging to a machine with the
        given system_id.

        Note that at least one valid block device or partition is required.

        @param (string) "{system_id}" [required=true] The machine system_id on
        which to create the volume group.

        @param (string) "name" [required=true] Name of the volume group.

        @param (string) "uuid" [required=false] (optional) UUID of the volume
        group.

        @param (string) "block_devices" [required=false] Block devices to add
        to the volume group.

        @param (string) "partitions" [required=false] Partitions to add to the
        volume group.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new volume
        group.
        @success-example "success-json" [exkey=vol-groups-create] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        machine = Machine.objects.get_node_or_404(
            system_id, request.user, NodePermission.admin
        )
        if machine.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot create volume group because the machine is not Ready."
            )
        form = CreateVolumeGroupForm(machine, data=request.data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        else:
            return form.save()


class VolumeGroupHandler(OperationsHandler):
    """Manage volume group on a machine."""

    api_doc_section_name = "Volume group"
    create = None
    model = VolumeGroup
    fields = DISPLAYED_VOLUME_GROUP_FIELDS

    @classmethod
    def resource_uri(cls, volume_group=None):
        # See the comment in NodeHandler.resource_uri.
        system_id = "system_id"
        volume_group_id = "id"
        if volume_group is not None:
            volume_group_id = volume_group.id
            node = volume_group.get_node()
            if node is not None:
                system_id = node.system_id
        return ("volume_group_handler", (system_id, volume_group_id))

    @classmethod
    def system_id(cls, volume_group):
        if volume_group is None:
            return None
        else:
            node = volume_group.get_node()
            return None if node is None else node.system_id

    @classmethod
    def size(cls, filesystem_group):
        return filesystem_group.get_size()

    @classmethod
    def human_size(cls, filesystem_group):
        return human_readable_bytes(filesystem_group.get_size())

    @classmethod
    def available_size(cls, volume_group):
        return volume_group.get_lvm_free_space()

    @classmethod
    def human_available_size(cls, volume_group):
        return human_readable_bytes(volume_group.get_lvm_free_space())

    @classmethod
    def used_size(cls, volume_group):
        return volume_group.get_lvm_allocated_size()

    @classmethod
    def human_used_size(cls, volume_group):
        return human_readable_bytes(volume_group.get_lvm_allocated_size())

    @classmethod
    def logical_volumes(cls, volume_group):
        return volume_group.virtual_devices.all()

    @classmethod
    def devices(cls, volume_group):
        return [
            filesystem.get_device()
            for filesystem in volume_group.filesystems.all()
        ]

    def read(self, request, system_id, id):
        """@description-title Read a volume group
        @description Read a volume group with the given id on the machine with
        the given system_id.

        @param (string) "{system_id}" [required=true] The machine system_id on
        which to create the volume group.
        @param (int) "{id}" [required=true] The id of the volume group.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        volume group.
        @success-example "success-json" [exkey=vol-groups-read-by-id]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No VolumeGroup matches the given query.
        """
        return VolumeGroup.objects.get_object_or_404(
            system_id, id, request.user, NodePermission.view
        )

    def update(self, request, system_id, id):
        """@description-title Update a volume group
        @description Update a volume group with the given id on the machine
        with the given system_id.

        @param (string) "{system_id}" [required=true] The machine system_id
        containing the volume group.
        @param (int) "{id}" [required=true] The id of the volume group.

        @param (string) "name" [required=false] Name of the volume group.

        @param (string) "uuid" [required=false] UUID of the volume group.

        @param (string) "add_block_devices" [required=false] Block devices to
        add to the volume group.

        @param (string) "remove_block_devices" [required=false] Block devices
        to remove from the volume group.

        @param (string) "add_partitions" [required=false] Partitions to add to
        the volume group.

        @param (string) "remove_partitions" [required=false] Partitions to
        remove from the volume group.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        volume group.
        @success-example "success-json" [exkey=vol-groups-update]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No VolumeGroup matches the given query.

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        volume_group = VolumeGroup.objects.get_object_or_404(
            system_id, id, request.user, NodePermission.admin
        )
        node = volume_group.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot update volume group because the machine is not Ready."
            )
        form = UpdateVolumeGroupForm(volume_group, data=request.data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        else:
            return form.save()

    def delete(self, request, system_id, id):
        """@description-title Delete volume group
        @description Delete a volume group with the given id from the machine
        with the given system_id.

        @param (string) "{system_id}" [required=true] The machine system_id
        containing the volume group.
        @param (int) "{id}" [required=true] The id of the volume group.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No VolumeGroup matches the given query.

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        volume_group = VolumeGroup.objects.get_object_or_404(
            system_id, id, request.user, NodePermission.admin
        )
        node = volume_group.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot delete volume group because the machine is not Ready."
            )
        volume_group.delete()
        return rc.DELETED

    @operation(idempotent=False)
    def create_logical_volume(self, request, system_id, id):
        """@description-title Create a logical volume
        @description Create a logical volume in the volume group with the given
        id on the machine with the given system_id.

        @param (string) "{system_id}" [required=true] The machine system_id
        containing the volume group.
        @param (int) "{id}" [required=true] The id of the volume group.

        @param (string) "name" [required=true] Name of the logical volume.

        @param (string) "uuid" [required=false] (optional) UUID of the logical
        volume.

        @param (string) "size" [required=false] (optional) Size of the logical
        volume. Must be larger than or equal to 4,194,304 bytes. E.g. ``4194304``. Will default to free space in the volume group if not given.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        volume group.
        @success-example "success-json" [exkey=vol-groups-create-log-vol]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No VolumeGroup matches the given query.

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        volume_group = VolumeGroup.objects.get_object_or_404(
            system_id, id, request.user, NodePermission.admin
        )
        node = volume_group.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot create logical volume because the machine is not "
                "Ready."
            )
        form = CreateLogicalVolumeForm(volume_group, data=request.data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        else:
            return form.save()

    @operation(idempotent=False)
    def delete_logical_volume(self, request, system_id, id):
        """@description-title Delete a logical volume
        @description Delete a logical volume in the volume group with the given
        id on the machine with the given system_id.

        Note: this operation returns HTTP status code 204 even if the logical
        volume id does not exist.

        @param (string) "{system_id}" [required=true] The machine system_id
        containing the volume group.
        @param (int) "{id}" [required=true] The id of the volume group.

        @param (int) "id" [required=true] The logical volume id.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No VolumeGroup matches the given query.

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        volume_group = VolumeGroup.objects.get_object_or_404(
            system_id, id, request.user, NodePermission.admin
        )
        node = volume_group.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot delete logical volume because the machine is not "
                "Ready."
            )
        volume_id = get_mandatory_param(request.data, "id")
        try:
            logical_volume = volume_group.virtual_devices.get(id=volume_id)
        except VirtualBlockDevice.DoesNotExist:
            # Ignore if it doesn't exists, we still return DELETED.
            pass
        else:
            logical_volume.delete()
        return rc.DELETED
