# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DeviceHandler",
    "DevicesHandler",
    ]

from django.shortcuts import get_object_or_404
from maasserver.api.logger import maaslog
from maasserver.api.support import (
    operation,
    OperationsHandler,
    )
from maasserver.api.utils import (
    get_mandatory_param,
    get_optional_list,
    )
from maasserver.dns.config import dns_update_zones
from maasserver.enum import (
    IPADDRESS_TYPE,
    NODE_PERMISSION,
    )
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPIValidationError,
    )
from maasserver.fields import MAC_RE
from maasserver.forms import (
    DeviceForm,
    DeviceWithMACsForm,
    )
from maasserver.models import (
    MACAddress,
    Node,
    NodeGroup,
    NodeGroupInterface,
    )
from maasserver.models.node import Device
from piston.utils import rc

# Device's fields exposed on the API.
DISPLAYED_DEVICE_FIELDS = (
    'system_id',
    'hostname',
    'owner',
    ('macaddress_set', ('mac_address',)),
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

    def read(self, request, system_id):
        """Read a specific device.

        Returns 404 if the device is not found.
        """
        return Device.devices.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.VIEW)

    def update(self, request, system_id):
        """Update a specific device.

        :param hostname: The new hostname for this device.
        :type hostname: unicode

        Returns 404 if the device is not found.
        Returns 403 if the user does not have permission to update the device.
        """
        device = Node.devices.get_node_or_404(
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
        device = Node.devices.get_node_or_404(
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

    @operation(idempotent=False)
    def claim_sticky_ip_address(self, request, system_id):
        """Assign a "sticky" IP address to a device's MAC.

        :param mac_address: Optional MAC address on the device on which to
            assign the sticky IP address.  If not passed, defaults to the
            primary MAC for the device.
        :param requested_address: Optional IP address to claim.  Must be in
            the range defined on a cluster interface to which the context
            MAC is related, or 403 Forbidden is returned.  If the requested
            address is unavailable for use, 404 Not Found is returned.

        Returns 404 if the device is not found.
        Returns 400 if the mac_address is not found on the device.
        Returns 503 if there are not enough IPs left on the cluster interface
        to which the mac_address is linked.
        """
        device = Node.devices.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.EDIT)
        raw_mac = request.POST.get('mac_address', None)
        if raw_mac is None:
            mac_address = device.get_primary_mac()
        else:
            try:
                mac_address = MACAddress.objects.get(
                    mac_address=raw_mac, node=device)
            except MACAddress.DoesNotExist:
                raise MAASAPIBadRequest(
                    "mac_address %s not found on the device" % raw_mac)
        requested_address = request.POST.get('requested_address', None)
        sticky_ips = mac_address.claim_static_ips(
            alloc_type=IPADDRESS_TYPE.STICKY,
            requested_address=requested_address)
        claims = [
            (static_ip.ip, mac_address.mac_address.get_raw())
            for static_ip in sticky_ips]
        device.update_host_maps(claims)
        dns_update_zones([device.nodegroup])
        maaslog.info(
            "%s: Sticky IP address(es) allocated: %s", device.hostname,
            ', '.join(allocation.ip for allocation in sticky_ips))
        return device

    @operation(idempotent=False)
    def connect_mac_to_cluster_interface(self, request, system_id):
        """Connect the given MAC Address to a cluster interface.

        :param mac_address: MAC address to connect.
        :param cluster_uuid: The UUID of the cluster the MAC address should
            be connected to.
        :param cluster_interface_name: The name of the cluster interface the
            MAC address should be connected to.

        Returns 404 if the device is not found.
        Returns 400 if the mac_address is not found on the device.
        """
        device = Node.devices.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.EDIT)
        mac_address = get_mandatory_param(request.data, 'mac_address')
        cluster_uuid = get_mandatory_param(request.data, 'cluster_uuid')
        cluster_interface_name = get_mandatory_param(
            request.data, 'cluster_interface')
        cluster = get_object_or_404(NodeGroup, uuid=cluster_uuid)
        nodegroupinterface = get_object_or_404(
            NodeGroupInterface, nodegroup=cluster,
            name=cluster_interface_name)
        try:
            mac = MACAddress.objects.get(
                mac_address=mac_address, node=device)
        except MACAddress.DoesNotExist:
            raise MAASAPIBadRequest(
                "mac_address %s not found on the device" % mac_address)
        mac.cluster_interface = nodegroupinterface
        mac.save()
        maaslog.info(
            "%s %s linked to cluster interface %s",
            device.hostname, mac_address, nodegroupinterface.name)


class DevicesHandler(OperationsHandler):
    """Manage the collection of all the devices in the MAAS."""
    api_doc_section_name = "Devices"
    create = read = update = delete = None

    @operation(idempotent=False)
    def new(self, request):
        """Create a new device.

        :param mac_addresses: One or more MAC addresses for the device.
        :param hostname: A hostname. If not given, one will be generated.
        """
        form = DeviceWithMACsForm(data=request.data, request=request)
        if form.is_valid():
            device = form.save()
            maaslog.info("%s: Added new device", device.hostname)
            return device
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=True)
    def list(self, request):
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
        devices = Device.devices.get_nodes(
            request.user, NODE_PERMISSION.VIEW, ids=match_ids)
        if match_macs is not None:
            devices = devices.filter(macaddress__mac_address__in=match_macs)
        match_hostnames = get_optional_list(request.GET, 'hostname')
        if match_hostnames is not None:
            devices = devices.filter(hostname__in=match_hostnames)

        # Prefetch related objects that are needed for rendering the result.
        devices = devices.prefetch_related('macaddress_set__node')
        devices = devices.prefetch_related('macaddress_set__ip_addresses')
        devices = devices.prefetch_related('tags')
        devices = devices.select_related('nodegroup')
        devices = devices.prefetch_related('nodegroup__dhcplease_set')
        devices = devices.prefetch_related('nodegroup__nodegroupinterface_set')
        devices = devices.prefetch_related('zone')
        return devices.order_by('id')

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('devices_handler', [])
