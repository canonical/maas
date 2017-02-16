# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Preseed generation for curtin network."""

__all__ = [
    ]

from collections import defaultdict
from operator import attrgetter

from maasserver.dns.zonegenerator import get_dns_search_paths
from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_FAMILY,
    IPADDRESS_TYPE,
)
from maasserver.models import Interface
from maasserver.models.staticroute import StaticRoute
from netaddr import IPAddress
import yaml


def _is_link_up(addresses):
    """Return True if the interface should be in LINK_UP mode.

    :param addresses: A list of StaticIPAddress model objects.
    """
    if len(addresses) == 0:
        return True
    elif len(addresses) == 1:
        address = addresses[0]
        if address.alloc_type == IPADDRESS_TYPE.STICKY and not address.ip:
            return True
    return False


def _get_param_value(value):
    """Return correct value based on type of `value`."""
    if isinstance(value, (bytes, str)):
        return value
    elif isinstance(value, bool):
        return 1 if value else 0
    else:
        return value


def _generate_route_operation(route):
    """Generate route operation place in `network_config`."""
    route_operation = {
        "id": route.id,
        "type": "route",
        "destination": route.destination.cidr,
        "gateway": route.gateway_ip,
        "metric": route.metric,
    }
    return route_operation


class InterfaceConfiguration:

    def __init__(self, iface, node_config):
        """

        :param iface: The interface whose configuration to generate.
        :param routes: Static routes present on the system.
        """
        self.iface = iface
        self.type = iface.type
        self.id = iface.id
        self.node_config = node_config
        self.routes = node_config.routes
        self.gateways = node_config.gateways
        self.matching_routes = set()
        self.addr_family_present = defaultdict(bool)
        self.config = None

        if self.type == INTERFACE_TYPE.PHYSICAL:
            self.config = self._generate_physical_operation()
        elif self.type == INTERFACE_TYPE.VLAN:
            self.config = self._generate_vlan_operation()
        elif self.type == INTERFACE_TYPE.BOND:
            self.config = self._generate_bond_operation()
        elif self.type == INTERFACE_TYPE.BRIDGE:
            self.config = self._generate_bridge_operation()
        else:
            raise ValueError("Unknown interface type: %s" % self.type)

    def _generate_physical_operation(self):
        """Generate physical interface operation for `interface` and place in
        `network_config`."""
        addrs = self._generate_addresses()
        physical_operation = self._get_initial_params()
        physical_operation.update({
            "id": self.iface.get_name(),
            "type": "physical",
            "name": self.iface .get_name(),
            "mac_address": str(self.iface .mac_address),
        })
        if addrs:
            physical_operation["subnets"] = addrs
        return physical_operation

    def _get_dhcp_type(self):
        """Return the DHCP type for the interface."""
        dhcp_types = set()
        for dhcp_ip in self.iface.ip_addresses.filter(
                alloc_type=IPADDRESS_TYPE.DHCP).select_related("subnet"):
            if dhcp_ip.subnet is None:
                # No subnet is linked so no IP family can be determined. So
                # we allow both families to be DHCP'd.
                dhcp_types.add(4)
                dhcp_types.add(6)
                self.addr_family_present[4] = True
                self.addr_family_present[6] = True
            else:
                dhcp_types.add(dhcp_ip.subnet.get_ipnetwork().version)
        if dhcp_types == {4, 6}:
            self.addr_family_present[4] = True
            self.addr_family_present[6] = True
            return "dhcp"
        elif dhcp_types == {4}:
            self.addr_family_present[4] = True
            return "dhcp4"
        elif dhcp_types == {6}:
            self.addr_family_present[6] = True
            return "dhcp6"
        else:
            return None

    def _get_default_gateway(self, subnet):
        """Return True if this is the gateway that should be added to the
        interface configuration."""
        if subnet.gateway_ip:
            for gateway in self.gateways:
                if gateway is not None:
                    iface_id, subnet_id, gateway_ip = gateway
                    if (iface_id == self.id and
                            subnet_id and subnet.id and
                            gateway_ip and subnet.gateway_ip):
                        return subnet.gateway_ip
        return None

    def _set_default_gateway(self, subnet, subnet_operation):
        """Set the default gateway on the `subnet_operation` if it should
        be set."""
        family = subnet.get_ipnetwork().version
        node_config = self.node_config
        if family == IPADDRESS_FAMILY.IPv4 and node_config.gateway_ipv4_set:
            return
        elif family == IPADDRESS_FAMILY.IPv6 and node_config.gateway_ipv6_set:
            return
        gateway = self._get_default_gateway(subnet)
        if gateway is not None:
            if family == IPADDRESS_FAMILY.IPv4:
                node_config.gateway_ipv4_set = True
            elif family == IPADDRESS_FAMILY.IPv6:
                node_config.gateway_ipv6_set = True
            subnet_operation["gateway"] = str(gateway)

    def _get_matching_routes(self, source):
        """Return all route objects matching `source`."""
        return {
            route
            for route in self.routes
            if route.source == source
        }

    def _generate_addresses(self):
        """Generate the various addresses needed for this interface."""
        addrs = []
        addresses = list(
            self.iface.ip_addresses.exclude(
                alloc_type__in=[
                    IPADDRESS_TYPE.DISCOVERED,
                    IPADDRESS_TYPE.DHCP,
                ]).order_by('id'))
        dhcp_type = self._get_dhcp_type()
        if _is_link_up(addresses) and not dhcp_type:
            addrs.append({"type": "manual"})
        else:
            for address in addresses:
                subnet = address.subnet
                if subnet is not None:
                    subnet_len = subnet.cidr.split('/')[1]
                    subnet_operation = {
                        "type": "static",
                        "address": "%s/%s" % (str(address.ip), subnet_len)
                    }
                    self.addr_family_present[
                        IPAddress(address.ip).version] = True
                    self._set_default_gateway(
                        subnet, subnet_operation)
                    if subnet.dns_servers is not None:
                        subnet_operation["dns_nameservers"] = (
                            subnet.dns_servers)
                    addrs.append(subnet_operation)
                    self.matching_routes.update(
                        self._get_matching_routes(subnet))
            if dhcp_type:
                addrs.append(
                    {"type": dhcp_type}
                )
        return addrs

    def _generate_vlan_operation(self):
        """Generate vlan operation for `iface` and place in
        `network_config`."""
        vlan = self.iface.vlan
        name = self.iface.get_name()
        addrs = self._generate_addresses()
        vlan_operation = self._get_initial_params()
        vlan_operation.update({
            "id": name,
            "type": "vlan",
            "name": name,
            "vlan_link": self.iface.parents.first().get_name(),
            "vlan_id": vlan.vid,
        })
        if addrs:
            vlan_operation["subnets"] = addrs
        return vlan_operation

    def _generate_bond_operation(self):
        """Generate bond operation for `iface` and place in
        `network_config`."""
        addrs = self._generate_addresses()
        bond_operation = self._get_initial_params()
        bond_operation.update({
            "id": self.iface.get_name(),
            "type": "bond",
            "name": self.iface.get_name(),
            "mac_address": str(self.iface.mac_address),
            "bond_interfaces": [parent.get_name() for parent in
                                self.iface.parents.order_by('name')],
            "params": self._get_bond_params(),
        })
        if addrs:
            bond_operation["subnets"] = addrs
        return bond_operation

    def _generate_bridge_operation(self):
        """Generate bridge operation for this interface."""
        addrs = self._generate_addresses()
        bridge_operation = self._get_initial_params()
        bridge_operation.update({
            "id": self.iface.get_name(),
            "type": "bridge",
            "name": self.iface.get_name(),
            "mac_address": str(self.iface.mac_address),
            "bridge_interfaces": [parent.get_name() for parent in
                                  self.iface.parents.order_by('name')],
            "params": self._get_bridge_params(),
        })
        if addrs:
            bridge_operation["subnets"] = addrs
        return bridge_operation

    def _get_initial_params(self):
        """Return the starting parameters for the interface.

        This is done by extracting parameters from the `params` property on
        the `interface`. This is done before all the other parameters are added
        so any colliding parameters will be overridden.
        """
        params = {}
        if self.iface.params:
            for key, value in self.iface.params.items():
                # Don't include bond or bridge parameters.
                if (not key.startswith("bond_") and
                        not key.startswith("bridge_") and
                        key != 'mtu'):
                    params[key] = _get_param_value(value)
        params['mtu'] = self.iface.get_effective_mtu()
        return params

    def _get_bond_params(self):
        params = {}
        if self.iface.params:
            for key, value in self.iface.params.items():
                # Only include bond parameters.
                if key.startswith("bond_"):
                    # Bond parameters are seperated with '-' instead of '_'
                    # which MAAS uses to keep consistent with bridges.
                    params[key.replace("bond_", "bond-")] = (
                        _get_param_value(value))
        return params

    def _get_bridge_params(self):
        params = {}
        if self.iface.params:
            for key, value in self.iface.params.items():
                # Only include bridge parameters.
                if key.startswith("bridge_"):
                    params[key] = _get_param_value(value)
        return params


