# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with TCP/IP packets. (That is, layers 3 and 4.)"""

from collections import namedtuple
from ipaddress import ip_address
import struct
import time

from netaddr import IPAddress

from provisioningserver.utils.ethernet import Ethernet, ETHERTYPE

# Definition for a decoded network packet.
Packet = namedtuple("Packet", ("timestamp", "l2", "l3", "l4", "payload"))


class PacketProcessingError(Exception):
    """Raised when an error occurs while interpreting a raw packet."""

    def __init__(self, error):
        self.error = error
        super().__init__(error)


class PROTOCOL:
    """Enumeration to represent IP protocols that MAAS needs to understand."""

    # https://www.iana.org/assignments/protocol-numbers/protocol-numbers.xhtml
    IPV6_HOP_BY_HOP = 0x00
    ICMP = 0x01
    IGMP = 0x02
    TCP = 0x06
    UDP = 0x11
    IPV6_ENCAPSULATION = 0x29
    IPV6_ROUTING_HEADER = 0x2B
    IPV6_FRAGMENT_HEADER = 0x2C
    MOBILITY = 0x37
    IPV6_ICMP = 0x3A
    IPV6_NO_NEXT_HEADER = 0x3B
    IPV6_DESTINATION_OPTIONS = 0x3C
    IPV6_MOBILITY = 0x87
    IPV6_SHIM6 = 0x8C


# Definitions for IPv4 packets used with `struct`.
# See https://tools.ietf.org/html/rfc791#section-3.1 for more details.
IPV4_PACKET = "!BBHHHBBHLL"
IPv4Packet = namedtuple(
    "IPv4Packet",
    (
        "version__ihl",
        "tos",
        "total_length",
        "fragment_id",
        "flags__fragment_offset",
        "ttl",
        "protocol",
        "header_checksum",
        "src_ip",
        "dst_ip",
    ),
)
IPV4_HEADER_MIN_LENGTH = 20


class IPv4:
    """Representation of an IPv4 packet."""

    def __init__(self, pkt_bytes: bytes):
        """Decodes the specified IPv4 packet.

        The IP payload will be placed in the `payload` ivar if the packet
        is valid. If the packet is valid, the `valid` ivar will be set to True.
        If the packet is not valid, the `valid` ivar will be set to False, and
        the `invalid_reason` will contain a description of why the packet is
        not valid.

        This class does not validate the header checksum, and as such, should
        only be used for testing.

        :param pkt_bytes: The input bytes of the IPv4 packet.
        """
        self.valid = True
        self.invalid_reason = None
        if len(pkt_bytes) < IPV4_HEADER_MIN_LENGTH:
            self.valid = False
            self.invalid_reason = f"Truncated IPv4 header; need at least {IPV4_HEADER_MIN_LENGTH} bytes."
            return
        packet = IPv4Packet._make(
            struct.unpack(IPV4_PACKET, pkt_bytes[0:IPV4_HEADER_MIN_LENGTH])
        )
        self.packet = packet
        # Mask out the version_ihl field to get the IP version and IHL
        # (Internet Header Length) separately.
        self.version = (packet.version__ihl & 0xF0) >> 4
        # The IHL is a count of 4-bit words that comprise the header.
        self.ihl = (packet.version__ihl & 0xF) * 4
        if self.version != 4:
            self.valid = False
            self.invalid_reason = (
                f"Invalid version field; expected IPv4, got IPv{self.version}."
            )
            return
        if self.ihl < 20:
            self.invalid_reason = f"Invalid IPv4 IHL field; expected at least 20 bytes; got {self.ihl} bytes."
            self.valid = False
            return
        if len(pkt_bytes) < self.ihl:
            self.valid = False
            self.invalid_reason = (
                f"Truncated IPv4 header; IHL indicates to read {self.ihl} bytes; "
                f"got {len(pkt_bytes)} bytes."
            )
            return
        self.protocol = packet.protocol
        # Everything beyond the IHL is the upper-layer payload. (No need to
        # understand IP options at this time.)
        self.payload = pkt_bytes[self.ihl :]

    @property
    def src_ip(self):
        return IPAddress(self.packet.src_ip)

    @property
    def dst_ip(self):
        return IPAddress(self.packet.dst_ip)

    def is_valid(self):
        return self.valid


IPV6_PACKET = "!LHBB16s16s"
IPv6Packet = namedtuple(
    "IPv6Packet",
    (
        "version__traffic_class__flow_label",
        "payload_length",
        "next_header",
        "hop_limit",
        "src_ip",
        "dst_ip",
    ),
)
IPV6_HEADER_MIN_LENGTH = 40


