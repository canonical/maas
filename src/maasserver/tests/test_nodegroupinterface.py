# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :class:`NodeGroupInterface`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from django.core.exceptions import ValidationError
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    NODEGROUPINTERFACE_MANAGEMENT_CHOICES_DICT,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from netaddr import IPNetwork


def make_interface():
    nodegroup = factory.make_node_group(
        status=NODEGROUP_STATUS.ACCEPTED,
        management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
    return nodegroup.get_managed_interface()


class TestNodeGroupInterface(TestCase):

    def test_network_is_defined_when_broadcast_and_mask_are(self):
        interface = make_interface()
        self.assertIsInstance(interface.network, IPNetwork)

    def test_network_is_undefined_when_broadcast_is_None(self):
        interface = make_interface()
        interface.broadcast_ip = None
        self.assertIsNone(interface.network)

    def test_network_is_undefined_when_broadcast_is_empty(self):
        interface = make_interface()
        interface.broadcast_ip = ""
        self.assertIsNone(interface.network)

    def test_network_is_undefined_when_subnet_mask_is_None(self):
        interface = make_interface()
        interface.subnet_mask = None
        self.assertIsNone(interface.network)

    def test_network_is_undefined_subnet_mask_is_empty(self):
        interface = make_interface()
        interface.subnet_mask = ""
        self.assertIsNone(interface.network)

    def test_display_management_display_management(self):
        interface = make_interface()
        self.assertEqual(
            NODEGROUPINTERFACE_MANAGEMENT_CHOICES_DICT[interface.management],
            interface.display_management())

    def test_clean_ips_in_network_validates_IP(self):
        network = IPNetwork('192.168.0.3/24')
        checked_fields = [
            'ip',
            'router_ip',
            'ip_range_low',
            'ip_range_high',
            ]
        for field in checked_fields:
            nodegroup = factory.make_node_group(network=network)
            interface = nodegroup.get_managed_interface()
            ip = '192.168.2.1'
            setattr(interface, field, '192.168.2.1')
            message = (
                "%s not in the %s network" % (ip, '192.168.0.255/24'))
            exception = self.assertRaises(
                ValidationError, interface.full_clean)
            self.assertEqual(
                {field: [message]}, exception.message_dict)

    def test_clean_broadcast_ip(self):
        nodegroup = factory.make_node_group()
        interface = nodegroup.get_managed_interface()
        interface.broadcast_ip = ''
        message = (
            "'Broadcast ip' can't be empty if 'Subnet mask' is defined")
        exception = self.assertRaises(ValidationError, interface.full_clean)
        self.assertEqual(
            {'broadcast_ip': [message]}, exception.message_dict)

    def test_clean_subnet_mask(self):
        nodegroup = factory.make_node_group()
        interface = nodegroup.get_managed_interface()
        interface.subnet_mask = ''
        message = (
            "'Subnet mask' can't be empty if 'Broadcast ip' is defined")
        exception = self.assertRaises(ValidationError, interface.full_clean)
        self.assertEqual(
            {'subnet_mask': [message]}, exception.message_dict)

    def test_clean_network(self):
        nodegroup = factory.make_node_group(
            network=IPNetwork('192.168.0.3/24'))
        interface = nodegroup.get_managed_interface()
        # Set a bogus subnet mask.
        interface.subnet_mask = '0.9.0.4'
        message = 'invalid IPNetwork 192.168.0.255/0.9.0.4'
        exception = self.assertRaises(ValidationError, interface.full_clean)
        self.assertEqual(
            {
                'subnet_mask': [message],
                'broadcast_ip': [message],
            },
            exception.message_dict)

    def test_clean_network_config_if_managed(self):
        network = IPNetwork('192.168.0.3/24')
        checked_fields = [
            'interface',
            # When broadcast_ip or subnet_mask are empty, it gets caught
            # by clean_network.
            #'broadcast_ip',
            #'subnet_mask',
            'router_ip',
            'ip_range_low',
            'ip_range_high',
            ]
        for field in checked_fields:
            nodegroup = factory.make_node_group(
                network=network,
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
            interface = nodegroup.get_managed_interface()
            setattr(interface, field, '')
            exception = self.assertRaises(
                ValidationError, interface.full_clean)
            message = (
                "That field cannot be empty (unless that interface is "
                "'unmanaged')")
            self.assertEqual({field: [message]}, exception.message_dict)
