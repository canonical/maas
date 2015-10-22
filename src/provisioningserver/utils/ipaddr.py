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

import os
import re
import string

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
    # Some of the tokens on this line aren't key/value pairs, but we don't
    # care about those, so strip them off if we see an odd number.
    # This will avoid an index out of bounds error below.
    num_tokens = len(settings)
    if num_tokens % 2 != 0:
        settings = settings[:-1]
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
    interface['name'] = name.split('@')[0]

    # Now parse the <properties> part from above.
    # This will be in the form "<FLAG1,FLAG2> key1 value1 key2 value2 ..."
    matches = re.match(r"^<(.*)>(.*)", properties)
    if matches:
        flags = matches.group(1)
        if len(flags) > 0:
            flags = flags.split(',')
        else:
            flags = []
        interface['flags'] = flags
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
    address_types = ['inet', 'inet6']
    for name in address_types:
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
    if network.version == 4:
        # IPv4 networks reserve the first address inside a CIDR for the
        # network address, and the last address for the broadcast address.
        return (
            IPAddress(network.first + 1, network.version),
            IPAddress(network.last - 1, network.version),
        )
    elif network.version == 6:
        # IPv6 networks reserve the first address inside a CIDR for the
        # network address, but do not have the notion of a broadcast address.
        return (
            IPAddress(network.first + 1, network.version),
            IPAddress(network.last, network.version),
        )
    else:
        raise ValueError("Unknown IP address family: %s" % network.version)


def get_interface_type(
        ifname, sys_class_net="/sys/class/net",
        proc_net_vlan='/proc/net/vlan'):
    """Heuristic to return the type of the given interface.

    The given interface must be able to be found in /sys/class/net/ifname.
    Otherwise, it will be reported as 'missing'.

    If an interface can be determined to be Ethernet, its type will begin
    with 'ethernet'. If a subtype can be determined, 'ethernet.subtype'
    will be returned.

    If a file named /proc/net/vlan/ifname can be found, the interface will
    be reported as 'ethernet.vlan'.

    If a directory named /sys/class/net/ifname/bridge can be found, the
    interface will be reported as 'ethernet.bridge'.

    If a directory named /sys/class/net/ifname/bonding can be found, the
    interface will be reported as 'ethernet.bond'.

    If a symbolic link named /sys/class/net/ifname/device/driver/module is
    found, the device will be assumed to be backed by real hardware.

    If /sys/class/net/ifname/device/ieee80211 exists, the hardware-backed
    interface will be reported as 'ethernet.wireless'.

    If an interface is assumed to be hardware-backed and cannot be determined
    to be a wireless interface, it will be reported as 'ethernet.physical'.

    If the interface can be determined to be a non-Ethernet type, the type
    that is found will be returned. (For example, 'loopback' or 'ipip'.)
    """
    sys_path = '%s/%s' % (sys_class_net, ifname)
    if not os.path.isdir(sys_path):
        return 'missing'

    sys_type_path = '%s/type' % sys_path
    with open(sys_type_path) as f:
        iftype = int(f.read().strip())

    # The iftype value here is defined in linux/if_arp.h.
    # The important thing here is that Ethernet maps to 1.
    # Currently, MAAS only runs on Ethernet interfaces.
    if iftype == 1:
        bridge_dir = os.path.join(sys_path, 'bridge')
        if os.path.isdir(bridge_dir):
            return 'ethernet.bridge'
        bond_dir = os.path.join(sys_path, 'bonding')
        if os.path.isdir(bond_dir):
            return 'ethernet.bond'
        if os.path.isfile('%s/%s' % (proc_net_vlan, ifname)):
            return 'ethernet.vlan'
        module_name_link = os.path.join(sys_path, 'device', 'driver', 'module')
        if not os.path.islink(module_name_link):
            return 'ethernet'
        module_name = os.readlink(module_name_link).split('/')[-1]
        if module_name:
            device_80211 = os.path.join(sys_path, 'device', 'ieee80211')
            if os.path.isdir(device_80211):
                return 'ethernet.wireless'
            else:
                return 'ethernet.physical'
        else:
            return 'ethernet'
    # ... however, we'll include some other commonly-seen interface types,
    # just for completeness.
    elif iftype == 772:
        return 'loopback'
    elif iftype == 768:
        return 'ipip'
    else:
        return 'unknown-%d' % iftype


def annotate_with_driver_information(interfaces):
    """Determines driver information for each of the given interfaces.

    Annotates the given dictionary to update it with driver information
    (if found) for each interface.
    """
    for name in interfaces:
        interfaces[name]['type'] = get_interface_type(name)
    return interfaces
