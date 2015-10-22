# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Discover networks attached to this cluster controller.

A cluster controller uses this when registering itself with the region
controller.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
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


def _filter_likely_physical_networks_using_interface_name(networks):
    """
    Given the specified list of networks and corresponding JSON, filters
    the list of networks and returns any that may be physical interfaces
    (based on the interface name).

    :param networks: A list of network dictionaries. Must contain an
        'interface' key containing the interface name.
    :return: The filtered list.
    """
    return [
        network
        for network in networks
        if 'interface' in network and
           (network['interface'].startswith('eth') or
            network['interface'].startswith('em') or
            network['interface'].startswith('vlan') or
            network['interface'].startswith('bond'))
        ]


def _filter_likely_physical_networks_using_json_data(networks, ip_addr_json):
    """
    Given the specified list of networks and corresponding JSON, filters
    the list of networks and returns any that are known to be physical
    interfaces. (based on driver information gathered from /sys)

    :param networks: A list of network dictionaries. Must contain an
        'interface' key containing the interface name.
    :param ip_addr_json: A JSON string returned from `get_ip_addr_json()`.
    :return: The filtered list.
    """
    addr_info = json.loads(ip_addr_json)
    assert isinstance(addr_info, dict)
    return [
        network
        for network in networks
        if (network['interface'] in addr_info and
            'type' in addr_info[network['interface']] and
            (addr_info[network['interface']]['type'] == 'ethernet.physical' or
             addr_info[network['interface']]['type'] == 'ethernet.vlan' or
             addr_info[network['interface']]['type'] == 'ethernet.bond'))
        ]


def filter_likely_unmanaged_networks(networks, ip_addr_json=None):
    """
    Given the specified list of networks and optional corresponding JSON,
    filters the list of networks and returns any that are known to be physical
    interfaces.

    If no interfaces are found, fall back to using the interface name to
    filter the list in a reasonable manner. (this allows support for running
    on LXCs, where all interfaces may be virtual.)

    :param networks: A list of network dictionaries. Must contain an
        'interface' key containing the interface name.
    :param ip_addr_json: A JSON string returned from `get_ip_addr_json()`.
    :return: The filtered list.
    """
    assert networks is not None
    if ip_addr_json is None:
        return _filter_likely_physical_networks_using_interface_name(networks)
    else:
        physical_networks = _filter_likely_physical_networks_using_json_data(
            networks, ip_addr_json)
        if len(physical_networks) > 0:
            return physical_networks
        else:
            # Since we couldn't find anything, fall back to using the heuristic
            # based on names. (we could be running inside a container with only
            # virtual interfaces, etc.)
            return _filter_likely_physical_networks_using_interface_name(
                networks)
