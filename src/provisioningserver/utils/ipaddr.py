# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
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

import json
import os
import re

from netaddr import IPAddress, IPNetwork
import netifaces

from provisioningserver.utils.shell import call_and_check


def get_settings_dict(settings_line):
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
        settings[2 * i]: settings[2 * i + 1] for i in range(num_tokens // 2)
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
    [index, name, properties] = map(str.strip, line.split(":"))

    interface["index"] = int(index)
    names = name.split("@")
    interface["name"] = names[0]
    if len(names) > 1:
        interface["parent"] = names[1]

    # Now parse the <properties> part from above.
    # This will be in the form "<FLAG1,FLAG2> key1 value1 key2 value2 ..."
    matches = re.match(r"^<(.*)>(.*)", properties)
    if matches:
        flags = matches.group(1)
        if len(flags) > 0:
            flags = flags.split(",")
        else:
            flags = []
        interface["flags"] = flags
        interface["settings"] = get_settings_dict(matches.group(2))
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
    settings = get_settings_dict(line)
    mac = settings.get("link/ether")
    if mac is not None:
        interface["mac"] = mac
    address_types = ["inet", "inet6"]
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
    if not isinstance(output, str):
        output = str(output, "utf-8")

    interfaces = {}
    interface = None
    for line in output.splitlines():
        if re.match(r"^[0-9]", line):
            interface = _parse_interface_definition(line)
            if interface is not None:
                interfaces[interface["name"]] = interface
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


def get_bonded_interfaces(ifname, sys_class_net="/sys/class/net"):
    """Returns a list of interface names which are part of the specified
    Ethernet bond.

    :return:list
    """
    bonding_slaves_file = os.path.join(
        sys_class_net, ifname, "bonding", "slaves"
    )
    if os.path.isfile(bonding_slaves_file):
        with open(bonding_slaves_file) as f:
            return f.read().split()
    else:
        return []


def get_bridged_interfaces(ifname, sys_class_net="/sys/class/net"):
    """Returns a list of interface names which are part of the specified
    Ethernet bridge interface.

    :return:list
    """
    bridged_interfaces_dir = os.path.join(sys_class_net, ifname, "brif")
    if os.path.isdir(bridged_interfaces_dir):
        return os.listdir(bridged_interfaces_dir)
    else:
        return []


def get_interface_type(
    ifname, sys_class_net="/sys/class/net", proc_net="/proc/net"
):
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
    sys_path = os.path.join(sys_class_net, ifname)
    if not os.path.isdir(sys_path):
        return "missing"

    sys_type_path = os.path.join(sys_path, "type")
    with open(sys_type_path) as f:
        iftype = int(f.read().strip())

    # The iftype value here is defined in linux/if_arp.h.
    # The important thing here is that Ethernet maps to 1.
    # Currently, MAAS only runs on Ethernet interfaces.
    if iftype == 1:
        bridge_dir = os.path.join(sys_path, "bridge")
        if os.path.isdir(bridge_dir):
            return "ethernet.bridge"
        bond_dir = os.path.join(sys_path, "bonding")
        if os.path.isdir(bond_dir):
            return "ethernet.bond"
        if os.path.isfile(os.path.join(proc_net, "vlan", ifname)):
            return "ethernet.vlan"
        if os.path.isfile(os.path.join(sys_path, "tun_flags")):
            return "ethernet.tunnel"
        device_path = os.path.join(sys_path, "device")
        if os.path.islink(device_path):
            device_80211 = os.path.join(sys_path, "device", "ieee80211")
            if os.path.isdir(device_80211):
                return "ethernet.wireless"
            else:
                return "ethernet.physical"
        else:
            return "ethernet"
    # ... however, we'll include some other commonly-seen interface types,
    # just for completeness.
    elif iftype == 772:
        return "loopback"
    elif iftype == 768:
        return "ipip"
    else:
        return "unknown-%d" % iftype


def _parse_proc_net_bonding(file):
    """Parse the given file, which must be a path to a file in the format
    that is used for file in `/proc/net/bonding/<interface>`.

    Returns a dictionary mapping each interface name found in the file to
    its original MAC address.
    """
    interfaces = {}
    current_iface = None
    with open(file) as f:
        for line in f.readlines():
            line = line.strip()
            slave_iface = line.split("Slave Interface: ")
            if len(slave_iface) == 2:
                current_iface = slave_iface[1]
            hw_addr = line.split("Permanent HW addr: ")
            if len(hw_addr) == 2:
                interfaces[current_iface] = hw_addr[1]
    return interfaces


def annotate_with_proc_net_bonding_original_macs(
    interfaces, proc_net="/proc/net"
):
    """Repairs the MAC addresses of bond members in the specified structure.

    Given the specified interfaces structure, uses the data in
    `/proc/net/bonding/*` to determine if any of the interfaces
    in the structure are bond members. If so, modifies their MAC address,
    setting it back to the original hardware MAC. (When an interface is added
    to a bond, its MAC address is set to the bond MAC, and subsequently
    reported in commands like "ip addr".)
    """
    proc_net_bonding = os.path.join(proc_net, "bonding")
    if os.path.isdir(proc_net_bonding):
        bonds = os.listdir(proc_net_bonding)
        for bond in bonds:
            parent_macs = _parse_proc_net_bonding(
                os.path.join(proc_net_bonding, bond)
            )
            for interface in parent_macs:
                if interface in interfaces:
                    interfaces[interface]["mac"] = parent_macs[interface]
    return interfaces


def annotate_with_driver_information(
    interfaces, sys_class_net="/sys/class/net", proc_net="/proc/net"
):
    """Determines driver information for each of the given interfaces.

    Annotates the given dictionary to update it with driver information
    (if found) for each interface.

    :param interfaces: interfaces dictionary from `parse_ip_addr()`.
    :param proc_net: path to /proc/net
    :param sys_class_net: path to /sys/class/net
    """
    interfaces = annotate_with_proc_net_bonding_original_macs(
        interfaces, proc_net=proc_net
    )
    for name in interfaces:
        iface = interfaces[name]
        iftype = get_interface_type(
            name, sys_class_net=sys_class_net, proc_net=proc_net
        )
        interfaces[name]["type"] = iftype
        if iftype == "ethernet.bond":
            bond_parents = get_bonded_interfaces(
                name, sys_class_net=sys_class_net
            )
            iface["bonded_interfaces"] = bond_parents
        elif iftype == "ethernet.vlan":
            iface["vid"] = get_vid_from_ifname(name)
        elif iftype == "ethernet.bridge":
            iface["bridged_interfaces"] = get_bridged_interfaces(
                name, sys_class_net=sys_class_net
            )
    return interfaces


def get_vid_from_ifname(ifname):
    """Returns the VID for the specified VLAN interface name.

    Returns 0 if the VID could not be determined.

    :return:int
    """
    vid = 0
    iface_vid_re = re.compile(r".*\.([0-9]+)$")
    iface_vid_match = iface_vid_re.match(ifname)
    vlan_vid_re = re.compile(r"vlan([0-9]+)$")
    vlan_vid_match = vlan_vid_re.match(ifname)
    if iface_vid_match:
        vid = int(iface_vid_match.group(1))
    elif vlan_vid_match:
        vid = int(vlan_vid_match.group(1))
    return vid


def get_ip_addr():
    """Returns this system's local IP address information as a dictionary.

    :raises:ExternalProcessError: if IP address information could not be
        gathered.
    """
    ip_addr_output = call_and_check(["ip", "addr"])
    ifaces = parse_ip_addr(ip_addr_output)
    return annotate_with_driver_information(ifaces)


def get_ip_addr_json():
    """Returns this system's local IP address information, in JSON format.

    :raises:ExternalProcessError: if IP address information could not be
        gathered.
    """
    return json.dumps(get_ip_addr())


def get_mac_addresses():
    """Returns a list of this system's MAC addresses.

    :raises:ExternalProcessError: if IP address information could not be
        gathered.
    """
    ip_addr = get_ip_addr()
    return list(
        {
            iface["mac"]
            for iface in ip_addr.values()
            if iface.get("mac", "00:00:00:00:00:00") != "00:00:00:00:00:00"
        }
    )


def get_machine_default_gateway_ip():
    """Return the default gateway IP for the machine."""
    gateways = netifaces.gateways()
    defaults = gateways.get("default")
    if not defaults:
        return

    def default_ip(family):
        gw_info = defaults.get(family)
        if not gw_info:
            return
        addresses = netifaces.ifaddresses(gw_info[1]).get(family)
        if addresses:
            return addresses[0]["addr"]

    return default_ip(netifaces.AF_INET) or default_ip(netifaces.AF_INET6)
