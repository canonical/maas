# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `VMFS Datastore`."""

from piston3.utils import rc

from maasserver.api.support import OperationsHandler
from maasserver.enum import NODE_STATUS
from maasserver.exceptions import MAASAPIValidationError, NodeStateViolation
from maasserver.forms import CreateVMFSForm, UpdateVMFSForm
from maasserver.models import Machine, VMFS
from maasserver.permissions import NodePermission
from maasserver.utils.converters import human_readable_bytes

DISPLAYED_VMFS_DATASTORE_FIELDS = (
    "id",
    "system_id",
    "uuid",
    "name",
    "devices",
    "size",
    "human_size",
    "filesystem",
)


class VmfsDatastoresHandler(OperationsHandler):
    """Manage VMFS datastores on a machine."""

    api_doc_section_name = "VMFS datastores"
    update = delete = None
    fields = DISPLAYED_VMFS_DATASTORE_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ("vmfs_datastores_handler", ["system_id"])

    def read(self, request, system_id):
        """@description-title List all VMFS datastores.
        @description List all VMFS datastores belonging to a machine with the
        given system_id.

        @param (string) "{system_id}" [required=true] The machine system_id
        containing the VMFS datastores.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of
        VMFS datastore objects.
        @success-example "success-json" [exkey=vmfs-datastores-read]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        machine = Machine.objects.get_node_or_404(
            system_id, request.user, NodePermission.view
        )
        return VMFS.objects.filter_by_node(machine)

    def create(self, request, system_id):
        """@description-title Create a VMFS datastore.
        @description Create a VMFS datastore belonging to a machine with the
        given system_id.

        Note that at least one valid block device or partition is required.

        @param (string) "{system_id}" [required=true] The machine system_id on
        which to create the VMFS datastore.

        @param (string) "name" [required=true] Name of the VMFS datastore.

        @param (string) "uuid" [required=false] (optional) UUID of the VMFS
        group.

        @param (string) "block_devices" [required=false] Block devices to add
        to the VMFS datastore.

        @param (string) "partitions" [required=false] Partitions to add to the
        VMFS datastore.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new VMFS
        datastore.
        @success-example "success-json" [exkey=vmfs-datastores-create]
        placeholder text

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
                "Cannot create VMFS group because the machine is not Ready."
            )
        form = CreateVMFSForm(machine, data=request.data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        else:
            return form.save()


class VmfsDatastoreHandler(OperationsHandler):
    """Manage VMFS datastore on a machine."""

    api_doc_section_name = "VMFS datastore"
    create = None
    model = VMFS
    fields = DISPLAYED_VMFS_DATASTORE_FIELDS

    @classmethod
    def resource_uri(cls, vmfs=None):
        # See the comment in NodeHandler.resource_uri.
        system_id = "system_id"
        vmfs_id = "id"
        if vmfs is not None:
            vmfs_id = vmfs.id
            node = vmfs.get_node()
            if node is not None:
                system_id = node.system_id
        return ("vmfs_datastore_handler", (system_id, vmfs_id))

    @classmethod
    def system_id(cls, vmfs):
        if vmfs is None:
            return None
        else:
            node = vmfs.get_node()
            return None if node is None else node.system_id

    @classmethod
    def size(cls, vmfs):
        return vmfs.get_size()

    @classmethod
    def human_size(cls, vmfs):
        return human_readable_bytes(vmfs.get_size())

    @classmethod
    def devices(cls, vmfs):
        return [
            filesystem.get_device() for filesystem in vmfs.filesystems.all()
        ]

    @classmethod
    def filesystem(cls, vmfs):
        # XXX: This is almost the same as
        # m.api.partitions.PartitionHandler.filesystem.
        filesystem = vmfs.virtual_device.get_effective_filesystem()
        if filesystem is not None:
            return {
                "fstype": filesystem.fstype,
                "mount_point": filesystem.mount_point,
            }
        else:
            return None

    def read(self, request, system_id, id):
        """@description-title Read a VMFS datastore.
        @description Read a VMFS datastore with the given id on the machine
        with the given system_id.

        @param (string) "{system_id}" [required=true] The machine system_id on
        which to create the VMFS datastore.
        @param (int) "{id}" [required=true] The id of the VMFS datastore.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        VMFS data.
        @success-example "success-json" [exkey=vmfs-datastore-read]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No VMFS matches the given query.
        """
        return VMFS.objects.get_object_or_404(
            system_id, id, request.user, NodePermission.view
        )

    def update(self, request, system_id, id):
        """@description-title Update a VMFS datastore.
        @description Update a VMFS datastore with the given id on the machine
        with the given system_id.

        @param (string) "{system_id}" [required=true] The machine system_id
        containing the VMFS datastore.
        @param (int) "{id}" [required=true] The id of the VMFS datastore.

        @param (string) "name" [required=false] Name of the VMFS datastore.

        @param (string) "uuid" [required=false] UUID of the VMFS datastore.

        @param (string) "add_block_devices" [required=false] Block devices to
        add to the VMFS datastore.

        @param (string) "add_partitions" [required=false] Partitions to add to
        the VMFS datastore.

        @param (string) "remove_partitions" [required=false] Partitions to
        remove from the VMFS datastore.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        VMFS datastore.
        @success-example "success-json" [exkey=vmfs-datastore-update]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No VMFS matches the given query.

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        vmfs = VMFS.objects.get_object_or_404(
            system_id, id, request.user, NodePermission.admin
        )
        node = vmfs.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot update the VMFS datastore because the machine is not "
                "Ready."
            )
        form = UpdateVMFSForm(vmfs, data=request.data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        else:
            return form.save()

    def delete(self, request, system_id, id):
        """@description-title Delete the specified VMFS datastore.
        @description Delete a VMFS datastore with the given id from the machine
        with the given system_id.

        @param (string) "{system_id}" [required=true] The machine system_id
        containing the VMFS datastore.
        @param (int) "{id}" [required=true] The id of the VMFS datastore.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No VMFS matches the given query.

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        vmfs = VMFS.objects.get_object_or_404(
            system_id, id, request.user, NodePermission.admin
        )
        node = vmfs.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot delete VMFS datastore because the machine is not "
                "Ready."
            )
        vmfs.delete()
        return rc.DELETED
