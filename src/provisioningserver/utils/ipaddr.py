# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helper functions to parse network information from LXD-based resource binary."""

import json
import os
from pathlib import Path
import re

import netifaces

from provisioningserver.refresh import get_resources_bin_path
from provisioningserver.utils.lxd import parse_lxd_networks
from provisioningserver.utils.shell import call_and_check


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
    output = call_and_check([get_resources_bin_path()])
    ifaces = parse_lxd_networks(json.loads(output)["networks"])
    _update_interface_type(ifaces)
    _annotate_with_proc_net_bonding_original_macs(ifaces)
    return ifaces


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


def _update_interface_type(interfaces, sys_class_net=Path("/sys/class/net")):
    """Update the interface type in a more detailed way than LXD code reports.


    LXD reports both virtual and physical interfaces as "broadcast". This logic
    looks at /sys to get more details about interface type.

    """

    def get_interface_type(name, details):
        iftype = details["type"]
        if iftype in ("vlan", "bond", "bridge", "loopback"):
            return iftype

        sys_path = sys_class_net / name
        if not sys_path.is_dir():
            return "missing"

        iftype_id = int(((sys_path / "type").read_text()))
        # The iftype value here is defined in linux/if_arp.h.
        # The important thing here is that Ethernet maps to 1.
        # Currently, MAAS only runs on Ethernet interfaces.
        if iftype_id == 1:
            if (sys_path / "tun_flags").is_file():
                return "tunnel"
            device_path = sys_path / "device"
            if device_path.is_symlink():
                if (device_path / "ieee80211").is_dir():
                    return "wireless"
                else:
                    return "physical"
            else:
                return "ethernet"
        # ... however, we'll include some other commonly-seen interface types,
        # just for completeness.
        elif iftype_id == 768:
            return "ipip"
        else:
            return "unknown-%d" % iftype

    for name, details in interfaces.items():
        details["type"] = get_interface_type(name, details)


def _annotate_with_proc_net_bonding_original_macs(
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


def _parse_proc_net_bonding(path):
    """Parse the given file, which must be a path to a file in the format
    that is used for file in `/proc/net/bonding/<interface>`.

    Returns a dictionary mapping each interface name found in the file to
    its original MAC address.
    """
    interfaces = {}
    current_iface = None
    with open(path) as fd:
        for line in fd.readlines():
            line = line.strip()
            slave_iface = line.split("Slave Interface: ")
            if len(slave_iface) == 2:
                current_iface = slave_iface[1]
            hw_addr = line.split("Permanent HW addr: ")
            if len(hw_addr) == 2:
                interfaces[current_iface] = hw_addr[1]
    return interfaces
