# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities related to network and cluster interfaces."""

__all__ = [
    "get_name_and_vlan_from_cluster_interface",
    "make_name_from_interface",
]

from random import randint
import re


def make_name_from_interface(interface, alias=None):
    """Generate a cluster interface name based on a network interface name.

    The name is used as an identifier in API URLs, so awkward characters are
    not allowed: whitespace, colons, etc.  If the interface name had any such
    characters in it, they are replaced with a double dash (`--`).

    If `interface` is `None`, or empty, a name will be made up.
    """
    if alias:
        interface = f"{interface}:{alias}"
    if interface is None or interface == "":
        base_name = "unnamed-%d" % randint(1000000, 9999999)
    else:
        base_name = interface
    return re.sub(r"[^\w:.-]", "--", base_name)


def get_name_and_vlan_from_cluster_interface(cluster_name, interface):
    """Return a name suitable for a `Network` managed by a cluster interface.

    :param interface: Network interface name, e.g. `eth0:1`.
    :param cluster_name: Name of the cluster.
    :return: a tuple of the new name and the interface's VLAN tag.  The VLAN
        tag may be None.
    """
    name = interface
    vlan_tag = None
    if "." in name:
        _, vlan_tag = name.split(".", 1)
        if ":" in vlan_tag:
            # Nasty: there's an alias after the VLAN tag.
            vlan_tag, _ = vlan_tag.split(":", 1)
        name = name.replace(".", "-")
    name = name.replace(":", "-")
    network_name = "-".join((cluster_name, name))
    return network_name, vlan_tag
