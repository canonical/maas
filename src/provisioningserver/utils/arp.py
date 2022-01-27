# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with ARP packets."""


from collections import namedtuple
from datetime import datetime
import json
import os
import stat
import struct
import subprocess
import sys
from textwrap import dedent

from netaddr import EUI, IPAddress

from provisioningserver.path import get_path
from provisioningserver.utils import sudo
from provisioningserver.utils.ethernet import Ethernet, ETHERTYPE
from provisioningserver.utils.network import bytes_to_int, format_eui
from provisioningserver.utils.pcap import PCAP, PCAPError
from provisioningserver.utils.script import ActionScriptError

# The SEEN_AGAIN_THRESHOLD is a time (in seconds) that determines how often
# to report (IP, MAC) bindings that have been seen again (or "REFRESHED").
# While it is important for MAAS to know about "NEW" and "MOVED" bindings
# immediately, "REFRESHED" bindings occur too often to be useful, and
# are thus throttled by this value.
SEEN_AGAIN_THRESHOLD = 600

# Definitions for ARP packet used with `struct`.
ARP_PACKET = "!hhBBh6sL6sL"
ARPPacket = namedtuple(
    "ARPPacket",
    (
        "hardware_type",
        "protocol",
        "hardware_length",
        "protocol_length",
        "operation",
        "sender_mac",
        "sender_ip",
        "target_mac",
        "target_ip",
    ),
)

SIZEOF_ARP_PACKET = 28


class ARP_OPERATION:
    """Enumeration to represent ARP operation types."""

    REQUEST = 1
    REPLY = 2

    def __init__(self, operation):
        super().__init__()
        self.operation = operation

    def __bytes__(self):
        """Returns the ARP operation in byte format.

        The returned value will be padded to two bytes; suitable for placement
        in an ARP packet.
        """
        return bytes.fromhex("%04x" % self.operation)

    def __str__(self):
        if self.operation == 1:
            extra = " (request)"
        elif self.operation == 2:
            extra = " (reply)"
        else:
            extra = ""
        return "%d%s" % (self.operation, extra)

    def __radd__(self, other):
        """Allows concatenating an ARP_OPERATION with `bytes`."""
        if isinstance(other, bytes):
            return other + bytes(self)
        else:
            raise NotImplementedError(
                "ARP_OPERATION may only be added to `bytes`."
            )


