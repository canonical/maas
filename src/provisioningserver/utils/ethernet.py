# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with Ethernet packets."""

from collections import namedtuple
import struct

from netaddr import EUI

from provisioningserver.utils.network import bytes_to_int, hex_str_to_bytes

# Definitions for Ethernet packet used with `struct`.
ETHERNET_PACKET = "!6s6s2s"

# 6 byte source MAC + 6 byte destination MAC + 2 byte Ethertype
ETHERNET_HEADER_LEN = 14

EthernetPacket = namedtuple(
    "EthernetPacket", ("dst_mac", "src_mac", "ethertype")
)

VLAN_HEADER = "!2s2s"
VLAN_HEADER_LEN = 4


class ETHERTYPE:
    """Enumeration to represent ethertypes that MAAS needs to understand."""

    IPV4 = hex_str_to_bytes("0800")
    IPV6 = hex_str_to_bytes("86dd")
    ARP = hex_str_to_bytes("0806")
    VLAN = hex_str_to_bytes("8100")


class Ethernet:
    """Representation of an Ethernet packet."""

    def __init__(self, pkt_bytes, time=None):
        """Decodes the specified Ethernet packet.

        Supports raw Ethernet frames, and Ethernet frames containing tagged
        802.1q VLANs.

        The VID will be placed in the `vid` attribute, and the payload (next
        layer packet) will be placed in the `payload` attribute.

        If specified, the time will be stored in the `time` attribute.

        The source MAC, destination MAC, and payload Ethertype will be
        stored in `src_mac`, `dst_mac`, and `ethertype` attributes,
        respectively.

        :param pkt_bytes: The input bytes of the Ethernet packet.
        :type pkt_bytes: bytes
        :param time: Timestamp packet was seen (seconds since epoch)
        :type time: str
        :return:
        """
        if len(pkt_bytes) < ETHERNET_HEADER_LEN:
            self.valid = False
            return
        packet = EthernetPacket._make(
            struct.unpack(ETHERNET_PACKET, pkt_bytes[0:ETHERNET_HEADER_LEN])
        )
        payload_index = ETHERNET_HEADER_LEN
        if packet.ethertype == ETHERTYPE.VLAN:
            # We found an 802.1q encapsulated frame. The next four bytes are
            # the QoS, VLAN ID,and the Ethertype of the encapsulated frame.
            if len(pkt_bytes) < (ETHERNET_HEADER_LEN + VLAN_HEADER_LEN):
                self.valid = False
                return
            vid, ethertype = struct.unpack(
                VLAN_HEADER,
                pkt_bytes[payload_index : payload_index + VLAN_HEADER_LEN],
            )
            vid = bytes_to_int(vid)
            # The VLAN is the lower 12 bits; the upper 4 bits are for QoS.
            vid &= 0xFFF
            self.vid = vid
            # Use the Ethertype found in the VLAN header.
            self.ethertype = ethertype
            payload_index += VLAN_HEADER_LEN
        else:
            self.vid = None
            self.ethertype = packet.ethertype
        self.valid = True
        self.packet = packet
        self.payload = pkt_bytes[payload_index:]
        self.src_mac = packet.src_mac
        self.dst_mac = packet.dst_mac
        self.time = time

    @property
    def src_eui(self):
        """Returns a netaddr.EUI representing the source MAC address."""
        return EUI(bytes_to_int(self.src_mac))

    @property
    def dst_eui(self):
        """Returns a netaddr.EUI representing the destination MAC address."""
        return EUI(bytes_to_int(self.dst_mac))

    def is_valid(self):
        """Returns True if this is a valid Ethernet packet, False otherwise."""
        return self.valid