class IPv6:
    """Representation of an IPv6 packet."""

    def __init__(self, pkt_bytes: bytes):
        """Decodes the specified IPv6 packet.

        The IP payload will be placed in the `payload` ivar if the packet
        is valid. If the packet is valid, the `valid` ivar will be set to True.
        If the packet is not valid, the `valid` ivar will be set to False, and
        the `invalid_reason` will contain a description of why the packet is
        not valid.

        This class does not validate the header checksum, and as such, should
        only be used for testing.

        :param pkt_bytes: The input bytes of the IPv6 packet.
        """
        self.valid = True
        self.invalid_reason = None
        self.protocol = None
        if len(pkt_bytes) < IPV6_HEADER_MIN_LENGTH:
            self.valid = False
            self.invalid_reason = f"Truncated IPv6 header; need at least {IPV6_HEADER_MIN_LENGTH} bytes."
            return
        packet = IPv6Packet._make(
            struct.unpack(IPV6_PACKET, pkt_bytes[0:IPV6_HEADER_MIN_LENGTH])
        )
        self.packet = packet
        # Mask out the version_ihl field to get the IP version and IHL
        # (Internet Header Length) separately.
        self.version = (
            packet.version__traffic_class__flow_label & 0xF0000000
        ) >> 28
        if self.version != 6:
            self.valid = False
            self.invalid_reason = (
                f"Invalid version field; expected IPv6, got IPv{self.version}."
            )
            return
        # XXX mpontillo 2017-08-15: should process next headers.
        # (not required for beaconing, since there won't be any)
        self.protocol = packet.next_header
        self.payload = pkt_bytes[IPV6_HEADER_MIN_LENGTH:]

    @property
    def src_ip(self):
        return ip_address(self.packet.src_ip)

    @property
    def dst_ip(self):
        return ip_address(self.packet.dst_ip)

    def is_valid(self):
        return self.valid


# Definitions for UDP packets used with `struct`.
# https://tools.ietf.org/html/rfc768
UDP_PACKET = "!HHHH"
UDPPacket = namedtuple(
    "IPPacket", ("src_port", "dst_port", "length", "checksum")
)
UDP_HEADER_LENGTH = 8


class UDP:
    """Representation of a UDP packet."""

    def __init__(self, pkt_bytes: bytes):
        """Decodes the specified UDP packet.

        The UDP payload will be placed in the `payload` ivar if the packet
        is valid. If the packet is valid, the `valid` ivar will be set to True.
        If the packet is not valid, the `valid` ivar will be set to False, and
        the `invalid_reason` will contain a description of why the packet is
        not valid.

        This class does not validate the UDP checksum, and as such, should only
        be used for testing.
        """
        self.valid = True
        self.invalid_reason = None
        if len(pkt_bytes) < UDP_HEADER_LENGTH:
            self.valid = False
            self.invalid_reason = f"Truncated UDP header; need at least {UDP_HEADER_LENGTH} bytes."
            return
        packet = UDPPacket._make(
            struct.unpack(UDP_PACKET, pkt_bytes[0:UDP_HEADER_LENGTH])
        )
        self.packet = packet
        if packet.length < UDP_HEADER_LENGTH:
            self.valid = False
            self.invalid_reason = (
                f"Invalid UDP packet; got length of {packet.length} bytes; expected at "
                f"least {UDP_HEADER_LENGTH} bytes."
            )
            return
        # UDP length includes UDP header, so subtract it to get payload length.
        payload_length = packet.length - UDP_HEADER_LENGTH
        self.payload = pkt_bytes[UDP_HEADER_LENGTH:]
        # Note: the payload could be more that the stated length due to
        # padding. Truncate it to the correct length.
        if len(self.payload) > payload_length:
            self.payload = self.payload[0:payload_length]
        if len(self.payload) != payload_length:
            self.valid = False
            self.invalid_reason = (
                f"UDP packet truncated; expected {payload_length} bytes; "
                f"got {len(self.payload)} bytes."
            )

    def is_valid(self):
        return self.valid


def decode_ethernet_udp_packet(packet, pcap_header=None):
    if pcap_header is None:
        timestamp = int(time.time())
    else:
        timestamp = pcap_header.timestamp_seconds
    ethernet = Ethernet(packet, time=timestamp)
    if not ethernet.is_valid():
        raise PacketProcessingError("Invalid Ethernet packet.")
    ethertype = ethernet.ethertype
    supported_ethertypes = (ETHERTYPE.IPV4, ETHERTYPE.IPV6)
    if ethertype not in supported_ethertypes:
        raise PacketProcessingError(
            f"Invalid ethertype; expected one of {supported_ethertypes!r}, got {ethertype!r}."
        )
    # Interpret Layer 3
    if ethertype == ETHERTYPE.IPV4:
        ip = IPv4(ethernet.payload)
    else:
        ip = IPv6(ethernet.payload)
    if not ip.is_valid():
        raise PacketProcessingError(ip.invalid_reason)
    if ip.protocol != PROTOCOL.UDP:
        raise PacketProcessingError(
            f"Invalid protocol; expected {PROTOCOL.UDP} (UDP), got {ip.protocol}."
        )
    # Interpret Layer 4
    udp = UDP(ip.payload)
    if not udp.is_valid():
        raise PacketProcessingError(udp.invalid_reason)
    return Packet(timestamp, ethernet, ip, udp, udp.payload)