class NodeNetworkConfiguration:
    """Generator for the YAML network configuration for curtin."""

    def __init__(self, node):
        """Create the YAML network configuration for the specified node, and
        store it in the `config` ivar.
        """
        self.node = node
        self.matching_routes = set()
        self.network_config = []
        self.gateway_ipv4_set = False
        self.gateway_ipv6_set = False
        # The default value is False: expected keys are 4 and 6.
        self.addr_family_present = defaultdict(bool)

        self.gateways = self.node.get_default_gateways()
        self.routes = StaticRoute.objects.all()

        interfaces = Interface.objects.all_interfaces_parents_first(self.node)
        for iface in interfaces:
            if not iface.is_enabled():
                continue
            generator = InterfaceConfiguration(iface, self)
            self.matching_routes.update(generator.matching_routes)
            self.addr_family_present.update(generator.addr_family_present)
            self.network_config.append(generator.config)

        # Generate each YAML operation in the network_config.
        self._generate_route_operations()

        # If we have no IPv6 addresses present, make sure we claim IPv4, so
        # that we at least get some address.
        if not self.addr_family_present[6]:
            self.addr_family_present[4] = True
        default_dns_servers = self.node.get_default_dns_servers(
            ipv4=self.addr_family_present[4], ipv6=self.addr_family_present[6])
        search_list = [self.node.domain.name] + [
            name
            for name in sorted(get_dns_search_paths())
            if name != self.node.domain.name]
        self.network_config.append({
            "type": "nameserver",
            "address": default_dns_servers,
            "search": search_list,
        })

        network_config = {
            "network_commands": {
                "builtin": ["curtin", "net-meta", "custom"],
            },
            "network": {
                "version": 1,
                "config": self.network_config,
            },
        }
        # Render the resulting YAML.
        self.config = yaml.safe_dump(network_config, default_flow_style=False)

    def _generate_route_operations(self):
        """Generate all route operations."""
        for route in sorted(self.matching_routes, key=attrgetter("id")):
            self.network_config.append(_generate_route_operation(route))


def compose_curtin_network_config(node):
    """Compose the network configuration for curtin."""
    generator = NodeNetworkConfiguration(node)
    return [generator.config]
