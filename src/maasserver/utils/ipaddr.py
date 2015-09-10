# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utility to parse 'ip addr [show]'.

Example dictionary returned by parse_ip_link():

{u'eth0': {u'flags': set([u'BROADCAST', u'LOWER_UP', u'MULTICAST', u'UP']),
           u'index': 2,
           u'mac': u'80:fa:5c:0d:43:5e',
           u'name': u'eth0',
           u'inet': [u'192.168.0.3/24', '172.16.43.1/24'],
           u'inet6': [u'fe80::3e97:eff:fe0e:56dc/64'],
           u'settings': {u'group': u'default',
                         u'mode': u'DEFAULT',
                         u'mtu': u'1500',
                         u'qdisc': u'pfifo_fast',
                         u'qlen': u'1000',
                         u'state': u'UP'}},
 u'lo': {u'flags': set([u'LOOPBACK', u'LOWER_UP', u'UP']),
         u'index': 1,
         u'name': u'lo',
         u'inet': u'127.0.0.1/8',
         u'inet6': u'::1/128',
         u'settings': {u'group': u'default',
                       u'mode': u'DEFAULT',
                       u'mtu': u'65536',
                       u'qdisc': u'noqueue',
                       u'state': u'UNKNOWN'}}}

The dictionary above is generated given the following input:

        1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN \
mode DEFAULT group default
            link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
            inet 127.0.0.1/8 scope host lo
                valid_lft forever preferred_lft forever
            inet6 ::1/128 scope host
                valid_lft forever preferred_lft forever
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast \
state UP mode DEFAULT group default qlen 1000
            link/ether 80:fa:5c:0d:43:5e brd ff:ff:ff:ff:ff:ff
            inet 192.168.0.3/24 brd 192.168.0.255 scope global eth0
                valid_lft forever preferred_lft forever
            inet 172.16.43.1/24 scope global eth0
                valid_lft forever preferred_lft forever
            inet6 fe80::3e97:eff:fe0e:56dc/64 scope link
                valid_lft forever preferred_lft forever
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = [
    'parse_ip_addr',
    'get_first_and_last_usable_host_in_network',
]

import re
import string

from maasserver.enum import IPADDRESS_FAMILY
from netaddr import (
    IPAddress,
    IPNetwork,
)


def _get_settings_dict(settings_line):
    """
    Given a string of the format:
        "[[<key1> <value1>] <key2> <value2>][...]"
    Returns a dictionary mapping each key to its corresponding value.
    :param settings_line: unicode
    :return: dict
    """
    settings = settings_line.strip().split()
    if len(settings) > 0 and settings[0] == "inet":
        settings = settings[:-1]
    num_tokens = len(settings)
    assert num_tokens % 2 == 0, \
        "Unexpected number of params in '%s'" % settings_line
    return {
        settings[2 * i]: settings[2 * i + 1] for i in range(num_tokens / 2)
        }


def _parse_interface_definition(line):
    """Given a string of the format:
        <interface_index>: <interface_name>: <flags> <settings>
    Returns a dictionary containing the component parts.
    :param line: unicode
    :return: dict
    :raises: ValueError if a malformed interface definition line is presented
    """
    interface = {}

    # This line is in the format:
    # <interface_index>: <interface_name>: <properties>
    [index, name, properties] = map(
        string.strip, line.split(':'))

    interface['index'] = int(index)
    interface['name'] = name

    # Now parse the <properties> part from above.
    # This will be in the form "<FLAG1,FLAG2> key1 value1 key2 value2 ..."
    matches = re.match(r"^<(.*)>(.*)", properties)
    if matches:
        flags = matches.group(1)
        if len(flags) > 0:
            flags = flags.split(',')
        else:
            flags = []
        interface['flags'] = set(flags)
        interface['settings'] = _get_settings_dict(matches.group(2))
    else:
        raise ValueError("Malformed 'ip addr' line (%s)" % line)
    return interface


def _add_additional_interface_properties(interface, line):
    """
    Given the specified interface and a specified follow-on line containing
    more interface settings, adds any additional settings to the interface
    dictionary. (currently, the only relevant setting is the interface MAC.)
    :param interface: dict
    :param line: unicode
    """
    settings = _get_settings_dict(line)
    mac = settings.get('link/ether')
    if mac is not None:
        interface['mac'] = mac
    cumul_settings = ['inet', 'inet6']
    for name in cumul_settings:
        value = settings.get(name)
        if value is not None:
            if not IPNetwork(value).is_link_local():
                group = interface.setdefault(name, [])
                group.append(value)


def parse_ip_addr(output):
    """Parses the output from 'ip addr' into a dictionary.

    Given the full output from 'ip addr [show]', parses it and returns a
    dictionary mapping each interface name to its settings.

    Link-local addresses are excluded from the returned dictionary.

    :param output: string or unicode
    :return: dict
    """
    # It's possible, though unlikely, that unicode characters will appear
    # in interface names.
    if not isinstance(output, unicode):
        output = unicode(output, "utf-8")

    interfaces = {}
    interface = None
    for line in output.splitlines():
        if re.match(r'^[0-9]', line):
            interface = _parse_interface_definition(line)
            if interface is not None:
                interfaces[interface['name']] = interface
        else:
            if interface is not None:
                _add_additional_interface_properties(interface, line)
    return interfaces


def get_first_and_last_usable_host_in_network(network):
    """Return the first and last usable host in network."""
    if network.version == IPADDRESS_FAMILY.IPv4:
        return (
            IPAddress(network.first + 1, network.version),
            IPAddress(network.last - 1, network.version),
        )
    elif network.version == IPADDRESS_FAMILY.IPv6:
        return (
            IPAddress(network.first + 1, network.version),
            IPAddress(network.last, network.version),
        )
    else:
        raise ValueError("Unknown IP address family: %s" % network.version)