class ARP:
    """Representation of an ARP packet."""

    def __init__(
        self, pkt_bytes, time=None, src_mac=None, dst_mac=None, vid=None
    ):
        """
        :param pkt_bytes: The input bytes of the ARP packet.
        :type pkt_bytes: bytes
        :param time: Timestamp packet was seen (seconds since epoch)
        :type time: str
        :param src_mac: Source MAC address from Ethernet header.
        :type src_mac: bytes
        :param dst_mac: Destination MAC address from Ethernet header.
        :type dst_mac: bytes
        :param vid: 802.1q VLAN ID (VID), or None if untagged.
        :type vid: int
        :return:
        """
        packet = ARPPacket._make(
            struct.unpack(ARP_PACKET, pkt_bytes[0:SIZEOF_ARP_PACKET])
        )
        self.packet = packet
        self.time = time
        if src_mac is not None:
            self.src_mac = EUI(bytes_to_int(src_mac))
        else:
            self.src_mac = None
        if dst_mac is not None:
            self.dst_mac = EUI(bytes_to_int(dst_mac))
        else:
            self.dst_mac = None
        self.vid = vid
        self.hardware_type = packet.hardware_type
        self.protocol_type = packet.protocol
        self.hardware_length = packet.hardware_length
        self.protocol_length = packet.protocol_length
        self.operation = packet.operation
        self.sender_hardware_bytes = packet.sender_mac
        self.sender_protocol_bytes = packet.sender_ip
        self.target_hardware_bytes = packet.target_mac
        self.target_protocol_bytes = packet.target_ip

    @property
    def source_eui(self):
        """Returns a netaddr.EUI representing the source MAC address."""
        return EUI(bytes_to_int(self.sender_hardware_bytes))

    @property
    def target_eui(self):
        """Returns a netaddr.EUI representing the target MAC address."""
        return EUI(bytes_to_int(self.target_hardware_bytes))

    @property
    def source_ip(self):
        """Returns a netaddr.IPAddress representing the source IP address."""
        return IPAddress(self.sender_protocol_bytes)

    @property
    def target_ip(self):
        """Returns a netaddr.IPAddress representing the target IP address."""
        return IPAddress(self.target_protocol_bytes)

    def is_valid(self):
        """Only (Ethernet MAC, IPv4) bindings are currently supported. This
        method ensures this ARP packet specifies those types.
        """
        # http://www.iana.org/assignments/arp-parameters/arp-parameters.xhtml
        # Hardware type 1 == Ethernet
        if self.hardware_type != 1:
            return False
        # Protocol type 0x800 == IPv4 (this should match the Ethertype)
        if self.protocol_type != 0x800:
            return False
        if self.hardware_length != 6:
            return False
        if self.protocol_length != 4:
            return False
        return True

    def bindings(self):
        """Yields each (MAC, IP) binding found in this ARP packet."""
        if not self.is_valid():
            return

        if self.operation == 1:
            # This is an ARP request.
            # We can find a binding in the (source_eui, source_ip)
            source_ip = self.source_ip
            source_eui = self.source_eui
            if int(source_ip) != 0 and int(source_eui) != 0:
                yield (source_ip, self.source_eui)
        elif self.operation == 2:
            # This is an ARP reply.
            # We can find a binding in both the (source_eui, source_ip) and
            # the (target_eui, target_ip).
            source_ip = self.source_ip
            source_eui = self.source_eui
            target_ip = self.target_ip
            target_eui = self.target_eui
            if int(source_ip) != 0 and int(source_eui) != 0:
                yield (source_ip, self.source_eui)
            if int(target_ip) != 0 and int(target_eui) != 0:
                yield (target_ip, self.target_eui)

    def write(self, out=sys.stdout):
        """Output text-based details about this ARP packet to the specified
        file or stream.
        :param out: An object with a `write(str)` method.
        """
        if self.time is not None:
            out.write(
                "ARP observed at %s:\n" % (datetime.fromtimestamp(self.time))
            )
        if self.vid is not None:
            out.write(
                f"   802.1q VLAN ID (VID): {self.vid} (0x{self.vid:03x})\n"
            )
        if self.src_mac is not None:
            out.write(
                "        Ethernet source: %s\n" % format_eui(self.src_mac)
            )
        if self.dst_mac is not None:
            out.write(
                "   Ethernet destination: %s\n" % format_eui(self.dst_mac)
            )
        out.write("          Hardware type: 0x%04x\n" % self.hardware_type)
        out.write("          Protocol type: 0x%04x\n" % self.protocol_type)
        out.write("Hardware address length: %d\n" % self.hardware_length)
        out.write("Protocol address length: %d\n" % self.protocol_length)
        out.write(
            "              Operation: %s\n" % (ARP_OPERATION(self.operation))
        )
        out.write(
            "Sender hardware address: %s\n" % (format_eui(self.source_eui))
        )
        out.write("Sender protocol address: %s\n" % self.source_ip)
        out.write(
            "Target hardware address: %s\n" % (format_eui(self.target_eui))
        )
        out.write("Target protocol address: %s\n" % self.target_ip)
        out.write("\n")


def update_bindings_and_get_event(bindings, vid, ip, mac, time):
    """Update the specified bindings dictionary and returns a dictionary if the
    information resulted in an update to the bindings. (otherwise, returns
    None.)

    If an event is returned, it will be a dictionary with the following fields:

        ip - The IP address of the binding.
        mac - The MAC address the IP was bound to.
        previous_mac - (if the IP moved between MACs) The previous MAC that
            was using the IP address.
        time - The time (in seconds since the epoch) the binding was observed.
        event - An event type; either "NEW", "MOVED", or "REFRESHED".
    """
    if (vid, ip) in bindings:
        binding = bindings[(vid, ip)]
        if binding["mac"] != mac:
            # Another MAC claimed ownership of this IP address. Update the
            # MAC and emit a "MOVED" event.
            previous_mac = binding["mac"]
            binding["mac"] = mac
            binding["time"] = time
            return dict(
                ip=str(ip),
                mac=format_eui(mac),
                time=time,
                event="MOVED",
                previous_mac=format_eui(previous_mac),
                vid=vid,
            )
        elif time - binding["time"] >= SEEN_AGAIN_THRESHOLD:
            binding["time"] = time
            return dict(
                ip=str(ip),
                mac=format_eui(mac),
                time=time,
                event="REFRESHED",
                vid=vid,
            )
        else:
            # The IP was found in the bindings dict, but within the
            # SEEN_AGAIN_THRESHOLD. Don't update the record; the time field
            # records the last time we emitted an event for this IP address.
            return None
    else:
        # We haven't seen this IP before, so add a binding for it and
        # emit a "NEW" event.
        bindings[(vid, ip)] = {"mac": mac, "time": time}
        return dict(
            ip=str(ip), mac=format_eui(mac), time=time, event="NEW", vid=vid
        )


