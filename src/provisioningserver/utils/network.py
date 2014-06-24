# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generic helpers for `netaddr` and network-related types."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'find_ip_via_arp',
    'find_mac_via_arp',
    'make_network',
    ]


from netaddr import (
    IPAddress,
    IPNetwork,
    )
import netifaces
from provisioningserver.utils import call_and_check


def make_network(ip_address, netmask_or_bits, **kwargs):
    """Construct an `IPNetwork` with the given address and netmask or width.

    This is a thin wrapper for the `IPNetwork` constructor.  It's here because
    the constructor for `IPNetwork` is easy to get wrong.  If you pass it an
    IP address and a netmask, or an IP address and a bit size, it will seem to
    work... but it will pick a default netmask, not the one you specified.

    :param ip_address:
    :param netmask_or_bits:
    :param kwargs: Any other (keyword) arguments you want to pass to the
        `IPNetwork` constructor.
    :raise netaddr.core.AddrFormatError: If the network specification is
        malformed.
    :return: An `IPNetwork` of the given base address and netmask or bit width.
    """
    return IPNetwork("%s/%s" % (ip_address, netmask_or_bits), **kwargs)


def find_ip_via_arp(mac):
    """Find the IP address for `mac` by reading the output of arp -n.

    Returns `None` if the MAC is not found.

    We do this because we aren't necessarily the only DHCP server on the
    network, so we can't check our own leases file and be guaranteed to find an
    IP that matches.

    :param mac: The mac address, e.g. '1c:6f:65:d5:56:98'.
    """

    output = call_and_check(['arp', '-n']).split('\n')

    for line in sorted(output):
        columns = line.split()
        if len(columns) == 5 and columns[2] == mac:
            return columns[0]
    return None


def find_mac_via_arp(ip):
    """Find the MAC address for `ip` by reading the output of arp -n.

    Returns `None` if the IP is not found.

    We do this because we aren't necessarily the only DHCP server on the
    network, so we can't check our own leases file and be guaranteed to find an
    IP that matches.

    :param ip: The ip address, e.g. '192.168.1.1'.
    """
    # Normalise ip.  IPv6 has a wealth of alternate notations, so we can't
    # just look for the string; we have to parse.
    ip = IPAddress(ip)
    # Use "C" locale; we're parsing output so we don't want any translations.
    output = call_and_check(['ip', 'neigh'], env={'LC_ALL': 'C'})

    for line in sorted(output.splitlines()):
        columns = line.split()
        if len(columns) < 4:
            raise Exception(
                "Output line from 'ip neigh' does not look like a neighbour "
                "entry: '%s'" % line)
        # Normal "ip neigh" output lines look like:
        #   <IP> dev <interface> lladdr <MAC> [router] <status>
        #
        # Where <IP> is an IPv4 or IPv6 address, <interface> is a network
        # interface name such as eth0, <MAC> is a MAC address, and status
        # can be REACHABLE, STALE, etc.
        #
        # However sometimes you'll also see lines like:
        #   <IP> dev <interface>  FAILED
        #
        # Note the missing lladdr entry.
        if IPAddress(columns[0]) == ip and columns[3] == 'lladdr':
            # Found matching IP address.  Return MAC.
            return columns[4]
    return None


def get_all_interface_addresses():
    """For each network interface, yield its IPv4 address."""
    for interface in netifaces.interfaces():
        addresses = netifaces.ifaddresses(interface)
        if netifaces.AF_INET in addresses:
            for inet_address in addresses[netifaces.AF_INET]:
                if "addr" in inet_address:
                    yield inet_address["addr"]
