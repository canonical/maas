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
from maasserver.models.staticroute import StaticRoute
from netaddr import IPAddress
import yaml


class CurtinNetworkGenerator:
    """Generator for the YAML network configuration for curtin."""

    def __init__(self, node):
        self.node = node
        self.gateways = node.get_default_gateways()
        self.routes = StaticRoute.objects.all()
        self.gateway_ipv4_set = False
        self.gateway_ipv6_set = False
        # The default value is False: expected keys are 4 and 6.
        self.addr_family_present = defaultdict(bool)
        self.operations = {
            "physical": [],
            "vlan": [],
            "bond": [],
            "bridge": [],
            "route": set(),
        }

    def generate(self):
        """Create the YAML network configuration for curtin."""
        self.network_config = []

        # Add all the items to operations.
        self._add_interface_operations()

        # Generate each YAML operation in the network_config.
        self._generate_physical_operations()
        self._generate_vlan_operations()
        self._generate_bond_operations()
        self._generate_bridge_operations()
        self._generate_route_operations()

        # Order the network_config where dependencies come first.
        self._order_config_dependency()

        # If we have no IPv6 addresses present, make sure we claim IPv4, so
        # that we at least get some address.
        if not self.addr_family_present[6]:
            self.addr_family_present[4] = True
        default_dns_servers = self.node.get_default_dns_servers(
            ipv4=self.addr_family_present[4], ipv6=self.addr_family_present[6])
        self.network_config.append({
            "type": "nameserver",
            "address": default_dns_servers,
            "search": sorted(get_dns_search_paths()),
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
        return yaml.safe_dump(network_config, default_flow_style=False)

    def _add_interface_operations(self):
        """Add all physical interface operations.

        These operations come from all of the physical interfaces attached
        to the node.
        """
        for interface in self.node.interface_set.filter(
                enabled=True).order_by('id'):
            if interface.type == INTERFACE_TYPE.PHYSICAL:
                self.operations["physical"].append(interface)
            elif interface.type == INTERFACE_TYPE.VLAN:
                self.operations["vlan"].append(interface)
            elif interface.type == INTERFACE_TYPE.BOND:
                self.operations["bond"].append(interface)
            elif interface.type == INTERFACE_TYPE.BRIDGE:
                self.operations["bridge"].append(interface)
            else:
                raise ValueError("Unknown interface type: %d" % (
                    interface.type))

    def _get_param_value(self, value):
        """Return correct value based on type of `value`."""
        if isinstance(value, (bytes, str)):
            return value
        elif isinstance(value, bool):
            return 1 if value else 0
        else:
            return value

    def _get_initial_params(self, interface):
        """Return the starting parameters for the `interface`.

        This is done by extracting parameters from the `params` property on
        the `interface`. This is done before all the other parameters are added
        so any colliding parameters will be overridden.
        """
        params = {}
        if interface.params:
            for key, value in interface.params.items():
                # Don't include bond or bridge parameters.
                if (not key.startswith("bond_") and
                        not key.startswith("bridge_") and
                        key != 'mtu'):
                    params[key] = self._get_param_value(value)
        params['mtu'] = interface.get_effective_mtu()
        return params

    def _get_bond_params(self, interface):
        params = {}
        if interface.params:
            for key, value in interface.params.items():
                # Only include bond parameters.
                if key.startswith("bond_"):
                    # Bond parameters are seperated with '-' instead of '_'
                    # which MAAS uses to keep consistent with bridges.
                    params[key.replace("bond_", "bond-")] = (
                        self._get_param_value(value))
        return params

    def _get_bridge_params(self, interface):
        params = {}
        if interface.params:
            for key, value in interface.params.items():
                # Only include bridge parameters.
                if key.startswith("bridge_"):
                    params[key] = self._get_param_value(value)
        return params

    def _generate_physical_operations(self):
        """Generate all physical interface operations."""
        for interface in self.operations["physical"]:
            self._generate_physical_operation(interface)

    def _generate_physical_operation(self, interface):
        """Generate physical interface operation for `interface` and place in
        `network_config`."""
        addrs = self._generate_addresses(interface)
        physical_operation = self._get_initial_params(interface)
        physical_operation.update({
            "id": interface.get_name(),
            "type": "physical",
            "name": interface.get_name(),
            "mac_address": str(interface.mac_address),
        })
        if addrs:
            physical_operation["subnets"] = addrs
        self.network_config.append(physical_operation)

    def _generate_vlan_operations(self):
        """Generate all partition operations."""
        for vlan_interface in self.operations["vlan"]:
            self._generate_vlan_operation(vlan_interface)

    def _get_dhcp_type(self, iface):
        """Return the DHCP type for the interface."""
        dhcp_types = set()
        for dhcp_ip in iface.ip_addresses.filter(
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
        if dhcp_types == set([4, 6]):
            self.addr_family_present[4] = True
            self.addr_family_present[6] = True
            return "dhcp"
        elif dhcp_types == set([4]):
            self.addr_family_present[4] = True
            return "dhcp4"
        elif dhcp_types == set([6]):
            self.addr_family_present[6] = True
            return "dhcp6"
        else:
            return None

    def _get_default_gateway(self, iface, subnet):
        """Return True if this is the gateway that should be added to the
        interface configuration."""
        if subnet.gateway_ip:
            for gateway in self.gateways:
                if gateway is not None:
                    iface_id, subnet_id, gateway_ip = gateway
                    if (iface_id == iface.id and
                            subnet_id and subnet.id and
                            gateway_ip and subnet.gateway_ip):
                        return subnet.gateway_ip
        return None

    def _set_default_gateway(self, iface, subnet, subnet_operation):
        """Set the default gateway on the `subnet_operation` if it should
        be set."""
        ip_family = subnet.get_ipnetwork().version
        if ip_family == IPADDRESS_FAMILY.IPv4 and self.gateway_ipv4_set:
            return
        elif ip_family == IPADDRESS_FAMILY.IPv6 and self.gateway_ipv6_set:
            return
        gateway = self._get_default_gateway(iface, subnet)
        if gateway is not None:
            if ip_family == IPADDRESS_FAMILY.IPv4:
                self.gateway_ipv4_set = True
            elif ip_family == IPADDRESS_FAMILY.IPv6:
                self.gateway_ipv6_set = True
            subnet_operation["gateway"] = str(gateway)

    def _is_link_up(self, addresses):
        """Return True if the interface is setup to be in LINK_UP mode."""
        if len(addresses) == 0:
            return True
        elif len(addresses) == 1:
            address = addresses[0]
            if address.alloc_type == IPADDRESS_TYPE.STICKY and not address.ip:
                return True
        return False

    def _get_matching_routes(self, source):
        """Return all route objects matching `source`."""
        return {
            route
            for route in self.routes
            if route.source == source
        }

    def _generate_addresses(self, iface):
        """Generate the various addresses needed for this interface."""
        addrs = []
        addresses = list(
            iface.ip_addresses.exclude(
                alloc_type__in=[
                    IPADDRESS_TYPE.DISCOVERED,
                    IPADDRESS_TYPE.DHCP,
                ]).order_by('id'))
        dhcp_type = self._get_dhcp_type(iface)
        if self._is_link_up(addresses) and not dhcp_type:
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
                    self._set_default_gateway(iface, subnet, subnet_operation)
                    if subnet.dns_servers is not None:
                        subnet_operation["dns_nameservers"] = (
                            subnet.dns_servers)
                    addrs.append(subnet_operation)
                    self.operations['route'].update(
                        self._get_matching_routes(subnet))
            if dhcp_type:
                addrs.append(
                    {"type": dhcp_type}
                )
        return addrs

    def _generate_vlan_operation(self, iface):
        """Generate vlan operation for `iface` and place in
        `network_config`."""
        vlan = iface.vlan
        name = iface.get_name()
        addrs = self._generate_addresses(iface)
        vlan_operation = self._get_initial_params(iface)
        vlan_operation.update({
            "id": name,
            "type": "vlan",
            "name": name,
            "vlan_link": iface.parents.first().get_name(),
            "vlan_id": vlan.vid,
        })
        if addrs:
            vlan_operation["subnets"] = addrs
        self.network_config.append(vlan_operation)

    def _generate_bond_operations(self):
        """Generate all bond operations."""
        for bond in self.operations["bond"]:
            self._generate_bond_operation(bond)

    def _generate_bond_operation(self, iface):
        """Generate bond operation for `iface` and place in
        `network_config`."""
        addrs = self._generate_addresses(iface)
        bond_operation = self._get_initial_params(iface)
        bond_operation.update({
            "id": iface.get_name(),
            "type": "bond",
            "name": iface.get_name(),
            "mac_address": str(iface.mac_address),
            "bond_interfaces": [parent.get_name() for parent in
                                iface.parents.order_by('id')],
            "params": self._get_bond_params(iface),
        })
        if addrs:
            bond_operation["subnets"] = addrs
        self.network_config.append(bond_operation)

    def _generate_bridge_operations(self):
        """Generate all bridge operations."""
        for bridge in self.operations["bridge"]:
            self._generate_bridge_operation(bridge)

    def _generate_bridge_operation(self, iface):
        """Generate bridge operation for `iface` and place in
        `network_config`."""
        addrs = self._generate_addresses(iface)
        bridge_operation = self._get_initial_params(iface)
        bridge_operation.update({
            "id": iface.get_name(),
            "type": "bridge",
            "name": iface.get_name(),
            "mac_address": str(iface.mac_address),
            "bridge_interfaces": [parent.get_name() for parent in
                                  iface.parents.order_by('id')],
            "params": self._get_bridge_params(iface),
        })
        if addrs:
            bridge_operation["subnets"] = addrs
        self.network_config.append(bridge_operation)

    def _generate_route_operations(self):
        """Generate all route operations."""
        for route in sorted(self.operations["route"], key=attrgetter("id")):
            self._generate_route_operation(route)

    def _generate_route_operation(self, route):
        """Generate route operation place in `network_config`."""
        route_operation = {
            "id": route.id,
            "type": "route",
            "destination": route.destination.cidr,
            "gateway": route.gateway_ip,
            "metric": route.metric,
        }
        self.network_config.append(route_operation)

    def _order_config_dependency(self):
        """Re-order the network config so dependencies appear before
        dependents."""
        # Continuously loop through the network configuration until a complete
        # pass is made without having to reorder dependencies.
        while True:
            ids_above = []
            for operation in list(self.network_config):
                operation_type = operation["type"]
                if operation_type in ["physical", "route"]:
                    # Doesn't depend on anything.
                    pass
                elif operation_type == "vlan":
                    device = operation["vlan_link"]
                    if device not in ids_above:
                        self._reorder_operation(operation, device)
                        break
                elif operation_type == "bond":
                    for parent in operation["bond_interfaces"]:
                        if parent not in ids_above:
                            self._reorder_operation(operation, parent)
                            break
                elif operation_type == "bridge":
                    for parent in operation["bridge_interfaces"]:
                        if parent not in ids_above:
                            self._reorder_operation(operation, parent)
                            break
                else:
                    raise ValueError(
                        "Unknown operation type: %s" % operation_type)
                ids_above.append(operation["id"])

            # If parsed the entire network config without breaking out of the
            # loop then all dependencies are in order.
            if len(ids_above) == len(self.network_config):
                break

    def _reorder_operation(self, operation, dependent_id):
        """Reorder the `operation` to be after `dependent_id` in the
        `network_config`."""
        # Remove the operation from the network_config.
        self.network_config.remove(operation)

        # Place the operation after the dependent in the network_config.
        dependent_idx = [
            idx
            for idx, op in enumerate(self.network_config)
            if op['id'] == dependent_id
        ][0]
        self.network_config.insert(dependent_idx + 1, operation)


def compose_curtin_network_config(node):
    """Compose the network configuration for curtin."""
    generator = CurtinNetworkGenerator(node)
    return [generator.generate()]
