# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for dhcp/detect.py"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.dhcp.detect import (
    DHCPDiscoverPacket,
    DHCPOfferPacket,
    )


class TestDHCPDiscoverPacket(MAASTestCase):

    def test_init_sets_transaction_ID(self):
        # The dhcp transaction should be 4 bytes long.
        discover = DHCPDiscoverPacket(factory.getRandomMACAddress())
        self.assertIsInstance(discover.transaction_ID, bytes)
        self.assertEqual(4, len(discover.transaction_ID))

    def test_init_sets_packed_mac(self):
        mac = factory.getRandomMACAddress()
        discover = DHCPDiscoverPacket(mac)
        self.assertEqual(
            discover.string_mac_to_packed(mac),
            discover.packed_mac)

    def test_init_sets_packet(self):
        discover = DHCPDiscoverPacket(factory.getRandomMACAddress())
        self.assertIsNotNone(discover.packet)

    def test_string_mac_to_packed(self):
        discover = DHCPDiscoverPacket
        expected = b"\x01\x22\x33\x99\xaa\xff"
        input = "01:22:33:99:aa:ff"
        self.assertEqual(expected, discover.string_mac_to_packed(input))

    def test__build(self):
        mac = factory.getRandomMACAddress()
        discover = DHCPDiscoverPacket(mac)
        discover._build()

        expected = (
            b'\x01\x01\x06\x00' + discover.transaction_ID +
            b'\x00\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00' +
            b'\x00\x00\x00\x00\x00\x00\x00\x00' +
            discover.packed_mac +
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' +
            b'\x00' * 67 +
            b'\x00' * 125 +
            b'\x63\x82\x53\x63\x35\x01\x01\x3d\x06' + discover.packed_mac +
            b'\x37\x03\x03\x01\x06\xff')

        self.assertEqual(expected, discover.packet)


class TestDHCPOfferPacket(MAASTestCase):

    def test_decodes_dhcp_server(self):
        buffer = b'\x00' * 245 + b'\x10\x00\x00\xaa'
        offer = DHCPOfferPacket(buffer)
        self.assertEqual('16.0.0.170', offer.dhcp_server_ID)
