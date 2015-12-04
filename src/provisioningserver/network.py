# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Discover networks attached to this cluster controller.

A cluster controller uses this when registering itself with the region
controller.
"""

__all__ = [
    'discover_networks',
    ]

from itertools import chain
import json
from operator import attrgetter

from netaddr import (
    IPAddress,
    IPNetwork,
)
from netifaces import (
    AF_INET,
    AF_INET6,
    ifaddresses,
    interfaces,
)
from provisioningserver.utils.ipaddr import (
    annotate_with_driver_information,
    parse_ip_addr,
)
from provisioningserver.utils.network import clean_up_netifaces_address
from provisioningserver.utils.shell import call_and_check


class AttachedNetwork:
    """A network as found attached to a network interface."""

    def __init__(self, interface, ip=None, subnet_mask=None):
        self.interface = interface
        self.ip = ip
        self.subnet_mask = subnet_mask

    @classmethod
    def from_address(cls, interface_name, address):
        """Construct `AttachedNetwork` from address as found by `netifaces`."""
        addr = address.get('addr')
        if addr is not None:
            addr = clean_up_netifaces_address(addr, interface_name)
        return cls(interface_name, ip=addr, subnet_mask=address.get('netmask'))

    def is_relevant(self):
        """Could this be a network that MAAS is interested in?"""
        if self.interface == 'lo':
            # Loopback device.  Not useful for nodes.
            return False
        if self.ip is None:
            # Interface has no address.  Not usable.
            return False
        ipaddress = IPAddress(self.ip)
        if ipaddress.version == 4 and not self.subnet_mask:
            # IPv4 network has no broadcast address configured.  Not usable.
            return False
        if ipaddress.is_link_local():
            # Link-local address.  MAAS doesn't know how to manage these.
            return False
        # Met all these requirements?  Then this is a relevant network.
        return True

    def as_dict(self):
        """Return information as a dictionary.

        The return value's format is suitable as an interface description
        for use with the `register` API call.
        """
        return {
            'interface': self.interface,
            'ip': self.ip,
            'subnet_mask': self.subnet_mask,
        }

    def get_ip_network(self):
        """Return `IPNetwork` for this network."""
        return IPNetwork('%s/%s' % (self.ip, self.subnet_mask)).cidr


def get_interface_info(interface):
    """Return a list of `AttachedNetwork` for the named `interface`."""
    ipv4_addrs = ifaddresses(interface).get(AF_INET, [])
    ipv6_addrs = ifaddresses(interface).get(AF_INET6, [])
    return [
        AttachedNetwork.from_address(interface, address)
        for address in ipv4_addrs + ipv6_addrs
        ]


def filter_unique_networks(networks):
    """Return only distinct networks out of `networks`.

    If two entries are on the same network (even if the entries' IP addresses
    differ), only one of them will be returned.

    :param networks: Iterable of `AttachedNetwork` that pass the
        `is_relevant` test.
    :return: List of `AttachedNetwork`.
    """
    known_ip_networks = set()
    unique_networks = []
    for network in sorted(networks, key=attrgetter('ip')):
        ip_network = network.get_ip_network()
        if ip_network not in known_ip_networks:
            unique_networks.append(network)
            known_ip_networks.add(ip_network)
    return unique_networks


def discover_networks():
    """Find the networks attached to this system.

    :return: A list of dicts, each containing keys `interface`, `ip`, and
        `subnet_mask`.
    """
    networks = chain.from_iterable(
        get_interface_info(interface) for interface in interfaces())
    networks = [network for network in networks if network.is_relevant()]
    networks = filter_unique_networks(networks)
    return [network.as_dict() for network in networks]


def get_ip_addr_json():
    """Returns this system's local IP address information, in JSON format.

    :raises:ExternalProcessError: if IP address information could not be
        gathered.
    """
    ip_addr_output = call_and_check(["/sbin/ip", "addr"])
    ifaces = parse_ip_addr(ip_addr_output)
    ifaces = annotate_with_driver_information(ifaces)
    ip_addr_json = json.dumps(ifaces)
    return ip_addr_json


def _filter_managed_networks_by_ifname(networks):
    """
    Given the specified list of networks, filters the list of networks and
    returns any that may be physical interfaces (based on the interface name).

    :param networks: A list of network dictionaries. Must contain an
        'interface' key containing the interface name.
    :return: The filtered list.
    """
    return [
        network
        for network in networks
        if 'interface' in network and
           (network['interface'].startswith('eth') or
            network['interface'].startswith('en') or
            network['interface'].startswith('em') or
            network['interface'].startswith('vlan') or
            network['interface'].startswith('bond'))
        ]


def _annotate_network_with_interface_information(network, addr_info):
    """Adds a 'type' field to a specified dictionary which represents a network
    interface.
    """
    iface = addr_info.get(network['interface'], None)
    if iface is not None and 'type' in iface:
        network['type'] = iface['type']
        if 'vid' in iface:
            network['vid'] = iface['vid']
        if 'bridged_interfaces' in iface:
            network['bridged_interfaces'] = ' '.join(
                iface['bridged_interfaces'])
        if 'bonded_interfaces' in iface:
            network['bonded_interfaces'] = ' '.join(
                iface['bonded_interfaces'])
        if 'parent' in iface:
            network['parent'] = iface['parent']
    return network


def _bridges_a_physical_interface(ifname, addr_info):
    """Returns True if the bridge interface with the specified name bridges
    at least one physical Ethernet interface. Otherwise, returns False.
    """
    bridge_interface = addr_info.get(ifname)
    for interface_name in bridge_interface.get('bridged_interfaces', []):
        iface = addr_info.get(interface_name, {})
        if iface.get('type') == 'ethernet.physical':
            return True
    return False


def _belongs_to_a_vlan(ifname, addr_info):
    """Returns True if the interface with the specified name is needed
    because a VLAN interface depends on it.
    """
    for interface_name in addr_info:
        iface = addr_info.get(interface_name, {})
        if iface.get('type') == 'ethernet.vlan':
            if iface.get('parent') == ifname:
                return True
    return False


def _network_name(network):
    """Returns interface name for the specified network. (removes a trailing
    alias, if present.)
    """
    return network['interface'].split(':')[0]


def _should_manage_network(network, addr_info):
    """Returns True if this network should be managed; otherwise returns False.
    """
    ifname = _network_name(network)
    addrinfo = addr_info.get(ifname, {})
    iftype = addrinfo.get('type', '')
    # In general, only physical Ethernet interfaces, VLANs, and bonds
    # are going to be managed. Since they are most likely irrelevant, (and
    # we don't want them to create superfluous subnets) filter out virtual
    # interfaces (whose specific type cannot be determined) and bridges.
    # However, reconsider bridges as "possibly managed" if they are
    # present in support of a physical Ethernet device, or a VLAN is
    # defined on top of the bridge.
    return (
        addrinfo and
        (_belongs_to_a_vlan(ifname, addr_info) or
         iftype == 'ethernet.physical' or
         iftype == 'ethernet.vlan' or
         iftype == 'ethernet.bond' or
         (iftype == 'ethernet.bridge' and
          _bridges_a_physical_interface(ifname, addr_info))
         )
    )


def _filter_and_annotate_managed_networks(networks, ip_addr_json):
    """
    Given the specified list of networks and corresponding JSON, filters
    the list of networks and returns any that are known to be physical
    interfaces. (based on driver information gathered from /sys)

    Also annotates the list of networks with each network's type.

    :param networks: A list of network dictionaries. Must contain an
        'interface' key containing the interface name.
    :param ip_addr_json: A JSON string returned from `get_ip_addr_json()`.
    :return: The filtered list.
    """
    addr_info = json.loads(ip_addr_json)
    assert isinstance(addr_info, dict)
    return [
        _annotate_network_with_interface_information(network, addr_info)
        for network in networks
        if _should_manage_network(network, addr_info)
        ]


def filter_and_annotate_networks(networks, ip_addr_json=None):
    """
    Given the specified list of networks and optional corresponding JSON,
    filters the list of networks and returns any that may correspond to managed
    networks. (that is, any physical Ethernet interfaces, plus bonds and
    VLANs.)

    If no interfaces are found, fall back to using the interface name to
    filter the list in a reasonable manner. (this allows support for running
    on LXCs, where all interfaces may be virtual.)

    Also annotates the list of networks with their type, and other metadata
    such as VLAN VID, bonded/bridged interfaces, or parent.

    :param networks: A list of network dictionaries. Must contain an
        'interface' key containing the interface name.
    :param ip_addr_json: A JSON string returned from `get_ip_addr_json()`.
    :return: The filtered list.
    """
    assert networks is not None
    if ip_addr_json is None:
        return _filter_managed_networks_by_ifname(networks)
    else:
        physical_networks = _filter_and_annotate_managed_networks(
            networks, ip_addr_json)
        if len(physical_networks) > 0:
            return physical_networks
        else:
            # Since we couldn't find anything, fall back to using the heuristic
            # based on names. (we could be running inside a container with only
            # virtual interfaces, etc.)
            return _filter_managed_networks_by_ifname(
                networks)


def _get_interface_type_priority(iface):
    """Returns a sort key based on interface types we prefer to process
    first when adding them to a NodeGroup.

    The most important thing is that we need to process VLANs last, since they
    require the underlying Fabric to be created first.
    """
    iftype = iface.get('type')
    # Physical interfaces first, followed by bonds, followed by bridges.
    # VLAN interfaces last.
    # This will ensure that underlying Fabric objects can be created before
    # any VLANs that may belong to each Fabric.
    if iftype == "ethernet.physical":
        return 0
    elif iftype == "ethernet.wireless":
        return 1
    elif iftype == "ethernet":
        return 2
    elif iftype == "ethernet.bond":
        return 3
    elif iftype == "ethernet.bridge":
        return 4
    elif iftype == "ethernet.vlan":
        return 5
    else:
        # We don't really care what the sort order is; they should be filtered
        # out anyway.
        return -1


def _network_priority_sort_key(iface):
    """Returns a sort key used for processing interfaces before adding them
    to a NodeGroup.

    First sorts by interface type, then interface name, then address family.
    (Since MAAS usually manages IPv4 addresses, and we have a name
    disambiguation funciton that can produce somewhat unfriendly names,
    make sure the IPv4 interfaces get to go first.)
    """
    return (
        _get_interface_type_priority(iface),
        iface['interface'],
        IPAddress(iface['ip']).version
    )


def sort_networks_by_priority(networks):
    """Sorts the specified list of networks in the order in which we would
    prefer to add them to a NodeGroup."""
    return sorted(networks, key=_network_priority_sort_key)
