# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
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
from provisioningserver.utils.network import clean_up_netifaces_address


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
        if IPAddress(self.ip).version == 4 and not self.subnet_mask:
            # IPv4 network has no broadcast address configured.  Not usable.
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


# Feature flag: reveal IPv6 capabilities to the user?
#
# While this is set to False, MAAS will not auto-detect IPv6 networks.
REVEAL_IPv6 = False


def get_interface_info(interface):
    """Return a list of `AttachedNetwork` for the named `interface`."""
    ipv4_addrs = ifaddresses(interface).get(AF_INET, [])
    if REVEAL_IPv6:
        ipv6_addrs = ifaddresses(interface).get(AF_INET6, [])
    else:
        ipv6_addrs = []
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
