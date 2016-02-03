# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The device handler for the WebSocket connection."""

__all__ = [
    "DeviceHandler",
    ]

from maasserver.clusterrpc import dhcp
from maasserver.enum import (
    IPADDRESS_TYPE,
    NODE_PERMISSION,
)
from maasserver.exceptions import NodeActionError
from maasserver.forms import (
    DeviceForm,
    DeviceWithMACsForm,
)
from maasserver.models.node import Device
from maasserver.models.nodegroupinterface import NodeGroupInterface
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.subnet import Subnet
from maasserver.node_action import compile_node_actions
from maasserver.websockets.base import (
    HandlerDoesNotExistError,
    HandlerError,
)
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from provisioningserver.logger import get_maas_logger


maaslog = get_maas_logger("websockets.device")


class DEVICE_IP_ASSIGNMENT:
    """The vocabulary of a `Device`'s possible IP assignment type. This value
    is calculated by looking at the overall model for a `Device`. This is not
    set directly on the model."""
    #: Device is outside of MAAS control.
    EXTERNAL = "external"

    #: Device receives ip address from `NodeGroupInterface` dynamic range.
    DYNAMIC = "dynamic"

    #: Device has ip address assigned from `NodeGroupInterface` static range.
    STATIC = "static"


def update_host_maps(static_mappings, nodegroups):
    """Helper to call update_host_maps will static mappings for all
    `nodegroups`."""
    static_mappings = {
        nodegroup: dict(static_mappings)
        for nodegroup in nodegroups
        }
    return list(dhcp.update_host_maps(static_mappings))


def get_Interface_from_list(interfaces, mac):
    """Return the `Interface` object based on the mac value."""
    for obj in interfaces:
        if obj.mac_address == mac:
            return obj
    return None


def log_static_allocations(device, external_static_ips, assigned_sticky_ips):
    """Log the allocation of the static ip address."""
    all_ips = [
        static_ip.ip
        for static_ip, _ in external_static_ips
        ]
    all_ips.extend([
        static_ip.ip
        for static_ip, _ in assigned_sticky_ips
        ])
    if len(all_ips) > 0:
        maaslog.info(
            "%s: Sticky IP address(es) allocated: %s",
            device.hostname, ', '.join(all_ips))


