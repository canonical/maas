# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with PCAP format streams."""

from collections import namedtuple
from pprint import pprint
import struct
import sys

# See documentation here for explanation of magic numbers, formats, etc:
#     https://wiki.wireshark.org/Development/LibpcapFileFormat
PCAP_NATIVE_BYTE_ORDER_MAGIC_NUMBER = 0xA1B2C3D4
PCAP_HEADER_SIZE = 24
PCAP_PACKET_HEADER_SIZE = 16

PCAPHeader = namedtuple(
    "PCAPHeader",
    (
        "magic_number",
        "pcap_version_major",
        "pcap_version_minor",
        "time_zone_gmt_offset",
        "timestamp_accuracy_sigfigs",
        "max_capture_bytes_per_packet",
        "data_link_type",
    ),
)

PCAPPacketHeader = namedtuple(
    "PCAPPacketHeader",
    (
        "timestamp_seconds",
        "timestamp_microseconds",
        "bytes_captured",
        "original_packet_length",
    ),
)


class PCAPError(IOError):
    """Exception class for problems originating in the PCAP I/O stream."""

    pass


class PCAP:
    """Class to encapsulate reading from a stream of PCAP capture output.

    The capture output is assumed to have been obtained on the same machine
    as this class is running, so no byte-swapping is needed for compatibility
    with architectures of differing endianness.
    """

    def __init__(self, stream):
        """Initializes the PCAP stream reader with the specified stream.

        Stores the global PCAP header in self.global_header, as a namedtuple
        of: (magic_number, pcap_version_major, pcap_version_minor,
        time_zone_gmt_offset, timestamp_accuracy_sigfigs,
        max_capture_bytes_per_packet, data_link_type).
        :raise EOFError: If an empty stream was supplied.
        :raise PCAPError: If the PCAP stream was invalid.
        """
        super().__init__()
        self.stream = stream
        global_header_bytes = stream.read(PCAP_HEADER_SIZE)
        if len(global_header_bytes) == 0:
            raise EOFError("No PCAP output found.")
        if len(global_header_bytes) != PCAP_HEADER_SIZE:
            raise PCAPError("Unexpected end of PCAP stream: invalid header.")
        # typedef struct pcap_hdr_s {
        #     guint32 magic_number;   /* magic number */
        #     guint16 version_major;  /* major version number */
        #     guint16 version_minor;  /* minor version number */
        #     gint32  thiszone; /* GMT to local correction */
        #     guint32 sigfigs;  /* accuracy of timestamps */
        #     guint32 snaplen;  /* max length of captured packets, in octets */
        #     guint32 network;  /* data link type */
        # } pcap_hdr_t;
        self.global_header = PCAPHeader._make(
            struct.unpack("IHHiIII", global_header_bytes)
        )
        if self.global_header[0] != PCAP_NATIVE_BYTE_ORDER_MAGIC_NUMBER:
            raise PCAPError("Stream is not in native PCAP format.")

    def read(self):
        """Reads a packet from the PCAP stream.

        :returns: a tuple of the format (pcap_packet_header, packet),
            where the pcap_packet_header is a namedtuple in the format:
            (timestamp_seconds, timestamp_microseconds, bytes_captured,
            original_packet_length), and the packet is of type `bytes` and
            matches the bytes_captured field in the tuple.
        :raise EOFError: If this is an attempt to read beyond the last packet.
        :raise PCAPError: If the PCAP stream was invalid.
        """
        pcap_packet_header_bytes = self.stream.read(PCAP_PACKET_HEADER_SIZE)
        if len(pcap_packet_header_bytes) == 0:
            raise EOFError("End of PCAP stream.")
        if len(pcap_packet_header_bytes) != PCAP_PACKET_HEADER_SIZE:
            raise PCAPError(
                "Unexpected end of PCAP stream: invalid packet header."
            )
        # typedef struct pcaprec_hdr_s {
        #     guint32 ts_sec;   /* timestamp seconds */
        #     guint32 ts_usec;  /* timestamp microseconds */
        #     guint32 incl_len; /* number of octets of packet saved in file */
        #     guint32 orig_len; /* actual length of packet */
        # } pcaprec_hdr_t;
        pcap_packet_header = PCAPPacketHeader._make(
            struct.unpack("IIII", pcap_packet_header_bytes)
        )
        packet = self.stream.read(pcap_packet_header.bytes_captured)
        if len(packet) != pcap_packet_header.bytes_captured:
            raise PCAPError("Unexpected end of PCAP stream: invalid packet.")
        return pcap_packet_header, packet

    def __iter__(self):
        """Iterate this PCAP stream.

        Stops when EOF is encountered."""
        while True:
            try:
                yield self.read()
            except EOFError:
                break


def main():
    """Debug function for printing packets output by tcpdump on stdin.

    Example usage:
        cd src
        sudo tcpdump -i eth0 -U --immediate-mode -s 64 -n -w - arp \
        | python3 -m provisioningserver.utils.pcap
    """
    packet_stream = PCAP(sys.stdin.buffer)
    pprint(packet_stream.global_header)
    for packet in packet_stream:
        pprint(packet)


if __name__ == "__main__":
    main()
