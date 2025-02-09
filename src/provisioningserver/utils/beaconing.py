# Copyright 2016-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with beaconing packets."""

from collections import namedtuple
from gzip import compress, decompress
import json
import math
import os
import stat
import struct
import subprocess
import sys
from textwrap import dedent
import time
import uuid
from uuid import UUID

from bson import BSON
from bson.errors import BSONError
from cryptography.fernet import InvalidToken

from provisioningserver.path import get_path
from provisioningserver.security import fernet_decrypt_psk, fernet_encrypt_psk
from provisioningserver.utils import sudo
from provisioningserver.utils.network import format_eui
from provisioningserver.utils.pcap import PCAP, PCAPError
from provisioningserver.utils.script import ActionScriptError
from provisioningserver.utils.tcpip import (
    decode_ethernet_udp_packet,
    PacketProcessingError,
)

BEACON_PORT = 5240
BEACON_IPV4_MULTICAST = "224.0.0.118"
BEACON_IPV6_MULTICAST = "ff02::15a"


BEACON_TYPES = {"solicitation": 1, "advertisement": 2}

BEACON_TYPE_VALUES = {value: name for name, value in BEACON_TYPES.items()}

PROTOCOL_VERSION = 1
BEACON_HEADER_FORMAT_V1 = "!BBH"
BEACON_HEADER_LENGTH_V1 = 4


BeaconPayload = namedtuple(
    "BeaconPayload", ("bytes", "version", "type", "payload")
)

ReceivedBeacon = namedtuple(
    "ReceivedBeacon",
    ("uuid", "json", "ifname", "ifinfo", "vid", "reply_address", "multicast"),
)

TopologyHint = namedtuple(
    "TopologyHint",
    ("ifname", "vid", "hint", "related_ifname", "related_vid", "related_mac"),
)


def uuid_to_timestamp(uuid_str):
    """Given the specified UUID string, returns the timestamp.

    The timestamp returned should be comparable to what would be returned
    from `import time; time.time()`.

    :param uuid_str: a UUID in string format
    :return: float
    """
    uuid_time = UUID(uuid_str).time
    # Reverse the algorithm in uuid.py.
    timestamp = (uuid_time - 0x01B21DD213814000) * 100 / 1e9
    return timestamp


def age_out_uuid_queue(queue, threshold=120.0):
    """Ages out a ordered dictionary (using UUID-based keys) based on time.

    The given threshold (in seconds) indicates how old an entry can be
    before it will be removed from the queue.

    :param queue: An `OrderedDict` with UUID strings as keys.
    :param threshold: The maximum time an entry can remain in the queue.
    """
    removals = []
    current_time = time.time()
    for key in queue:
        beacon_timestamp = uuid_to_timestamp(key)
        # Don't leave beacons from the future in the queue if the clock
        # suddenly changes. (This shouldn't happen, since the Fernet TTL
        # should not have allowed them through. But just in case.)
        difference = math.fabs(current_time - beacon_timestamp)
        # Age out beacons greater than two minutes old.
        if difference > threshold:
            removals.append(key)
        else:
            # If we're already encountering packets that haven't met the age
            # threshold (and were received more recently, and thus are later
            # in the queue) then it's time to give up. (Yes, it's possible that
            # clock skew could be an issue here, but after a couple of minutes,
            # it won't matter.)
            break
    for uuid_to_remove in removals:
        queue.pop(uuid_to_remove, None)


def beacon_to_json(beacon_payload):
    """Converts the specified beacon into a format suitable for JSON."""
    return {
        "version": beacon_payload.version,
        "type": beacon_payload.type,
        "payload": beacon_payload.payload,
    }


def create_beacon_payload(beacon_type, payload=None, version=PROTOCOL_VERSION):
    """Creates a beacon payload of the specified type, with the given data.

    :param beacon_type: The beacon packet type. Indicates the purpose of the
        beacon to the receiver.
    :param payload: Optional JSON-encodable dictionary. Will be converted to an
        inner encrypted payload and presented in the "data" field in the
        resulting dictionary.
    :param version: Optional protocol version to use (defaults to most recent).
    :return: BeaconPayload namedtuple representing the packet bytes, the outer
        payload, and the inner encrypted data (if any).
    """
    beacon_type_code = BEACON_TYPES[beacon_type]
    if payload is not None:
        payload = payload.copy()
        payload["uuid"] = str(uuid.uuid1())
        payload["type"] = beacon_type_code
        data_bytes = BSON.encode(payload)
        compressed_bytes = compress(data_bytes, compresslevel=9)
        payload_bytes = fernet_encrypt_psk(compressed_bytes, raw=True)
    else:
        payload_bytes = b""
    beacon_bytes = struct.pack(
        BEACON_HEADER_FORMAT_V1 + "%ds" % len(payload_bytes),
        version,
        beacon_type_code,
        len(payload_bytes),
        payload_bytes,
    )
    return BeaconPayload(
        beacon_bytes, version, BEACON_TYPE_VALUES[beacon_type_code], payload
    )


