# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The device handler for the WebSocket connection."""

__all__ = [
    "DeviceHandler",
    ]

from maasserver.enum import (
    INTERFACE_LINK_TYPE,
    IPADDRESS_TYPE,
    NODE_PERMISSION,
)
from maasserver.exceptions import NodeActionError
from maasserver.forms import (
    DeviceForm,
    DeviceWithMACsForm,
)
from maasserver.forms.interface import PhysicalInterfaceForm
from maasserver.models.node import Device
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.subnet import Subnet
from maasserver.node_action import compile_node_actions
from maasserver.utils.orm import reload_object
from maasserver.websockets.base import (
    HandlerDoesNotExistError,
    HandlerError,
    HandlerValidationError,
)
from maasserver.websockets.handlers.node import (
    node_prefetch,
    NodeHandler,
)
from netaddr import EUI
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


def get_Interface_from_list(interfaces, mac):
    """Return the `Interface` object with the given MAC address."""
    # Compare using EUI instances so that we're not concerned with a MAC's
    # canonical form, i.e. colons versus hyphens, uppercase versus lowercase.
    mac = EUI(mac)
    for interface in interfaces:
        ifmac = interface.mac_address
        if ifmac is not None and EUI(ifmac.raw) == mac:
            return interface
    else:
        return None


class DeviceHandler(NodeHandler):

    class Meta(NodeHandler.Meta):
        abstract = False
        queryset = node_prefetch(Device.objects.filter(parent=None))
        allowed_methods = [
            'list',
            'get',
            'set_active',
            'create',
            'create_interface',
            'action']
        exclude = [
            "dynamic",
            "type",
            "boot_interface",
            "boot_cluster_ip",
            "boot_disk",
            "token",
            "netboot",
            "agent_name",
            "cpu_count",
            "cpu_speed",
            "current_commissioning_script_set",
            "current_testing_script_set",
            "current_installation_script_set",
            "memory",
            "power_state",
            "routers",
            "architecture",
            "bios_boot_method",
            "status",
            "previous_status",
            "status_expires",
            "power_state_queried",
            "power_state_updated",
            "osystem",
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
            "instance_power_parameters",
            "dns_process",
            "managing_process",
            "address_ttl",
            "url",
            "last_image_sync",
            "default_user",
            ]
        list_fields = [
            "id",
            "system_id",
            "hostname",
            "owner",
            "domain",
            "zone",
            "parent",
            "pxe_mac",
            ]
        listen_channels = [
            "device",
            ]

    def get_queryset(self):
        """Return `QuerySet` for devices only viewable by `user`."""
        return Device.objects.get_nodes(
            self.user, NODE_PERMISSION.VIEW, from_nodes=self._meta.queryset)

    def dehydrate_parent(self, parent):
        if parent is None:
            return None
        else:
            return parent.system_id

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        data["fqdn"] = obj.fqdn
        data["actions"] = list(compile_node_actions(obj, self.user).keys())
        data["node_type_display"] = obj.get_node_type_display()

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
        if reload_object(self.user).is_superuser or obj.owner == self.user:
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
            "parent": params.get("parent"),
            }

        if "domain" in params:
            new_params["domain"] = params["domain"]["name"]

        # Cleanup any fields that have a None value.
        new_params = {
            key: value
            for key, value in new_params.items()
            if value is not None
        }
        return super(DeviceHandler, self).preprocess_form(action, new_params)

    def _configure_interface(self, interface, params):
        """Configure the interface based on the selection."""
        ip_assignment = params["ip_assignment"]
        if ip_assignment == DEVICE_IP_ASSIGNMENT.EXTERNAL:
            subnet = Subnet.objects.get_best_subnet_for_ip(
                params["ip_address"])
            sticky_ip = StaticIPAddress.objects.create(
                alloc_type=IPADDRESS_TYPE.USER_RESERVED,
                ip=params["ip_address"], subnet=subnet, user=self.user)
            interface.ip_addresses.add(sticky_ip)
        elif ip_assignment == DEVICE_IP_ASSIGNMENT.DYNAMIC:
            interface.link_subnet(INTERFACE_LINK_TYPE.DHCP, None)
        elif ip_assignment == DEVICE_IP_ASSIGNMENT.STATIC:
            # Convert an empty string to None.
            ip_address = params.get("ip_address")
            if not ip_address:
                ip_address = None

            # Link to the subnet statically.
            subnet = Subnet.objects.get(id=params["subnet"])
            interface.link_subnet(
                INTERFACE_LINK_TYPE.STATIC, subnet, ip_address=ip_address)

    def create(self, params):
        """Create the object from params."""
        # XXX blake_r 03-04-15 bug=1440102: This is very ugly and a repeat
        # of code in other places. Needs to be refactored.

        # Create the object with the form and then create all of the interfaces
        # based on the users choices.
        data = super(DeviceHandler, self).create(params)
        device_obj = Device.objects.get(system_id=data['system_id'])
        interfaces = list(device_obj.interface_set.all())

        # Acquire all of the needed ip address based on the user selection.
        for nic in params["interfaces"]:
            interface = get_Interface_from_list(interfaces, nic["mac"])
            self._configure_interface(interface, nic)
        return self.full_dehydrate(device_obj)

    def create_interface(self, params):
        """Create an interface on a device."""
        device = self.get_object(params)
        form = PhysicalInterfaceForm(node=device, data=params)
        if form.is_valid():
            interface = form.save()
            self._configure_interface(interface, params)
            return self.full_dehydrate(reload_object(device))
        else:
            raise HandlerValidationError(form.errors)

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
