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

from textwrap import dedent

from netaddr import IPAddress


def extract_ip_from_sequence(ips, ip_version):
    """Return the first address for the given IP version from `ips`.

    :param ips: A sequence of IP address strings.
    :param ip_version: Either 4 or 6 (for IPv4 or IPv6 respectively).  Only an
        address for this version will be returned.
    :return: A matching IP address, or `None`.
    """
    for ip in ips:
        if IPAddress(ip).version == ip_version:
            return ip
    return None


def extract_ip(mapping, mac, ip_version):
    """Extract IP address for `mac` and given IP version from `mapping`.

    :param mapping: A dict mapping MAC addresses to iterables of IP addresses,
        each with at most one IPv4 and at most one IPv6 address.
    :param mac: A MAC address.
    :param ip_version: Either 4 or 6 (for IPv4 or IPv6 respectively).  Only an
        address for this version will be returned.
    :return: A matching IP address, or `None`.
    """
    return extract_ip_from_sequence(mapping.get(mac, []), ip_version)


def compose_ipv4_stanza(interface, disable=False):
    """Return a Debian `/etc/network/interfaces` stanza for DHCPv4.

    :param interface: Name of the network interface whose configuration should
        be generated.
    :param disable: If `True`, generate a stanza to disable the IPv4 address.
        If `False` (the default), generate a DHCP stanza.
    :return: Text of the interface's IPv4 address configuration stanza.
    """
    if disable:
        return dedent("""\
            # MAAS was configured to disable IPv4 networking on this node.
            iface %s inet static
            \tnetmask 255.255.255.255
            \taddress 0.0.0.0
            """.rstrip()) % interface
    else:
        return "iface %s inet dhcp" % interface


def compose_ipv6_stanza(interface, ip, gateway=None, nameserver=None):
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
    if nameserver is not None:
        # Actually this keyword accepts up to 2 nameservers.
        lines.append('\tdns-nameservers %s' % nameserver)
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
                               gateways_mapping, disable_ipv4=False,
                               nameservers=None, netmasks=None):
    """Return contents for a node's `/etc/network/interfaces` file.

    :param interfaces: A list of interface/MAC pairs for the node.
    :param auto_interfaces: A list of MAC addresses whose network interfaces
        should come up automatically on node boot.
    :param ips_mapping: A dict mapping MAC addresses to containers of the
        corresponding network interfaces' IP addresses.
    :param gateways_mapping: A `defaultdict` mapping MAC addresses to
        containers of the corresponding network interfaces' default gateways.
    :param disable_ipv4: Should this node be installed without IPv4 networking?
    :param nameservers: Optional list of DNS servers.
    :param netmasks: Optional dict mapping MAC IP addresses from `ips_mapping`
        to their respective netmask strings.
    """
    if nameservers is None:
        ipv6_nameserver = None
    else:
        ipv6_nameserver = extract_ip_from_sequence(nameservers, 6)
    if netmasks is None:
        netmasks = {}

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
        if mac in auto_interfaces:
            stanzas.append('auto %s' % interface)
        stanzas.append(compose_ipv4_stanza(interface, disable=disable_ipv4))
        static_ipv6 = extract_ip(ips_mapping, mac, 6)
        if static_ipv6 is not None:
            gateway = extract_ip(gateways_mapping, mac, 6)
            stanzas.append(
                compose_ipv6_stanza(
                    interface, static_ipv6, gateway=gateway,
                    nameserver=ipv6_nameserver))
    return '%s\n' % '\n\n'.join(stanzas)
