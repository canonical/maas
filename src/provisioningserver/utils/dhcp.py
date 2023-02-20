# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with DHCP packets."""


from collections import namedtuple
from io import BytesIO
import struct
from typing import Optional

from netaddr import IPAddress

from provisioningserver.utils.network import bytes_to_ipaddress

# Definitions for DHCP packet used with `struct`.
# See https://tools.ietf.org/html/rfc2131#section-2 for packet format.
DHCP_PACKET = "!BBBBLHHLLLL16s64s128sBBBB"
DHCPPacket = namedtuple(
    "DHCPPacket",
    (
        "op",
        "htype",
        "len",
        "hops",
        "xid",
        "secs",
        "flags",
        "ciaddr",
        "yiaddr",
        "siaddr",
        "giaddr",
        "chaddr",
        "sname",
        "file",
        "cookie1",
        "cookie2",
        "cookie3",
        "cookie4",
    ),
)

# This is the size of the struct; DHCP options are not included here.
SIZEOF_DHCP_PACKET = 240


class InvalidDHCPPacket(Exception):
    """Raised internally when a DHCP packet is not valid."""


class DHCP:
    """Representation of a DHCP packet."""

    def __init__(self, pkt_bytes: bytes):
        """
        Create a DHCP packet, given the specified upper-layer packet bytes.

        :param pkt_bytes: The input bytes of the DHCP packet.
        :type pkt_bytes: bytes
        """
        super().__init__()
        self.valid = None
        self.invalid_reason = None
        self.options = None
        if len(pkt_bytes) < SIZEOF_DHCP_PACKET:
            self.valid = False
            self.invalid_reason = "Truncated DHCP packet."
            return
        packet = DHCPPacket._make(
            struct.unpack(DHCP_PACKET, pkt_bytes[0:SIZEOF_DHCP_PACKET])
        )
        # https://tools.ietf.org/html/rfc2131#section-3
        expected_cookie = (99, 130, 83, 99)
        actual_cookie = (
            packet.cookie1,
            packet.cookie2,
            packet.cookie3,
            packet.cookie4,
        )
        if expected_cookie != actual_cookie:
            self.valid = False
            self.invalid_reason = "Invalid DHCP cookie."
            return
        self.packet = packet
        option_bytes = pkt_bytes[SIZEOF_DHCP_PACKET:]
        try:
            self.options = {
                option: value
                for option, value in self._parse_options(option_bytes)
            }
        except InvalidDHCPPacket as exception:
            self.valid = False
            self.invalid_reason = str(exception)
        if self.valid is None:
            self.valid = True

    def _parse_options(self, option_bytes: bytes):
        """Yields tuples of DHCP options found in the given `bytes`.

        :returns: Iterator of (option_code: int, option: bytes).
        :raises InvalidDHCPPacket: If the options are invalid.
        """
        stream = BytesIO(option_bytes)
        while True:
            option_bytes = stream.read(1)
            if len(option_bytes) != 1:
                break
            option_code = option_bytes[0]
            # RFC 1533 (https://tools.ietf.org/html/rfc1533#section-3) defines
            # 255 as the "end option" and 0 as the "pad option"; both are one
            # byte in length.
            if option_code == 255:
                break
            if option_code == 0:
                continue
            # Each option field is a one-byte quantity indicating how many
            # bytes are expected to follow.
            length_bytes = stream.read(1)
            if len(length_bytes) != 1:
                raise InvalidDHCPPacket(
                    "Truncated length field in DHCP option."
                )
            option_length = length_bytes[0]
            option_value = stream.read(option_length)
            if len(option_value) != option_length:
                raise InvalidDHCPPacket("Truncated DHCP option value.")
            yield option_code, option_value

    @property
    def server_identifier(self) -> Optional[IPAddress]:
        """Returns the DHCP server identifier option.

        This returns the IP address of the DHCP server.

        :return: netaddr.IPAddress
        """
        server_identifier_bytes = self.options.get(54, None)
        if server_identifier_bytes is not None:
            return bytes_to_ipaddress(server_identifier_bytes)
        return None