def read_beacon_payload(beacon_bytes):
    """Returns a BeaconPayload namedtuple representing the given beacon bytes.

    Decrypts the inner beacon data if necessary.

    :param beacon_bytes: beacon payload (bytes).
    :return: BeaconPayload namedtuple
    """
    if len(beacon_bytes) < BEACON_HEADER_LENGTH_V1:
        raise InvalidBeaconingPacket(
            "Beaconing packet must be at least %d bytes."
            % BEACON_HEADER_LENGTH_V1
        )
    header = beacon_bytes[:BEACON_HEADER_LENGTH_V1]
    version, beacon_type_code, expected_payload_length = struct.unpack(
        BEACON_HEADER_FORMAT_V1, header
    )
    actual_payload_length = len(beacon_bytes) - BEACON_HEADER_LENGTH_V1
    if len(beacon_bytes) - BEACON_HEADER_LENGTH_V1 < expected_payload_length:
        raise InvalidBeaconingPacket(
            "Invalid payload length: expected %d bytes, got %d bytes."
            % (expected_payload_length, actual_payload_length)
        )
    payload_start = BEACON_HEADER_LENGTH_V1
    payload_end = BEACON_HEADER_LENGTH_V1 + expected_payload_length
    payload_bytes = beacon_bytes[payload_start:payload_end]
    payload = None
    if version == 1:
        if len(payload_bytes) == 0:
            # No encrypted inner payload; nothing to do.
            pass
        else:
            try:
                decrypted_data = fernet_decrypt_psk(
                    payload_bytes, ttl=60, raw=True
                )
            except InvalidToken:
                raise InvalidBeaconingPacket(  # noqa: B904
                    "Failed to decrypt inner payload: check MAAS secret key."
                )
            try:
                decompressed_data = decompress(decrypted_data)
            except OSError:
                raise InvalidBeaconingPacket(  # noqa: B904
                    "Failed to decompress inner payload: %r" % decrypted_data
                )
            try:
                # Replace the data in the dictionary with its decrypted form.
                payload = BSON.decode(decompressed_data)
            except BSONError:
                raise InvalidBeaconingPacket(  # noqa: B904
                    "Inner beacon payload is not BSON: %r" % decompressed_data
                )
    else:
        raise InvalidBeaconingPacket("Unknown beacon version: %d" % version)
    beacon_type_code = payload["type"] if payload else beacon_type_code
    return BeaconPayload(
        beacon_bytes, version, BEACON_TYPE_VALUES[beacon_type_code], payload
    )


class InvalidBeaconingPacket(Exception):
    """Raised when a beaconing packet is not valid."""

    def __init__(self, invalid_reason):
        self.invalid_reason = invalid_reason
        super().__init__(invalid_reason)


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
        self.data = self.parse()

    def parse(self):
        try:
            beacon = read_beacon_payload(self.packet)
            self.valid = True
            return beacon
        except InvalidBeaconingPacket as ibp:
            self.valid = False
            self.invalid_reason = ibp.invalid_reason
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
                if not beacon.valid:
                    continue
                output_json = {
                    "source_mac": format_eui(packet.l2.src_eui),
                    "destination_mac": format_eui(packet.l2.dst_eui),
                    "source_ip": str(packet.l3.src_ip),
                    "destination_ip": str(packet.l3.dst_ip),
                    "source_port": packet.l4.packet.src_port,
                    "destination_port": packet.l4.packet.dst_port,
                    "time": pcap_header.timestamp_seconds,
                }
                if packet.l2.vid is not None:
                    output_json["vid"] = packet.l2.vid
                if beacon.data is not None:
                    output_json.update(beacon_to_json(beacon.data))
                out.write(json.dumps(output_json))
                out.write("\n")
                out.flush()
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
    parser.description = dedent(
        """\
        Observes beaconing traffic on the specified interface.
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
        help="File to read beaconing output from. Use - for stdin. Default is "
        "to call `sudo /usr/lib/maas/beacon-monitor` to get input.",
    )


def run(
    args, output=sys.stdout, stdin=sys.stdin, stdin_buffer=sys.stdin.buffer
):
    """Observe an Ethernet interface and print beaconing packets."""

    # First, become a progress group leader, so that signals can be directed
    # to this process and its children; see p.u.twisted.terminateProcess.
    os.setpgrp()

    network_monitor = None
    if args.input_file is None:
        if args.interface is None:
            raise ActionScriptError("Required argument: interface")
        cmd = sudo([get_path("/usr/lib/maas/beacon-monitor"), args.interface])
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
    return_code = observe_beaconing_packets(input=infile, out=output)
    if return_code is not None:
        raise SystemExit(return_code)
    if network_monitor is not None:
        return_code = network_monitor.poll()
        if return_code is not None:
            raise SystemExit(return_code)
