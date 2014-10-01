# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Code to configure networking on Debian-like operating systems."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'compose_network_interfaces',
    ]

from netaddr import IPAddress


def extract_ip(mapping, mac, ip_version):
    """Extract IP address for `mac` and given IP version from `mapping`.

    :param mapping: A dict mapping MAC addresses to iterables of IP addresses,
        each with at most one IPv4 and at most one IPv6 address.
    :param mac: A MAC address.
    :param ip_version: Either 4 or 6 (for IPv4 or IPv6 respectively).  Only an
        address for this version will be returned.
    :return: A matching IP address, or `None`.
    """
    for ip in mapping.get(mac, []):
        if IPAddress(ip).version == ip_version:
            return ip
    return None


def compose_ipv4_stanza(interface):
    """Return a Debian `/etc/network/interfaces` stanza for DHCPv4."""
    return "iface %s inet dhcp" % interface


def compose_ipv6_stanza(interface, ip, gateway=None):
    """Return a Debian `/etc/network/interfaces` stanza for IPv6.

    The stanza will configure a static address.
    """
    lines = [
        'iface %s inet6 static' % interface,
        '\tnetmask 64',
        '\taddress %s' % ip,
        ]
    if gateway is not None:
        lines.append('\tgateway %s' % gateway)
    return '\n'.join(lines)


def has_static_ipv6_address(mapping):
    """Does `mapping` contain an IPv6 address?

    :param mapping: A dict mapping MAC addresses to containers of IP addresses.
    :return: Boolean: is any of the IP addresses and IPv6 address?
    """
    for ips in mapping.values():
        for ip in ips:
            if IPAddress(ip).version == 6:
                return True
    return False


def compose_network_interfaces(interfaces, auto_interfaces, ips_mapping,
                               gateways_mapping, disable_ipv4=False):
    """Return contents for a node's `/etc/network/interfaces` file.

    :param interfaces: A list of interface/MAC pairs for the node.
    :param auto_interfaces: A list of MAC addresses whose network interfaces
        should come up automatically on node boot.
    :param ips_mapping: A dict mapping MAC addresses to containers of the
        corresponding network interfaces' IP addresses.
    :param gateways_mapping: A `defaultdict` mapping MAC addresses to
        containers of the corresponding network interfaces' default gateways.
    :param disable_ipv4: Should this node be installed without IPv4 networking?
    """
    # Should we disable IPv4 on this node?  For safety's sake, we won't do this
    # if the node has no static IPv6 addresses.  Otherwise it might become
    # accidentally unaddressable: it may have IPv6 addresses, but apart from
    # being able to guess autoconfigured addresses, we won't know what they
    # are.
    disable_ipv4 = (disable_ipv4 and has_static_ipv6_address(ips_mapping))
    stanzas = [
        'auto lo',
        ]
    for interface, mac in interfaces:
        stanzas.append('auto %s' % interface)
        if not disable_ipv4:
            stanzas.append(compose_ipv4_stanza(interface))
        static_ipv6 = extract_ip(ips_mapping, mac, 6)
        if static_ipv6 is not None:
            gateway = extract_ip(gateways_mapping, mac, 6)
            stanzas.append(
                compose_ipv6_stanza(interface, static_ipv6, gateway))
    return '%s\n' % '\n\n'.join(stanzas)
