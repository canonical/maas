# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from django.core.exceptions import PermissionDenied
from piston3.utils import rc

from maasserver.api.logger import maaslog
from maasserver.api.nodes import (
    NodeHandler,
    NodesHandler,
    WorkloadAnnotationsMixin,
)
from maasserver.api.support import operation
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import DeviceForm, DeviceWithMACsForm
from maasserver.models.node import Device
from maasserver.permissions import NodePermission
from maasserver.utils.orm import reload_object

# Device's fields exposed on the API.
DISPLAYED_DEVICE_FIELDS = (
    "system_id",
    "hostname",
    "description",
    "domain",
    "fqdn",
    "owner",
    "owner_data",
    "parent",
    "tag_names",
    "address_ttl",
    "ip_addresses",
    "interface_set",
    "zone",
    "node_type",
    "node_type_name",
    "workload_annotations",
)


class DeviceHandler(NodeHandler, WorkloadAnnotationsMixin):
    """
    Manage an individual device.

    The device is identified by its system_id.
    """

    api_doc_section_name = "Device"

    create = None  # Disable create.
    model = Device
    fields = DISPLAYED_DEVICE_FIELDS

    @classmethod
    def parent(handler, node):
        """Return the system ID of the parent, if any."""
        if node.parent is None:
            return None
        else:
            return node.parent.system_id

    def update(self, request, system_id):
        """@description-title Update a device
        @description Update a device with a given system_id.

        @param (string) "{system_id}" [required=true] A device system_id.

        @param (string) "hostname" [required=false] The hostname for this
        device.

        @param (string) "description" [required=false] The optional description
        for this machine.

        @param (string) "domain" [required=false] The domain for this device.

        @param (string) "parent" [required=false] Optional system_id to
        indicate this device's parent. If the parent is already set and this
        parameter is omitted, the parent will be unchanged.

        @param (string) "zone" [required=false] Name of a valid physical zone
        in which to place this node.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        device.
        @success-example "success-json" [exkey=devices-update] placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        required to update the device.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested device is not found.
        @error-example "not-found"
            No Device matches the given query.
        """
        device = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.edit
        )
        form = DeviceForm(data=request.data, instance=device)

        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, system_id):
        """@description-title Delete a device
        @description Delete a device with the given system_id.

        @param (string) "{system_id}" [required=true] A device system_id.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        required to delete the device.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested device is not found.
        @error-example "not-found"
            No Device matches the given query.
        """
        device = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.edit
        )
        device.delete()
        return rc.DELETED

    @operation(idempotent=False)
    def restore_networking_configuration(self, request, system_id):
        """@description-title Reset networking options
        @description Restore the networking options of a device with the given
        system_id to default values.

        @param (string) "{system_id}" [required=true] A device system_id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        device.
        @success-example "success-json" [exkey=devices-restore-network-conf]
        placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        required to update the device.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested device is not found.
        @error-example "not-found"
            No Device matches the given query.
        """
        device = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.admin
        )
        device.set_initial_networking_configuration()
        return reload_object(device)

    @operation(idempotent=False)
    def restore_default_configuration(self, request, system_id):
        """@description-title Reset device configuration
        @description Restore the configuration options of a device with the
        given system_id to default values.

        @param (string) "{system_id}" [required=true] A device system_id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        device.
        @success-example "success-json" [exkey=devices-restore-default-conf]
        placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        required to update the device.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested device is not found.
        @error-example "not-found"
            No Device matches the given query.

        """
        device = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.admin
        )
        device.set_initial_networking_configuration()
        return reload_object(device)

    @classmethod
    def resource_uri(cls, device=None):
        # This method is called by piston in two different contexts:
        # - when generating an uri template to be used in the documentation
        # (in this case, it is called with node=None).
        # - when populating the 'resource_uri' field of an object
        # returned by the API (in this case, node is a node object).
        device_system_id = "system_id"
        if device is not None:
            device_system_id = device.system_id
        return ("device_handler", (device_system_id,))


class DevicesHandler(NodesHandler):
    """Manage the collection of all the devices in the MAAS."""

    api_doc_section_name = "Devices"
    update = delete = None
    base_model = Device

    def create(self, request):
        """@description-title Create a new device
        @description Create a new device.

        @param (string) "hostname" [required=false] A hostname. If not given,
        one will be generated.

        @param (string) "description" [required=false] A optional description.

        @param (string) "domain" [required=false] The domain of the device. If
        not given the default domain is used.

        @param (string) "mac_addresses" [required=true] One or more MAC
        addresses for the device.

        @param (string) "parent" [required=false] The system id of the parent.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new device.
        @success-example "success-json" [exkey=devices-create] placeholder text

        @error (http-status-code) "400" 400
        @error (content) "bad-param" There was a problem with the given
        parameters.
        """
        form = DeviceWithMACsForm(data=request.data, request=request)
        if not form.has_perm(request.user):
            raise PermissionDenied()
        if form.is_valid():
            device = form.save()
            parent = device.parent
            maaslog.info(
                "%s: Added new device%s",
                device.hostname,
                "" if not parent else " (parent: %s)" % parent.hostname,
            )
            return device
        else:
            raise MAASAPIValidationError(form.errors)

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("devices_handler", [])
