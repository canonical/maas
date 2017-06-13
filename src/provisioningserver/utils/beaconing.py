# Copyright 2016-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with beaconing packets."""

__all__ = [
    "BeaconingPacket",
    "add_arguments",
    "run"
]

import json
import os
import stat
import subprocess
import sys
from textwrap import dedent

import bson
from provisioningserver.utils import sudo
from provisioningserver.utils.network import format_eui
from provisioningserver.utils.pcap import (
    PCAP,
    PCAPError,
)
from provisioningserver.utils.script import ActionScriptError
from provisioningserver.utils.tcpip import (
    decode_ethernet_udp_packet,
    PacketProcessingError,
)


class InvalidBeaconingPacket(Exception):
    """Raised internally when a beaconing packet is not valid."""


class BeaconingPacket:
    """Representation of a beaconing packet."""

    def __init__(self, pkt_bytes: bytes):
        """
        Create a beaconing packet, given the specified upper-layer packet.

        :param pkt_bytes: The input bytes of the beaconing packet.
        :type pkt_bytes: bytes
        """
        super().__init__()
        self.valid = None
        self.invalid_reason = None
        self.packet = pkt_bytes
        self.payload = self.parse()

    def parse(self):
        """Output text-based details about this beaconing packet to the
        specified file or stream.

        :param out: An object with `write(str)` and `flush()` methods.
        """
        try:
            payload = bson.decode_all(self.packet)
            self.valid = True
            return payload
        except bson.InvalidBSON:
            self.valid = False
            self.invalid_reason = "Packet payload is not BSON."
            return None


def observe_beaconing_packets(input=sys.stdin.buffer, out=sys.stdout):
    """Read stdin and look for tcpdump binary beaconing output.

    :param input: Stream to read PCAP data from.
    :type input: a file or stream supporting `read(int)`
    :param out: Stream to write to.
    :type input: a file or stream supporting `write(str)` and `flush()`.
    """
    err = sys.stderr
    try:
        pcap = PCAP(input)
        if pcap.global_header.data_link_type != 1:
            # Not an Ethernet interface. Need to exit here, because our
            # assumptions about the link layer header won't be correct.
            return 4
        for pcap_header, packet_bytes in pcap:
            try:
                packet = decode_ethernet_udp_packet(packet_bytes, pcap_header)
                beacon = BeaconingPacket(packet.payload)
                output_json = {
                    "source_mac": format_eui(packet.l2.src_eui),
                    "destination_mac": format_eui(packet.l2.dst_eui),
                    "source_ip": str(packet.l3.src_ip),
                    "destination_ip": str(packet.l3.dst_ip),
                }
                if packet.l2.vid is not None:
                    output_json["vid"] = packet.l2.vid
                if beacon.payload is not None:
                    output_json['payload'] = beacon.payload
                    output_json['time'] = pcap_header.timestamp_seconds
                    out.write(json.dumps(output_json))
                    out.write('\n')
                    out.flush()
                else:
                    err.write(
                        "Invalid beacon payload (not BSON): %r.\n" % (
                            beacon.packet))
                    err.flush()
            except PacketProcessingError as e:
                err.write(e.error)
                err.write("\n")
                err.flush()
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
    parser.description = dedent("""\
        Observes beaconing traffic on the specified interface.
        """)
    parser.add_argument(
        'interface', type=str, nargs='?',
        help="Ethernet interface from which to capture traffic. Optional if "
             "an input file is specified.")
    parser.add_argument(
        '-i', '--input-file', type=str, required=False,
        help="File to read beaconing output from. Use - for stdin. Default is "
             "to call `sudo /usr/lib/maas/maas-beacon-monitor` to get input.")


def run(args, output=sys.stdout, stdin=sys.stdin,
        stdin_buffer=sys.stdin.buffer):
    """Observe an Ethernet interface and print beaconing packets."""

    # First, become a progress group leader, so that signals can be directed
    # to this process and its children; see p.u.twisted.terminateProcess.
    os.setpgrp()

    network_monitor = None
    if args.input_file is None:
        if args.interface is None:
            raise ActionScriptError("Required argument: interface")
        cmd = sudo(["/usr/lib/maas/maas-beacon-monitor", args.interface])
        network_monitor = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE)
        infile = network_monitor.stdout
    else:
        if args.input_file == '-':
            mode = os.fstat(stdin.fileno()).st_mode
            if not stat.S_ISFIFO(mode):
                raise ActionScriptError("Expected stdin to be a pipe.")
            infile = stdin_buffer
        else:
            infile = open(args.input_file, "rb")
    return_code = observe_beaconing_packets(input=infile, out=output)
    if return_code is not None:
        raise SystemExit(return_code)
    if network_monitor is not None:
        return_code = network_monitor.poll()
        if return_code is not None:
            raise SystemExit(return_code)
