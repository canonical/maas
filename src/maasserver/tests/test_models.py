# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver models."""

from __future__ import print_function

__metaclass__ = type
__all__ = []

from django.core.exceptions import ValidationError
from maas.testing import TestCase
from maasserver.models import (
    MACAddress,
    Node,
    )


class NodeTest(TestCase):

    def setUp(self):
        super(NodeTest, self).setUp()
        self.node = Node()
        self.node.save()

    def test_system_id(self):
        """
        The generated system_id looks good.

        """
        self.assertEqual(len(self.node.system_id), 41)
        self.assertTrue(self.node.system_id.startswith('node-'))

    def test_add_mac_address(self):
        self.node.add_mac_address('AA:BB:CC:DD:EE:FF')
        macs = MACAddress.objects.filter(
            node=self.node, mac_address='AA:BB:CC:DD:EE:FF').count()
        self.assertEqual(1, macs)

    def test_remove_mac_address(self):
        self.node.add_mac_address('AA:BB:CC:DD:EE:FF')
        self.node.remove_mac_address('AA:BB:CC:DD:EE:FF')
        macs = MACAddress.objects.filter(
            node=self.node, mac_address='AA:BB:CC:DD:EE:FF').count()
        self.assertEqual(0, macs)


class MACAddressTest(TestCase):

    def make_MAC(self, address):
        """Create a MAC address."""
        node = Node()
        node.save()
        return MACAddress(mac_address=address, node=node)

    def test_stores_to_database(self):
        mac = self.make_MAC('00:11:22:33:44:55')
        mac.save()
        self.assertEqual([mac], list(MACAddress.objects.all()))

    def test_invalid_address_raises_validation_error(self):
        mac = self.make_MAC('AA:BB:CCXDD:EE:FF')
        self.assertRaises(ValidationError, mac.full_clean)
