# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    "DeviceHandler",
    "DevicesHandler",
    ]

from maasserver.api.logger import maaslog
from maasserver.api.nodes import (
    NodeHandler,
    NodesHandler,
    OwnerDataMixin,
)
from maasserver.api.support import operation
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import (
    DeviceForm,
    DeviceWithMACsForm,
)
from maasserver.models.node import Device
from maasserver.utils.orm import reload_object
from piston3.utils import rc

# Device's fields exposed on the API.
DISPLAYED_DEVICE_FIELDS = (
    'system_id',
    'hostname',
    'domain',
    'fqdn',
    'owner',
    'owner_data',
    'parent',
    'tag_names',
    'address_ttl',
    'ip_addresses',
    ('interface_set', (
        'id',
        'name',
        'type',
        'vlan',
        'mac_address',
        'parents',
        'children',
        'tags',
        'enabled',
        'links',
        'params',
        'discovered',
        'effective_mtu',
        )),
    'zone',
    'node_type',
    'node_type_name',
    )


class DeviceHandler(NodeHandler, OwnerDataMixin):
    """Manage an individual device.

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
        """Update a specific device.

        :param hostname: The new hostname for this device.
        :type hostname: unicode

        :param domain: The domain for this device.
        :type domain: unicode

        :param parent: Optional system_id to indicate this device's parent.
            If the parent is already set and this parameter is omitted,
            the parent will be unchanged.
        :type parent: unicode

        :param zone: Name of a valid physical zone in which to place this
            node.
        :type zone: unicode

        Returns 404 if the device is not found.
        Returns 403 if the user does not have permission to update the device.
        """
        device = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.EDIT)
        form = DeviceForm(data=request.data, instance=device)

        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, system_id):
        """Delete a specific Device.

        Returns 404 if the device is not found.
        Returns 403 if the user does not have permission to delete the device.
        Returns 204 if the device is successfully deleted.
        """
        device = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user,
            perm=NODE_PERMISSION.EDIT)
        device.delete()
        return rc.DELETED

    @operation(idempotent=False)
    def restore_networking_configuration(self, request, system_id):
        """Reset a device's network options.

        Returns 404 if the device is not found
        Returns 403 if the user does not have permission to reset the device.
        """
        device = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user,
            perm=NODE_PERMISSION.ADMIN)
        device.set_initial_networking_configuration()
        return reload_object(device)

    @operation(idempotent=False)
    def restore_default_configuration(self, request, system_id):
        """Reset a device's configuration to its initial state.

        Returns 404 if the device is not found.
        Returns 403 if the user does not have permission to reset the device.
        """
        device = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user,
            perm=NODE_PERMISSION.ADMIN)
        device.restore_default_configuration()
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
        return ('device_handler', (device_system_id,))


class DevicesHandler(NodesHandler):
    """Manage the collection of all the devices in the MAAS."""
    api_doc_section_name = "Devices"
    update = delete = None
    base_model = Device

    def create(self, request):
        """Create a new device.

        :param hostname: A hostname. If not given, one will be generated.
        :type hostname: unicode

        :param domain: The domain of the device. If not given the default
            domain is used.
        :type domain: unicode

        :param mac_addresses: One or more MAC addresses for the device.
        :type mac_addresses: unicode

        :param parent: The system id of the parent.  Optional.
        :type parent: unicode
        """
        form = DeviceWithMACsForm(data=request.data, request=request)
        if form.is_valid():
            device = form.save()
            parent = device.parent
            maaslog.info(
                "%s: Added new device%s", device.hostname,
                "" if not parent else " (parent: %s)" % parent.hostname)
            return device
        else:
            raise MAASAPIValidationError(form.errors)

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('devices_handler', [])
