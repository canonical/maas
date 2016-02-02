# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    "DeviceHandler",
    "DevicesHandler",
    ]

from maasserver.api.logger import maaslog
from maasserver.api.support import (
    operation,
    OperationsHandler,
)
from maasserver.api.utils import get_optional_list
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import MAASAPIValidationError
from maasserver.fields import MAC_RE
from maasserver.forms import (
    DeviceForm,
    DeviceWithMACsForm,
)
from maasserver.models.node import Device
from piston3.utils import rc

# Device's fields exposed on the API.
DISPLAYED_DEVICE_FIELDS = (
    'system_id',
    'hostname',
    'owner',
    'macaddress_set',
    'parent',
    'tag_names',
    'ip_addresses',
    'zone',
    )


class DeviceHandler(OperationsHandler):
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

    @classmethod
    def hostname(handler, node):
        """Override the 'hostname' field so that it returns the FQDN."""
        return node.fqdn

    @classmethod
    def owner(handler, node):
        """Override 'owner' so it emits the owner's name rather than a
        full nested user object."""
        if node.owner is None:
            return None
        return node.owner.username

    @classmethod
    def macaddress_set(handler, device):
        return [
            {"mac_address": "%s" % interface.mac_address}
            for interface in device.interface_set.all()
            if interface.mac_address
        ]

    def read(self, request, system_id):
        """Read a specific device.

        Returns 404 if the device is not found.
        """
        return Device.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.VIEW)

    def update(self, request, system_id):
        """Update a specific device.

        :param hostname: The new hostname for this device.
        :param parent: Optional system_id to indicate this device's parent.
            If the parent is already set and this parameter is omitted,
            the parent will be unchanged.
        :type hostname: unicode

        Returns 404 if the device is not found.
        Returns 403 if the user does not have permission to update the device.
        """
        device = Device.objects.get_node_or_404(
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
        device = Device.objects.get_node_or_404(
            system_id=system_id, user=request.user,
            perm=NODE_PERMISSION.EDIT)
        device.delete()
        return rc.DELETED

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


class DevicesHandler(OperationsHandler):
    """Manage the collection of all the devices in the MAAS."""
    api_doc_section_name = "Devices"
    update = delete = None

    @operation(idempotent=False)
    def create(self, request):
        """Create a new device.

        :param mac_addresses: One or more MAC addresses for the device.
        :param hostname: A hostname. If not given, one will be generated.
        :param parent: The system id of the parent.  Optional.
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

    def read(self, request):
        """List devices visible to the user, optionally filtered by criteria.

        :param hostname: An optional list of hostnames.  Only devices with
            matching hostnames will be returned.
        :type hostname: iterable
        :param mac_address: An optional list of MAC addresses.  Only
            devices with matching MAC addresses will be returned.
        :type mac_address: iterable
        :param id: An optional list of system ids.  Only devices with
            matching system ids will be returned.
        :type id: iterable
        """
        # Get filters from request.
        match_ids = get_optional_list(request.GET, 'id')
        match_macs = get_optional_list(request.GET, 'mac_address')
        if match_macs is not None:
            invalid_macs = [
                mac for mac in match_macs if MAC_RE.match(mac) is None]
            if len(invalid_macs) != 0:
                raise MAASAPIValidationError(
                    "Invalid MAC address(es): %s" % ", ".join(invalid_macs))

        # Fetch nodes and apply filters.
        devices = Device.objects.get_nodes(
            request.user, NODE_PERMISSION.VIEW, ids=match_ids)
        if match_macs is not None:
            devices = devices.filter(interface__mac_address__in=match_macs)
        match_hostnames = get_optional_list(request.GET, 'hostname')
        if match_hostnames is not None:
            devices = devices.filter(hostname__in=match_hostnames)

        # Prefetch related objects that are needed for rendering the result.
        devices = devices.prefetch_related('interface_set__node')
        devices = devices.prefetch_related('interface_set__ip_addresses')
        devices = devices.prefetch_related('tags')
        devices = devices.prefetch_related('zone')
        devices = devices.prefetch_related('domain')
        return devices.order_by('id')

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('devices_handler', [])