def update_and_print_bindings(bindings, arp, out=sys.stdout):
    """Update the specified bindings dictionary with the given ARP packet.

    Output a JSON object on the specified stream (defaults to stdout) based on
    the results of updating the binding.
    """
    for ip, mac in arp.bindings():
        event = update_bindings_and_get_event(
            bindings, arp.vid, ip, mac, arp.time
        )
        if event is not None:
            out.write("%s\n" % json.dumps(event))
            out.flush()


def observe_arp_packets(
    verbose=False, bindings=False, input=sys.stdin.buffer, output=sys.stdout
):
    """Read stdin and look for tcpdump binary ARP output.
    :param verbose: Output text-based ARP packet details.
    :type verbose: bool
    :param bindings: Track (MAC, IP) bindings, and print new/update bindings.
    :type bindings: bool
    :param input: Stream to read PCAP data from.
    :type input: a file or stream supporting `read(int)`
    :param output: Stream to write JSON data to.
    :type input: a file or stream supporting `write(str)` and `flush()`.
    """
    if bindings:
        bindings = dict()
    else:
        bindings = None
    try:
        pcap = PCAP(input)
        if pcap.global_header.data_link_type != 1:
            # Not an Ethernet interface. Need to exit here, because our
            # assumptions about the link layer header won't be correct.
            return 4
        for header, packet in pcap:
            ethernet = Ethernet(packet, time=header.timestamp_seconds)
            if not ethernet.is_valid():
                # Ignore packets with a truncated Ethernet header.
                continue
            if len(ethernet.payload) < SIZEOF_ARP_PACKET:
                # Ignore truncated ARP packets.
                continue
            if ethernet.ethertype != ETHERTYPE.ARP:
                # Ignore non-ARP packets.
                continue
            arp = ARP(
                ethernet.payload,
                src_mac=ethernet.src_mac,
                dst_mac=ethernet.dst_mac,
                vid=ethernet.vid,
                time=ethernet.time,
            )
            if bindings is not None:
                update_and_print_bindings(bindings, arp, output)
            if verbose:
                arp.write()
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
        Observes the traffic on the specified interface, looking for ARP
        traffic. Outputs JSON objects (one per line) for each NEW, REFRESHED,
        or MOVED binding.

        Reports on REFRESHED bindings at most once every ten minutes.
        """
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        required=False,
        help="Print verbose packet information.",
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
        "call `sudo /usr/lib/maas/network-monitor` to get input.",
    )


def run(
    args, output=sys.stdout, stdin=sys.stdin, stdin_buffer=sys.stdin.buffer
):
    """Observe an Ethernet interface and print ARP bindings."""

    # First, become a progress group leader, so that signals can be directed
    # to this process and its children; see p.u.twisted.terminateProcess.
    os.setpgrp()

    network_monitor = None
    if args.input_file is None:
        if args.interface is None:
            raise ActionScriptError("Required argument: interface")
        cmd = [get_path("/usr/lib/maas/network-monitor"), args.interface]
        cmd = sudo(cmd)
        network_monitor = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE
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
    return_code = observe_arp_packets(
        bindings=True, verbose=args.verbose, input=infile, output=output
    )
    if return_code is not None:
        raise SystemExit(return_code)
    if network_monitor is not None:
        return_code = network_monitor.poll()
        if return_code is not None:
            raise SystemExit(return_code)