class DeviceHandler(TimestampedModelHandler):

    class Meta:
        queryset = (
            Device.devices.filter(installable=False, parent=None)
            .select_related('nodegroup', 'owner')
            .prefetch_related('interface_set__ip_addresses__subnet')
            .prefetch_related('nodegroup__nodegroupinterface_set')
            .prefetch_related('zone')
            .prefetch_related('tags'))
        pk = 'system_id'
        pk_type = str
        allowed_methods = ['list', 'get', 'set_active', 'create', 'action']
        exclude = [
            "id",
            "installable",
            "boot_interface",
            "boot_cluster_ip",
            "boot_disk",
            "token",
            "netboot",
            "agent_name",
            "cpu_count",
            "memory",
            "power_state",
            "routers",
            "architecture",
            "boot_type",
            "bios_boot_method",
            "status",
            "power_parameters",
            "power_state_updated",
            "disable_ipv4",
            "osystem",
            "power_type",
            "error_description",
            "error",
            "license_key",
            "distro_series",
            "min_hwe_kernel",
            "hwe_kernel",
            "gateway_link_ipv4",
            "gateway_link_ipv6",
            "enable_ssh",
            "skip_networking",
            "skip_storage",
            ]
        list_fields = [
            "system_id",
            "hostname",
            "owner",
            "zone",
            "parent",
            "pxe_mac",
            ]
        listen_channels = [
            "device",
            ]

    def get_queryset(self):
        """Return `QuerySet` for devices only vewable by `user`."""
        nodes = super(DeviceHandler, self).get_queryset()
        return Device.devices.get_nodes(
            self.user, NODE_PERMISSION.VIEW, from_nodes=nodes)

    def dehydrate_owner(self, user):
        """Return owners username."""
        if user is None:
            return ""
        else:
            return user.username

    def dehydrate_zone(self, zone):
        """Return zone name."""
        return {
            "id": zone.id,
            "name": zone.name,
            }

    def dehydrate_nodegroup(self, nodegroup):
        """Return the nodegroup name."""
        if nodegroup is None:
            return None
        else:
            return {
                "id": nodegroup.id,
                "uuid": nodegroup.uuid,
                "name": nodegroup.name,
                "cluster_name": nodegroup.cluster_name,
                }

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        data["fqdn"] = obj.fqdn
        data["actions"] = list(compile_node_actions(obj, self.user).keys())

        boot_interface = obj.get_boot_interface()
        data["primary_mac"] = (
            "%s" % boot_interface.mac_address
            if boot_interface is not None else "")
        data["extra_macs"] = [
            "%s" % interface.mac_address
            for interface in obj.interface_set.all()
            if interface != boot_interface
            ]

        data["ip_assignment"] = self.dehydrate_ip_assignment(
            obj, boot_interface)
        data["ip_address"] = self.dehydrate_ip_address(
            obj, boot_interface)

        data["tags"] = [
            tag.name
            for tag in obj.tags.all()
            ]
        return data

    def _get_first_none_discovered_ip(self, ip_addresses):
        for ip in ip_addresses:
            if ip.alloc_type != IPADDRESS_TYPE.DISCOVERED:
                return ip

    def _get_first_discovered_ip_with_ip(self, ip_addresses):
        for ip in ip_addresses:
            if ip.alloc_type == IPADDRESS_TYPE.DISCOVERED and ip.ip:
                return ip

    def dehydrate_ip_assignment(self, obj, interface):
        """Return the calculated `DEVICE_IP_ASSIGNMENT` based on the model."""
        if interface is None:
            return ""
        # We get the IP address from the all() so the cache is used.
        ip_addresses = list(interface.ip_addresses.all())
        first_ip = self._get_first_none_discovered_ip(ip_addresses)
        if first_ip is not None:
            if first_ip.alloc_type == IPADDRESS_TYPE.DHCP:
                return DEVICE_IP_ASSIGNMENT.DYNAMIC
            elif first_ip.subnet is None:
                return DEVICE_IP_ASSIGNMENT.EXTERNAL
            else:
                return DEVICE_IP_ASSIGNMENT.STATIC
        return DEVICE_IP_ASSIGNMENT.DYNAMIC

    def dehydrate_ip_address(self, obj, interface):
        """Return the IP address for the device."""
        if interface is None:
            return None

        # Get ip address from StaticIPAddress if available.
        ip_addresses = list(interface.ip_addresses.all())
        first_ip = self._get_first_none_discovered_ip(ip_addresses)
        if first_ip is not None:
            if first_ip.alloc_type == IPADDRESS_TYPE.DHCP:
                discovered_ip = self._get_first_discovered_ip_with_ip(
                    ip_addresses)
                if discovered_ip:
                    return "%s" % discovered_ip.ip
            elif first_ip.ip:
                return "%s" % first_ip.ip
        # Currently has no assigned IP address.
        return None

    def get_object(self, params):
        """Get object by using the `pk` in `params`."""
        obj = super(DeviceHandler, self).get_object(params)
        if self.user.is_superuser or obj.owner == self.user:
            return obj
        raise HandlerDoesNotExistError(params[self._meta.pk])

    def get_form_class(self, action):
        """Return the form class used for `action`."""
        if action == "create":
            return DeviceWithMACsForm
        elif action == "update":
            return DeviceForm
        else:
            raise HandlerError("Unknown action: %s" % action)

    def get_mac_addresses(self, data):
        """Convert the given `data` into a list of mac addresses.

        This is used by the create method and the hydrate method.
        The `primary_mac` will always be the first entry in the list.
        """
        macs = data.get("extra_macs", [])
        if "primary_mac" in data:
            macs.insert(0, data["primary_mac"])
        return macs

    def preprocess_form(self, action, params):
        """Process the `params` to before passing the data to the form."""
        new_params = {
            "mac_addresses": self.get_mac_addresses(params),
            "hostname": params.get("hostname"),
            }

        # Cleanup any fields that have a None value.
        new_params = {
            key: value
            for key, value in new_params.items()
            if value is not None
        }
        return super(DeviceHandler, self).preprocess_form(action, new_params)

    def create(self, params):
        """Create the object from params."""
        # XXX blake_r 03-04-15 bug=1440102: This is very ugly and a repeat
        # of code in other places. Needs to be refactored.

        # Create the object with the form and then create all of the interfaces
        # based on the users choices.
        data = super(DeviceHandler, self).create(params)
        device_obj = Device.objects.get(system_id=data['system_id'])
        interfaces = list(device_obj.interface_set.all())
        external_static_ips = []
        assigned_sticky_ips = []

        # Acquire all of the needed ip address based on the user selection.
        for nic in params["interfaces"]:
            interface = get_Interface_from_list(interfaces, nic["mac"])
            ip_assignment = nic["ip_assignment"]
            if ip_assignment == DEVICE_IP_ASSIGNMENT.EXTERNAL:
                subnet = Subnet.objects.get_best_subnet_for_ip(
                    nic["ip_address"])
                sticky_ip = StaticIPAddress.objects.create(
                    alloc_type=IPADDRESS_TYPE.USER_RESERVED,
                    ip=nic["ip_address"], subnet=subnet, user=self.user)
                interface.ip_addresses.add(sticky_ip)
                external_static_ips.append(
                    (sticky_ip, interface))
            elif ip_assignment == DEVICE_IP_ASSIGNMENT.DYNAMIC:
                dhcp_ip = StaticIPAddress.objects.create(
                    alloc_type=IPADDRESS_TYPE.DHCP, ip=None)
                interface.ip_addresses.add(dhcp_ip)
            elif ip_assignment == DEVICE_IP_ASSIGNMENT.STATIC:
                # Link the MAC address to the cluster interface.
                cluster_interface = NodeGroupInterface.objects.get(
                    id=nic["interface"])
                ip = StaticIPAddress.objects.create(
                    alloc_type=IPADDRESS_TYPE.DISCOVERED,
                    ip=None, subnet=cluster_interface.subnet)
                interface.ip_addresses.add(ip)

                # Convert an empty string to None.
                ip_address = nic.get("ip_address")
                if not ip_address:
                    ip_address = None

                # Claim the static ip.
                sticky_ips = interface.claim_static_ips(
                    requested_address=ip_address)
                assigned_sticky_ips.extend([
                    (static_ip, interface)
                    for static_ip in sticky_ips
                ])

        log_static_allocations(
            device_obj, external_static_ips, assigned_sticky_ips)
        return self.full_dehydrate(device_obj)

    def action(self, params):
        """Perform the action on the object."""
        obj = self.get_object(params)
        action_name = params.get("action")
        actions = compile_node_actions(obj, self.user)
        action = actions.get(action_name)
        if action is None:
            raise NodeActionError(
                "%s action is not available for this device." % action_name)
        extra_params = params.get("extra", {})
        return action.execute(**extra_params)
