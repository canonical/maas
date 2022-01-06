# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Bcache`."""

from piston3.utils import rc

from maasserver.api.support import OperationsHandler
from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT, NODE_STATUS
from maasserver.exceptions import MAASAPIValidationError, NodeStateViolation
from maasserver.forms import CreateBcacheForm, UpdateBcacheForm
from maasserver.models import Bcache, Machine
from maasserver.permissions import NodePermission
from maasserver.utils.converters import human_readable_bytes
from provisioningserver.events import EVENT_TYPES

DISPLAYED_BCACHE_FIELDS = (
    "system_id",
    "id",
    "uuid",
    "name",
    "cache_set",
    "backing_device",
    "size",
    "human_size",
    "virtual_device",
    "cache_mode",
)


class BcachesHandler(OperationsHandler):
    """Manage bcache devices on a machine."""

    api_doc_section_name = "Bcache Devices"
    update = delete = None
    fields = DISPLAYED_BCACHE_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ("bcache_devices_handler", ["system_id"])

    def read(self, request, system_id):
        """@description-title List all bcache devices
        @description List all bcache devices belonging to a
        machine.

        @param (string) "{system_id}" [required=true] The machine's system_id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of
        bcache devices.
        @success-example "success-json" [exkey=bcache-placeholder] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested system_id is not found.
        @error-example "not-found"
            Not Found
        """
        machine = Machine.objects.get_node_or_404(
            system_id, request.user, NodePermission.view
        )
        return Bcache.objects.filter_by_node(machine)

    def create(self, request, system_id):
        """@description-title Creates a bcache
        @description Creates a bcache.

        Specifying both a device and a partition for a given role (cache or
        backing) is not allowed.

        @param (string) "{system_id}" [required=true] The machine's system_id.

        @param (string) "name" [required=false] Name of the Bcache.

        @param (string) "uuid" [required=false] UUID of the Bcache.

        @param (string) "cache_set" [required=false] Cache set.

        @param (string) "backing_device" [required=false] Backing block device.

        @param (string) "backing_partition" [required=false] Backing partition.

        @param (string) "cache_mode" [required=false] Cache mode:
        ``WRITEBACK``, ``WRITETHROUGH``, ``WRITEAROUND``.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new bcache
        device.
        @success-example "success-json" [exkey=bcache-placeholder] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested system_id is not found.
        @error-example "not-found"
            Not Found

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        machine = Machine.objects.get_node_or_404(
            system_id, request.user, NodePermission.admin
        )
        if machine.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot create Bcache because the machine is not Ready."
            )
        form = CreateBcacheForm(machine, data=request.data)
        if form.is_valid():
            create_audit_event(
                EVENT_TYPES.NODE,
                ENDPOINT.API,
                request,
                system_id,
                "Created bcache.",
            )
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)


class BcacheHandler(OperationsHandler):
    """Manage bcache device on a machine."""

    api_doc_section_name = "Bcache Device"
    create = None
    model = Bcache
    fields = DISPLAYED_BCACHE_FIELDS

    @classmethod
    def resource_uri(cls, bcache=None):
        # See the comment in NodeHandler.resource_uri.
        system_id = "system_id"
        bcache_id = "id"
        if bcache is not None:
            bcache_id = bcache.id
            node = bcache.get_node()
            if node is not None:
                system_id = node.system_id
        return ("bcache_device_handler", (system_id, bcache_id))

    @classmethod
    def system_id(cls, bcache):
        node = bcache.get_node()
        return None if node is None else node.system_id

    @classmethod
    def size(cls, bcache):
        return bcache.get_size()

    @classmethod
    def human_size(cls, bcache):
        return human_readable_bytes(bcache.get_size())

    @classmethod
    def virtual_device(cls, bcache):
        """Return the `VirtualBlockDevice` of bcache device."""
        return bcache.virtual_device

    @classmethod
    def backing_device(cls, bcache):
        """Return the backing device for this bcache."""
        return bcache.get_bcache_backing_filesystem().get_device()

    def read(self, request, system_id, id):
        """@description-title Read a bcache device
        @description Read bcache device on a machine.

        @param (string) "{system_id}" [required=true] The machine's system_id.
        @param (string) "{id}" [required=true] The bcache id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the bcache
        device.
        @success-example "success-json" [exkey=bcache-placeholder] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or bcache id is not
        found.
        @error-example "not-found"
            Not Found
        """
        return Bcache.objects.get_object_or_404(
            system_id, id, request.user, NodePermission.view
        )

    def delete(self, request, system_id, id):
        """@description-title Delete a bcache
        @description Delete bcache on a machine.

        @param (string) "{system_id}" [required=true] The machine's system_id.
        @param (string) "{id}" [required=true] The bcache id.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested id or system_id is not
        found.
        @error-example "not-found"
            Not Found

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        bcache = Bcache.objects.get_object_or_404(
            system_id, id, request.user, NodePermission.admin
        )
        node = bcache.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot delete Bcache because the machine is not Ready."
            )
        bcache.delete()
        create_audit_event(
            EVENT_TYPES.NODE,
            ENDPOINT.API,
            request,
            system_id,
            "Deleted bcache.",
        )
        return rc.DELETED

    def update(self, request, system_id, id):
        """@description-title Update a bcache
        @description Update bcache on a machine.

        Specifying both a device and a partition for a given role (cache or
        backing) is not allowed.

        @param (string) "{system_id}" [required=true] The machine's system_id.
        @param (string) "{id}" [required=true] The bcache id.

        @param (string) "name" [required=false] Name of the Bcache.

        @param (string) "uuid" [required=false] UUID of the Bcache.

        @param (string) "cache_set" [required=false] Cache set to replace
        current one.

        @param (string) "backing_device" [required=false] Backing block device
        to replace current one.

        @param (string) "backing_partition" [required=false] Backing partition
        to replace current one.

        @param (string) "cache_mode" [required=false] Cache mode:
        ``WRITEBACK``, ``WRITETHROUGH``, ``WRITEAROUND``.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new bcache
        device.
        @success-example "success-json" [exkey=bcache-placeholder] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested id or system_id is not
        found.
        @error-example "not-found"
            Not Found

        @error (http-status-code) "409" 409
        @error (content) "not-ready" The requested machine is not ready.
        """
        bcache = Bcache.objects.get_object_or_404(
            system_id, id, request.user, NodePermission.admin
        )
        node = bcache.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot update Bcache because the machine is not Ready."
            )
        form = UpdateBcacheForm(bcache, data=request.data)
        if form.is_valid():
            create_audit_event(
                EVENT_TYPES.NODE,
                ENDPOINT.API,
                request,
                system_id,
                "Updated bcache.",
            )
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)
