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


# UDP ports for the BOOTP protocol.  Used for discovery requests.
BOOTP_SERVER_PORT = 67
BOOTP_CLIENT_PORT = 68

# ioctl request for requesting IP address.
SIOCGIFADDR = 0x8915

# ioctl request for requesting hardware (MAC) address.
SIOCGIFHWADDR = 0x8927


def get_interface_MAC(sock, interface):
    """Obtain a network interface's MAC address, as a string."""
    ifreq = struct.pack(b'256s', interface.encode('ascii')[:15])
    info = fcntl.ioctl(sock.fileno(), SIOCGIFHWADDR,  ifreq)
    mac = ''.join(['%02x:' % ord(char) for char in info[18:24]])[:-1]
    return mac


def get_interface_IP(sock, interface):
    """Obtain an IP address for a network interface, as a string."""
    ifreq = struct.pack(
        b'16sH14s', interface.encode('ascii')[:15], socket.AF_INET, b'\x00'*14)
    info = fcntl.ioctl(sock, SIOCGIFADDR, ifreq)
    ip = struct.unpack(b'16sH2x4s8x', info)[2]
    return socket.inet_ntoa(ip)


def probe_dhcp(interface):
    """Look for a DHCP server on the network.

    This must be run with provileges to broadcast from the BOOTP port, which
    typically requires root.  It may fail to bind to that port if a DHCP client
    is running on that same interface.

    :param interface: Network interface name, e.g. "eth0", attached to the
        network you wish to probe.
    :return: Set of discovered DHCP servers.

    :exception IOError: If the interface does not have an IP address.
    """
    servers = set()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        mac = get_interface_MAC(sock, interface)
        bind_address = get_interface_IP(sock, interface)

        sock.bind((bind_address, BOOTP_CLIENT_PORT))
        discover = DHCPDiscoverPacket(mac)
        sock.sendto(discover.packet, ('<broadcast>', BOOTP_SERVER_PORT))

        # Close the socket and rebind it to IN_ANY, because DHCP servers
        # reply using the broadcast address and we won't see that if
        # still bound to the interface's address.
        sock.close()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', BOOTP_CLIENT_PORT))

        while True:
            sock.settimeout(3)
            try:
                data = sock.recv(1024)
            except socket.timeout:
                break
            offer = DHCPOfferPacket(data)
            if offer.transaction_ID == discover.transaction_ID:
                servers.add(offer.dhcp_server_ID)
    finally:
        sock.close()

    return servers
