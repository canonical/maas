# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with ARP packets."""

__all__ = [
    "ARP"
]

from collections import namedtuple
from datetime import datetime
import json
import os
import stat
import struct
import sys

from netaddr import (
    EUI,
    IPAddress,
)
from provisioningserver.utils.network import (
    bytes_to_int,
    format_eui,
    hex_str_to_bytes,
)
from provisioningserver.utils.pcap import (
    PCAP,
    PCAPError,
)

# The SEEN_AGAIN_THRESHOLD is a time (in seconds) that determines how often
# to report (IP, MAC) bindings that have been seen again (or "REFRESHED").
# While it is important for MAAS to know about "NEW" and "MOVED" bindings
# immediately, "REFRESHED" bindings occur too often to be useful, and
# are thus throttled by this value.
SEEN_AGAIN_THRESHOLD = 600

# Definitions for ARP packet used with `struct`.
ARP_PACKET = '!hhBBh6sL6sL'
ARPPacket = namedtuple('ARPPacket', (
    'hardware_type',
    'protocol',
    'hardware_length',
    'protocol_length',
    'operation',
    'sender_mac',
    'sender_ip',
    'target_mac',
    'target_ip',
))


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
                'ARP_OPERATION may only be added to `bytes`.')


class ARP:
    """Representation of an ARP packet."""

    def __init__(self, pkt_bytes, time=None, src_mac=None, dst_mac=None):
        """
        :param pkt_bytes: The input bytes of the ARP packet.
        :type pkt_bytes: bytes
        :param time: Timestamp packet was seen (seconds since epoch)
        :type time: str
        :param src_mac: Source MAC address from Ethernet header.
        :type src_mac: bytes
        :param dst_mac: Destination MAC address from Ethernet header.
        :type dst_mac: bytes
        :return:
        """
        # Truncate the packet at 28 bytes.
        packet = ARPPacket._make(
            struct.unpack(ARP_PACKET, pkt_bytes[0:28]))
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
            if int(source_ip) != 0:
                yield (source_ip, self.source_eui)
        elif self.operation == 2:
            # This is an ARP reply.
            # We can find a binding in both the (source_eui, source_ip) and
            # the (target_eui, target_ip).
            source_ip = self.source_ip
            target_ip = self.target_ip
            if int(source_ip) != 0:
                yield (source_ip, self.source_eui)
            if int(target_ip) != 0:
                yield (target_ip, self.target_eui)

    def write(self, out=sys.stdout):
        """Output text-based details about this ARP packet to the specified
        file or stream.
        :param out: An object with a `write(str)` method.
        """
        if self.time is not None:
            out.write("ARP observed at %s:\n" % (
                datetime.fromtimestamp(self.time)))
        if self.src_mac is not None:
            out.write("        Ethernet source: %s\n" % format_eui(
                self.src_mac))
        if self.dst_mac is not None:
            out.write("   Ethernet destination: %s\n" % format_eui(
                self.dst_mac))
        out.write("          Hardware type: 0x%04x\n" % self.hardware_type)
        out.write("          Protocol type: 0x%04x\n" % self.protocol_type)
        out.write("Hardware address length: %d\n" % self.hardware_length)
        out.write("Protocol address length: %d\n" % self.protocol_length)
        out.write("              Operation: %s\n" % (
            ARP_OPERATION(self.operation)))
        out.write("Sender hardware address: %s\n" % (
            format_eui(self.source_eui)))
        out.write("Sender protocol address: %s\n" % self.source_ip)
        out.write("Target hardware address: %s\n" % (
            format_eui(self.target_eui)))
        out.write("Target protocol address: %s\n" % self.target_ip)
        out.write("\n")


def update_bindings_and_get_event(bindings, ip, mac, time):
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
    if ip in bindings:
        binding = bindings[ip]
        if binding['mac'] != mac:
            # Another MAC claimed ownership of this IP address. Update the
            # MAC and emit a "MOVED" event.
            previous_mac = binding['mac']
            binding['mac'] = mac
            binding['time'] = time
            return (dict(
                ip=str(ip), mac=format_eui(mac), time=time, event="MOVED",
                previous_mac=format_eui(previous_mac)))
        elif time - binding['time'] >= SEEN_AGAIN_THRESHOLD:
            binding['time'] = time
            return dict(
                ip=str(ip), mac=format_eui(mac), time=time,
                event="REFRESHED")
        else:
            # The IP was found in the bindings dict, but within the
            # SEEN_AGAIN_THRESHOLD. Don't update the record; the time field
            # records the last time we emitted an event for this IP address.
            return None
    else:
        # We haven't seen this IP before, so add a binding for it and
        # emit a "NEW" event.
        bindings[ip] = {'mac': mac, 'time': time}
        return dict(
            ip=str(ip), mac=format_eui(mac), time=time,
            event="NEW")


def update_and_print_bindings(bindings, arp, out=sys.stdout):
    """Update the specified bindings dictionary with the given ARP packet.

    Output a JSON object on the specified stream (defaults to stdout) based on
    the results of updating the binding.
    """
    for ip, mac in arp.bindings():
        event = update_bindings_and_get_event(bindings, ip, mac, arp.time)
        if event is not None:
            out.write("%s\n" % json.dumps(event))
            out.flush()


def observe_arp_packets(
        verbose=False, bindings=False, input=sys.stdin.buffer):
    """Read stdin and look for tcpdump binary ARP output.
    :param verbose: Output text-based ARP packet details.
    :type verbose: bool
    :param bindings: Track (MAC, IP) bindings, and print new/update bindings.
    :type bindings: bool
    :param input: Stream to read PCAP data from.
    :type input: a file or stream supporting `read(int)`
    """
    arp_ethertype = hex_str_to_bytes('0806')
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
            src_mac, dst_mac, ethertype = struct.unpack('6s6s2s', packet[:14])
            if len(packet) < (14 + 28):
                # Ignore truncated packets.
                continue
            if ethertype != arp_ethertype:
                # Ignore non-ARP packets.
                continue
            arp = ARP(
                packet[14:], src_mac=src_mac, dst_mac=dst_mac,
                time=header.timestamp_seconds)
            if bindings is not None:
                update_and_print_bindings(bindings, arp)
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


def main(argv, err=sys.stderr):
    """Main entry point. Ensure stdin is a pipe, then check command-line
    arguments and run the ARP observation loop.

    Assuming you are in the 'src' directory, this file can be tested
    interactively by invoking as follows:

    sudo tcpdump -i eth0 -U --immediate-mode -s 64 -n -w - arp \
        | python3 -m provisioningserver.utils.arp -v -b

    (Use the name of an Ethernet interface in place of 'eth0' in the above
    command.)

    :param argv: The contents of sys.argv.
    :param err: Output stream for errors.
    """
    mode = os.fstat(sys.stdin.fileno()).st_mode
    if not stat.S_ISFIFO(mode):
        err.write("Usage:\n")
        err.write("    sudo tcpdump -i eth0 -U --immediate-mode -s 64 -n -w - "
                  "arp 2> /dev/null | %s [args]\n" % (argv[0]))
        err.write("\n")
        err.write("Arguments:\n")
        err.write("    -v --verbose  Print each ARP packet.\n")
        err.write("    -b --bindings Track each (MAC,IP) binding and print\n"
                  "                  new or changed bindings to stdout.\n")
        return 1
    verbose = False
    bindings = False
    if '-v' in argv or '--verbose' in argv:
        verbose = True
    if '-b' in argv or '--bindings' in argv:
        bindings = True
    return observe_arp_packets(
        verbose=verbose, bindings=bindings)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
