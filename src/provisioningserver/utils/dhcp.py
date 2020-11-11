# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with DHCP packets."""


from collections import namedtuple
from datetime import datetime
from io import BytesIO
import os
from pprint import pformat
import stat
import struct
import subprocess
import sys
from textwrap import dedent

from netaddr import IPAddress

from provisioningserver.path import get_path
from provisioningserver.utils import sudo
from provisioningserver.utils.network import bytes_to_ipaddress, format_eui
from provisioningserver.utils.pcap import PCAP, PCAPError
from provisioningserver.utils.script import ActionScriptError
from provisioningserver.utils.tcpip import (
    decode_ethernet_udp_packet,
    PacketProcessingError,
)

# The SEEN_AGAIN_THRESHOLD is a time (in seconds) that determines how often
# to report (IP, MAC) bindings that have been seen again (or "REFRESHED").
# While it is important for MAAS to know about "NEW" and "MOVED" bindings
# immediately, "REFRESHED" bindings occur too often to be useful, and
# are thus throttled by this value.
SEEN_AGAIN_THRESHOLD = 600

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

    def is_valid(self):
        return self.valid

    @property
    def server_identifier(self) -> IPAddress:
        """Returns the DHCP server identifier option.

        This returns the IP address of the DHCP server.

        :return: netaddr.IPAddress
        """
        server_identifier_bytes = self.options.get(54, None)
        if server_identifier_bytes is not None:
            return bytes_to_ipaddress(server_identifier_bytes)
        return None

    def write(self, out=sys.stdout):
        """Output text-based details about this DHCP packet to the specified
        file or stream.

        :param out: An object with `write(str)` and `flush()` methods.
        """
        packet = pformat(self.packet)
        out.write(packet)
        out.write("\n")
        options = pformat(self.options)
        out.write(options)
        out.write("\nServer identifier: %s\n\n" % self.server_identifier)
        out.flush()


def observe_dhcp_packets(input=sys.stdin.buffer, out=sys.stdout):
    """Read stdin and look for tcpdump binary DHCP output.

    :param input: Stream to read PCAP data from.
    :type input: a file or stream supporting `read(int)`
    :param out: Stream to write to.
    :type input: a file or stream supporting `write(str)` and `flush()`.
    """
    try:
        pcap = PCAP(input)
        if pcap.global_header.data_link_type != 1:
            # Not an Ethernet interface. Need to exit here, because our
            # assumptions about the link layer header won't be correct.
            return 4
        for pcap_header, packet_bytes in pcap:
            out.write(str(datetime.now()))
            out.write("\n")
            try:
                packet = decode_ethernet_udp_packet(packet_bytes, pcap_header)
                dhcp = DHCP(packet.payload)
                if not dhcp.is_valid():
                    out.write(dhcp.invalid_reason)
                out.write(
                    "     Source MAC address: %s\n"
                    % format_eui(packet.l2.src_eui)
                )
                out.write(
                    "Destination MAC address: %s\n"
                    % format_eui(packet.l2.dst_eui)
                )
                if packet.l2.vid is not None:
                    out.write("     Seen on 802.1Q VID: %s\n" % packet.l2.vid)
                out.write("      Source IP address: %s\n" % packet.l3.src_ip)
                out.write(" Destination IP address: %s\n" % packet.l3.dst_ip)
                dhcp.write(out=out)
                out.flush()
            except PacketProcessingError as e:
                out.write(e.error)
                out.write("\n\n")
                out.flush()
    except EOFError:
        # Capture aborted before it could even begin. Note that this does not
        # occur if the end-of-stream occurs normally. (In that case, the
        # program will just exit.)
        return 3
    except PCAPError:
        # Capture aborted due to an I/O error.
        return 2
    return None


def add_arguments(parser):
    """Add this command's options to the `ArgumentParser`.

    Specified by the `ActionScript` interface.
    """
    parser.description = dedent(
        """\
        Observes DHCP traffic specified interface.
        """
    )
    parser.add_argument(
        "interface",
        type=str,
        nargs="?",
        help="Ethernet interface from which to capture traffic. Optional if "
        "an input file is specified.",
    )
    parser.add_argument(
        "-i",
        "--input-file",
        type=str,
        required=False,
        help="File to read PCAP output from. Use - for stdin. Default is to "
        "call `sudo /usr/lib/maas/dhcp-monitor` to get input.",
    )


def run(
    args, output=sys.stdout, stdin=sys.stdin, stdin_buffer=sys.stdin.buffer
):
    """Observe an Ethernet interface and print DHCP packets."""
    network_monitor = None
    if args.input_file is None:
        if args.interface is None:
            raise ActionScriptError("Required argument: interface")
        cmd = sudo([get_path("/usr/lib/maas/dhcp-monitor"), args.interface])
        network_monitor = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        infile = network_monitor.stdout
    else:
        if args.input_file == "-":
            mode = os.fstat(stdin.fileno()).st_mode
            if not stat.S_ISFIFO(mode):
                raise ActionScriptError("Expected stdin to be a pipe.")
            infile = stdin_buffer
        else:
            infile = open(args.input_file, "rb")
    return_code = observe_dhcp_packets(input=infile, out=output)
    if return_code is not None:
        raise SystemExit(return_code)
    if network_monitor is not None:
        return_code = network_monitor.poll()
        if return_code is not None:
            raise SystemExit(return_code)
