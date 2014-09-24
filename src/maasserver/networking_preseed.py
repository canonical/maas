# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Network configuration preseed code.

This will eventually generate installer networking configuration like:

   https://gist.github.com/jayofdoom/b035067523defec7fb53

The installer running on a node will use this to set up the node's networking
according to MAAS's specifications.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'generate_networking_config',
    ]

from lxml import etree
from maasserver.models.nodeprobeddetails import get_probed_details


def extract_network_interface_data(element):
    """Extract network interface name and MAC address from XML element.

    :return: A tuple of network interface name and MAC address as found in
        the XML.  If either is not found, it will be `None`.
    """
    interfaces = element.xpath("logicalname")
    macs = element.xpath("serial")
    if len(interfaces) == 0 or len(macs) == 0:
        # Not enough data.
        return None, None
    assert len(interfaces) == 1
    assert len(macs) == 1
    return interfaces[0].text, macs[0].text


def normalise_mac(mac):
    """Return a MAC's normalised representation.

    This doesn't actually parse all the different formats for writing MAC
    addresses, but it does eliminate case differences.  In practice, any MAC
    address this code is likely to will equal another version of itself after
    normalisation, even if they were originally different spellings.
    """
    return mac.strip().lower()


def extract_network_interfaces(node):
    """Extract network interfaces from node's `lshw` output.

    :param node: A `Node`.
    :return: A list of tuples describing the network interfaces.
        Each tuple consists of an interface name and a MAC address.
    """
    node_details = get_probed_details([node.system_id])
    if node.system_id not in node_details:
        return []
    lshw_xml = node_details[node.system_id].get('lshw')
    if lshw_xml is None:
        return []
    network_nodes = etree.fromstring(lshw_xml).xpath("//node[@id='network']")
    interfaces = [
        extract_network_interface_data(xml_node)
        for xml_node in network_nodes
        ]
    return [
        (interface, normalise_mac(mac))
        for interface, mac in interfaces
        if interface is not None and mac is not None
        ]


def generate_ethernet_link_entry(interface, mac):
    """Generate the `links` list entry for the given ethernet interface.

    :param interface: Network interface name, e.g. `eth0`.
    :param mac: MAC address, e.g. `00:11:22:33:44:55`.
    :return: A dict specifying the network interface, with keys
        `id`, `type`, and `ethernet_mac_address` (and possibly more).
    """
    return {
        'id': interface,
        'type': 'ethernet',
        'ethernet_mac_address': mac,
        }


def generate_networking_config(node):
    """Generate a networking preseed for `node`.

    :param node: A `Node`.
    :return: A dict along the lines of the example in
        https://gist.github.com/jayofdoom/b035067523defec7fb53 -- just
        json-encode it to get a file in that format.
    """
    interfaces = extract_network_interfaces(node)
    return {
        'provider': "MAAS",
        'network_info': {
            'services': [
                # List DNS servers here.
                ],
            'networks': [
                # Write network specs here.
                ],
            'links': [
                generate_ethernet_link_entry(interface, mac)
                for interface, mac in interfaces
                ],
            },
        }
