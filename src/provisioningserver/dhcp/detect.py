# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities and helpers to help discover DHCP servers on your network."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


import fcntl
from random import randint
import socket
import struct


class DHCPDiscoverPacket:
    """A representation of a DHCP_DISCOVER packet.

    :param my_mac: The MAC address to which the dhcp server should respond.
        Normally this is the MAC of the interface you're using to send the
        request.
    """

    def __init__(self, my_mac):
        self.transaction_ID = b''
        for _ in range(4):
            self.transaction_ID += struct.pack(b'!B', randint(0, 255))
        self.packed_mac = self.string_mac_to_packed(my_mac)
        self._build()

    @classmethod
    def string_mac_to_packed(cls, mac):
        """Convert a string MAC address to 6 hex octets.

        :param mac: A MAC address in the format AA:BB:CC:DD:EE:FF
        :return: a byte string of length 6
        """
        packed = b''
        for pair in mac.split(':'):
            hex_octet = int(pair, 16)
            packed += struct.pack(b'!B', hex_octet)
        return packed

    def _build(self):
        self.packet = b''
        self.packet += b'\x01'  # Message type: Boot Request (1)
        self.packet += b'\x01'  # Hardware type: Ethernet
        self.packet += b'\x06'  # Hardware address length: 6
        self.packet += b'\x00'  # Hops: 0
        self.packet += self.transaction_ID
        self.packet += b'\x00\x00'  # Seconds elapsed: 0

        # Bootp flags: 0x8000 (Broadcast) + reserved flags
        self.packet += b'\x80\x00'

        self.packet += b'\x00\x00\x00\x00'  # Client IP address: 0.0.0.0
        self.packet += b'\x00\x00\x00\x00'  # Your (client) IP address: 0.0.0.0
        self.packet += b'\x00\x00\x00\x00'  # Next server IP address: 0.0.0.0
        self.packet += b'\x00\x00\x00\x00'  # Relay agent IP address: 0.0.0.0
        self.packet += self.packed_mac

        # Client hardware address padding: 00000000000000000000
        self.packet += b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

        self.packet += b'\x00' * 67  # Server host name not given
        self.packet += b'\x00' * 125  # Boot file name not given
        self.packet += b'\x63\x82\x53\x63'  # Magic cookie: DHCP

        # Option: (t=53,l=1) DHCP Message Type = DHCP Discover
        self.packet += b'\x35\x01\x01'

        self.packet += b'\x3d\x06' + self.packed_mac

        # Option: (t=55,l=3) Parameter Request List
        self.packet += b'\x37\x03\x03\x01\x06'

        self.packet += b'\xff'   # End Option


class DHCPOfferPacket:
    """A representation of a DHCP_OFFER packet."""

    def __init__(self, data):
        self.transaction_ID = data[4:8]
        self.dhcp_server_ID = socket.inet_ntoa(data[245:249])


# Example code to drive the above classes.
if __name__ == '__main__':
    # Set UDP.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Set broadcast mode.
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    # Work out what MAC address eth0 has.
    ifname = b"eth0"
    info = fcntl.ioctl(
        sock.fileno(), 0x8927,  struct.pack(b'256s', ifname[:15]))
    # s/ord/str/ for Python3 here:
    mac = ''.join(['%02x:' % ord(char) for char in info[18:24]])[:-1]

    # DHCP requires that you send from the privileged port 68. (requires
    # root permissions)
    try:
        sock.bind(('', 68))
    except socket.error as e:
        print("Unable to bind socket: %s" % e)
        sock.close()
        exit()

    discover = DHCPDiscoverPacket(mac)
    sock.sendto(discover.packet, ('<broadcast>', 67))

    sock.settimeout(3)
    try:
        data = sock.recv(1024)
        offer = DHCPOfferPacket(data)
        if offer.transaction_ID == discover.transaction_ID:
            print("Offer received from %s" % offer.dhcp_server_ID)
    except socket.timeout:
        pass

    sock.close()
