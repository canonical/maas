"""
Test maasserver models.
"""

from django.test import TestCase
from maasserver.models import Node, MACAddress
from django.core.exceptions import ValidationError


class NodeTest(TestCase):

    def test_system_id(self):
        node = Node()
        self.assertEqual(len(node.system_id), 41)
        self.assertTrue(node.system_id.startswith('node-'))


class MACAddressTest(TestCase):

    def test_mac_address_invalid(self):
        node = Node()
        node.save()
        mac = MACAddress(mac_address='AA:BB:CCXDD:EE:FF', node=node)
        self.assertRaises(ValidationError, mac.full_clean)

    def test_mac_address_valid(self):
        node = Node()
        node.save()
        mac = MACAddress(mac_address='AA:BB:CC:DD:EE:FF', node=node)
        mac.full_clean()  # No exception.
