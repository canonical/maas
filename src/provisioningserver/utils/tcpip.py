# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with TCP/IP packets. (That is, layers 3 and 4.)"""

__all__ = [
    "IPv4",
    "UDP",
]

from collections import namedtuple
import struct
import time

from netaddr import IPAddress
from provisioningserver.utils.ethernet import (
    Ethernet,
    ETHERTYPE,
)

# Definitions for IPv4 packets used with `struct`.
# See https://tools.ietf.org/html/rfc791#section-3.1 for more details.
IPV4_PACKET = '!BBHHHBBHLL'
IPv4Packet = namedtuple('IPv4Packet', (
    'version__ihl',
    'tos',
    'total_length',
    'fragment_id',
    'flags__fragment_offset',
    'ttl',
    'protocol',
    'header_checksum',
    'src_ip',
    'dst_ip',
))
IPV4_HEADER_MIN_LENGTH = 20

# Definition for a decoded network packet.
Packet = namedtuple("Packet", (
    'timestamp',
    'l2',
    'l3',
    'l4',
    'payload'
))


class PacketProcessingError(Exception):
    """Raised when an error occurs while interpreting a raw packet."""

    def __init__(self, error):
        self.error = error
        super().__init__(error)


class PROTOCOL:
    """Enumeration to represent IP protocols that MAAS needs to understand."""
    UDP = 0x11


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
            self.invalid_reason = (
                "Truncated IPv4 header; need at least %d bytes." % (
                    IPV4_HEADER_MIN_LENGTH))
            return
        packet = IPv4Packet._make(
            struct.unpack(
                IPV4_PACKET, pkt_bytes[0:IPV4_HEADER_MIN_LENGTH]))
        self.packet = packet
        # Mask out the version_ihl field to get the IP version and IHL
        # (Internet Header Length) separately.
        self.version = (packet.version__ihl & 0xF0) >> 4
        # The IHL is a count of 4-bit words that comprise the header.
        self.ihl = (packet.version__ihl & 0xF) * 4
        if self.version != 4:
            self.valid = False
            self.invalid_reason = (
                "Invalid version field; expected IPv4, got IPv%d." % (
                    self.version))
            return
        if self.ihl < 20:
            self.invalid_reason = (
                "Invalid IPv4 IHL field; expected at least 20 bytes; got %d "
                "bytes." % self.ihl)
            self.valid = False
            return
        if len(pkt_bytes) < self.ihl:
            self.valid = False
            self.invalid_reason = (
                "Truncated IPv4 header; IHL indicates to read %d bytes; got "
                "%d bytes." % (self.ihl, len(pkt_bytes)))
            return
        # Everything beyond the IHL is the upper-layer payload. (No need to
        # understand IP options at this time.)
        self.payload = pkt_bytes[self.ihl:]

    @property
    def src_ip(self):
        return IPAddress(self.packet.src_ip)

    @property
    def dst_ip(self):
        return IPAddress(self.packet.dst_ip)

    def is_valid(self):
        return self.valid


# Definitions for UDP packets used with `struct`.
# https://tools.ietf.org/html/rfc768
UDP_PACKET = '!HHHH'
UDPPacket = namedtuple('IPPacket', (
    'src_port',
    'dst_port',
    'length',
    'checksum',
))
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
            self.invalid_reason = (
                "Truncated UDP header; need at least %d bytes." % (
                    UDP_HEADER_LENGTH))
            return
        packet = UDPPacket._make(
            struct.unpack(
                UDP_PACKET, pkt_bytes[0:UDP_HEADER_LENGTH]))
        self.packet = packet
        if packet.length < UDP_HEADER_LENGTH:
            self.valid = False
            self.invalid_reason = (
                "Invalid UDP packet; got length of %d bytes; expected at "
                "least %d bytes. " % (packet.length, UDP_HEADER_LENGTH))
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
                "UDP packet truncated; expected %d bytes; got %d bytes." % (
                    payload_length, len(self.payload)))

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
    # XXX Need to support IPv6 as well.
    if ethernet.ethertype != ETHERTYPE.IPV4:
        raise PacketProcessingError(
            "Invalid ethertype; expected %r, got %r." % (
                ETHERTYPE.IPV4, ethernet.ethertype))
    # Interpret Layer 3
    ip = IPv4(ethernet.payload)
    if not ip.is_valid():
        raise PacketProcessingError(ip.invalid_reason)
    if ip.packet.protocol != PROTOCOL.UDP:
        # Ignore non-IPv4 packets.
        raise PacketProcessingError(
            "Invalid protocol; expected %d (UDP), got %d." % (
                PROTOCOL.UDP, ip.packet.protocol))
    # Interpret Layer 4
    udp = UDP(ip.payload)
    if not udp.is_valid():
        raise PacketProcessingError(udp.invalid_reason)
    return Packet(timestamp, ethernet, ip, udp, udp.payload)
