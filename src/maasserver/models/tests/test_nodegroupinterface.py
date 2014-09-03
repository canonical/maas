# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :class:`NodeGroupInterface`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django.core.exceptions import ValidationError
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    NODEGROUPINTERFACE_MANAGEMENT_CHOICES_DICT,
    )
from maasserver.models import NodeGroupInterface
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from netaddr import (
    IPAddress,
    IPNetwork,
    )


def make_interface(network=None):
    nodegroup = factory.make_node_group(
        status=NODEGROUP_STATUS.ACCEPTED,
        management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
        network=network)
    [interface] = nodegroup.get_managed_interfaces()
    return interface


class TestNodeGroupInterface(MAASServerTestCase):

    def test_network(self):
        network = IPNetwork("10.0.0.3/24")
        interface = make_interface(network=network)
        self.assertEqual(IPNetwork("10.0.0.0/24"), interface.network)

    def test_network_is_defined_when_netmask_is(self):
        interface = make_interface()
        interface.ip = "10.0.0.9"
        interface.subnet_mask = "255.255.255.0"
        self.assertIsInstance(interface.network, IPNetwork)

    def test_network_does_not_require_broadcast_address(self):
        interface = make_interface()
        interface.broadcast_ip = None
        self.assertIsInstance(interface.network, IPNetwork)

    def test_network_does_not_require_nonempty_broadcast_address(self):
        interface = make_interface()
        interface.broadcast_ip = ""
        self.assertIsInstance(interface.network, IPNetwork)

    def test_network_is_undefined_when_subnet_mask_is_None(self):
        interface = make_interface()
        interface.subnet_mask = None
        self.assertIsNone(interface.network)

    def test_network_is_undefined_when_subnet_mask_is_empty(self):
        interface = make_interface()
        interface.subnet_mask = ""
        self.assertIsNone(interface.network)

    def test_display_management_display_management(self):
        interface = make_interface()
        self.assertEqual(
            NODEGROUPINTERFACE_MANAGEMENT_CHOICES_DICT[interface.management],
            interface.display_management())

    def test_name_accepts_network_interface_name(self):
        cluster = factory.make_node_group()
        self.assertEqual(
            'eth0',
            factory.make_node_group_interface(cluster, name='eth0').name)

    def test_name_accepts_network_interface_name_with_alias(self):
        cluster = factory.make_node_group()
        self.assertEqual(
            'eth0:1',
            factory.make_node_group_interface(cluster, name='eth0:1').name)

    def test_name_accepts_vlan_interface(self):
        cluster = factory.make_node_group()
        self.assertEqual(
            'eth0.1',
            factory.make_node_group_interface(cluster, name='eth0.1').name)

    def test_name_accepts_dashes(self):
        cluster = factory.make_node_group()
        self.assertEqual(
            'eth0-1',
            factory.make_node_group_interface(cluster, name='eth0-1').name)

    def test_name_rejects_other_unusual_characters(self):
        cluster = factory.make_node_group()
        self.assertRaises(
            ValidationError,
            factory.make_node_group_interface, cluster, name='eth 0')

    def test_clean_ips_in_network_validates_IP(self):
        network = IPNetwork('192.168.0.3/24')
        ip_outside_network = '192.168.2.1'
        checked_fields = [
            'broadcast_ip',
            'router_ip',
            'ip_range_low',
            'ip_range_high',
            'static_ip_range_low',
            'static_ip_range_high',
            ]
        for field in checked_fields:
            nodegroup = factory.make_node_group(
                network=network, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
            [interface] = nodegroup.get_managed_interfaces()
            setattr(interface, field, ip_outside_network)
            message = "%s not in the %s network" % (
                ip_outside_network,
                '192.168.0.0/24',
                )
            exception = self.assertRaises(
                ValidationError, interface.full_clean)
            self.assertEqual({field: [message]}, exception.message_dict)

    def test_clean_network(self):
        nodegroup = factory.make_node_group(
            network=IPNetwork('192.168.0.3/24'),
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        [interface] = nodegroup.get_managed_interfaces()
        # Set a bogus subnet mask.
        interface.subnet_mask = '0.9.0.4'
        message = "invalid IPNetwork %s/0.9.0.4" % interface.ip
        exception = self.assertRaises(ValidationError, interface.full_clean)
        self.assertEqual(
            {'subnet_mask': [message]},
            exception.message_dict)

    def test_clean_network_config_if_managed(self):
        network = IPNetwork('192.168.0.3/24')
        checked_fields = [
            'interface',
            'subnet_mask',
            'router_ip',
            'ip_range_low',
            'ip_range_high',
            ]
        for field in checked_fields:
            nodegroup = factory.make_node_group(
                network=network,
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
            [interface] = nodegroup.get_managed_interfaces()
            setattr(interface, field, '')
            exception = self.assertRaises(
                ValidationError, interface.full_clean)
            message = (
                "That field cannot be empty (unless that interface is "
                "'unmanaged')")
            self.assertEqual({field: [message]}, exception.message_dict)

    def test_clean_network_config_if_managed_accepts_empty_static_range(self):
        network = IPNetwork('192.168.0.3/24')
        checked_fields = [
            'static_ip_range_low',
            'static_ip_range_high',
            ]
        for field in checked_fields:
            nodegroup = factory.make_node_group(
                network=network,
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
            [interface] = nodegroup.get_managed_interfaces()
            setattr(interface, field, '')
            # This doesn't raise a validation error.
            interface.full_clean()

    def test_clean_network_config_sets_default_if_netmask_not_given(self):
        network = factory.getRandomNetwork()
        nodegroup = factory.make_node_group(
            network=network,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        [interface] = nodegroup.get_managed_interfaces()
        interface.full_clean()
        self.assertEqual(unicode(network.broadcast), interface.broadcast_ip)

    def test_clean_network_config_sets_no_broadcast_without_netmask(self):
        network = factory.getRandomNetwork()
        nodegroup = factory.make_node_group(
            network=network,
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        interface = NodeGroupInterface.objects.get(nodegroup=nodegroup)
        interface.subnet_mask = None
        interface.broadcast_ip = None
        interface.full_clean()
        self.assertIsNone(interface.broadcast_ip)

    def test_default_broadcast_ip_saves_cleanly(self):
        # When the default value for broadcast_ip was introduced, it broke
        # the form but not tests.  The reason: the default was an IPAddress,
        # but GenericIPAddressValidation expects a string.
        nodegroup = factory.make_node_group()
        # Can't use the factory for this one; it may hide the problem.
        interface = NodeGroupInterface(
            nodegroup=nodegroup, name=factory.make_name('ngi'),
            ip='10.1.1.1', router_ip='10.1.1.254',
            subnet_mask='255.255.255.0', ip_range_low='10.1.1.100',
            ip_range_high='10.1.1.200',
            static_ip_range_low='10.1.1.201',
            static_ip_range_high='10.1.1.253', interface='eth99',
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        interface.save()
        self.assertEqual(interface, reload_object(interface))

    def test_clean_ip_ranges_checks_for_overlapping_ranges(self):
        network = IPNetwork('10.1.1.0/24')
        interface = make_interface(network)
        interface.ip_range_low = '10.1.1.10'
        interface.ip_range_high = '10.1.1.20'
        interface.static_ip_range_low = '10.1.1.15'
        interface.static_ip_range_high = '10.1.1.25'
        exception = self.assertRaises(
            ValidationError, interface.full_clean)
        message = "Static and dynamic IP ranges may not overlap."
        errors = {
            'ip_range_low': [message],
            'ip_range_high': [message],
            'static_ip_range_low': [message],
            'static_ip_range_high': [message],
            }
        self.assertEqual(errors, exception.message_dict)

    def test_clean_ip_ranges_works_with_ipv6_ranges(self):
        network = factory.make_ipv6_network()
        interface = make_interface(network)
        interface.ip_range_low = unicode(
            IPAddress(network.first))
        interface.ip_range_high = unicode(
            IPAddress(network.last))
        interface.static_ip_range_low = unicode(
            IPAddress(network.first + 1))
        interface.static_ip_range_high = unicode(
            IPAddress(network.last - 1))
        exception = self.assertRaises(
            ValidationError, interface.full_clean)
        message = "Static and dynamic IP ranges may not overlap."
        errors = {
            'ip_range_low': [message],
            'ip_range_high': [message],
            'static_ip_range_low': [message],
            'static_ip_range_high': [message],
            }
        self.assertEqual(errors, exception.message_dict)

    def clean_ip_ranges_works_with_mixed_ranges(self):
        # No-one sane would ever declare this network, most likely, but
        # we should test for it because the world has insane people in
        # it.
        network = IPNetwork('::ffff:192.168.0.0/64')
        interface = make_interface(network)
        interface.ip_range_low = '::ffff:192.168.0.1'
        interface.ip_range_high = '::ffff:ffff:ffff:ffff:ffff'
        interface.static_ip_range_low = '192.168.0.100'
        interface.static_ip_range_high = '192.168.0.255'
        exception = self.assertRaises(
            ValidationError, interface.full_clean)
        message = "Static and dynamic IP ranges may not overlap."
        errors = {
            'ip_range_low': [message],
            'ip_range_high': [message],
            'static_ip_range_low': [message],
            'static_ip_range_high': [message],
            }
        self.assertEqual(errors, exception.message_dict)

    def test_clean_ip_range_bounds_checks_for_reversed_range_bounds(self):
        network = IPNetwork("10.1.0.0/16")
        interface = make_interface(network)
        interface.ip_range_low = '10.1.0.2'
        interface.ip_range_high = '10.1.0.1'
        interface.static_ip_range_low = '10.1.0.10'
        interface.static_ip_range_high = '10.1.0.9'
        exception = self.assertRaises(
            ValidationError, interface.full_clean)
        message = "Lower bound %s is higher than upper bound %s"
        errors = {
            'ip_range_low': [
                message % (interface.ip_range_low, interface.ip_range_high)],
            'ip_range_high': [
                message % (interface.ip_range_low, interface.ip_range_high)],
            'static_ip_range_low': [
                message % (
                    interface.static_ip_range_low,
                    interface.static_ip_range_high)],
            'static_ip_range_high': [
                message % (
                    interface.static_ip_range_low,
                    interface.static_ip_range_high)],
            }
        self.assertEqual(errors, exception.message_dict)

    def test_manages_static_range_returns_False_if_not_managed(self):
        cluster = factory.make_node_group()
        network = IPNetwork("10.9.9.0/24")
        interface = factory.make_node_group_interface(
            cluster, network=network,
            ip_range_low='10.9.9.10', ip_range_high='10.9.9.50',
            static_ip_range_low='10.9.9.100',
            static_ip_range_high='10.9.9.200',
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        self.assertFalse(interface.manages_static_range())

    def test_manages_static_range_returns_False_if_no_static_range(self):
        network = IPNetwork("10.9.9.0/24")
        interface = make_interface(network)
        interface.static_ip_range_low = None
        interface.static_ip_range_high = None
        self.assertFalse(interface.manages_static_range())

    def test_manages_static_range_returns_False_if_partial_static_range(self):
        network = IPNetwork("10.9.9.0/24")
        interface = make_interface(network)
        interface.static_ip_range_low = '10.99.99.100'
        interface.static_ip_range_high = None
        self.assertFalse(interface.manages_static_range())

    def test_manages_static_range_returns_True_if_manages_static_range(self):
        cluster = factory.make_node_group()
        network = IPNetwork("10.9.9.0/24")
        interface = factory.make_node_group_interface(
            cluster, network=network,
            ip_range_low='10.9.9.10', ip_range_high='10.9.9.50',
            static_ip_range_low='10.9.9.100',
            static_ip_range_high='10.9.9.200',
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        self.assertTrue(interface.manages_static_range())

    @staticmethod
    def make_managed_interface():
        return factory.make_node_group_interface(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            nodegroup=factory.make_node_group())

    def test_dynamic_ip_range_returns_None_if_range_low_not_set(self):
        interface = self.make_managed_interface()
        interface.ip_range_low = None
        self.assertIsNone(interface.get_dynamic_ip_range())

    def test_dynamic_ip_range_returns_None_if_range_high_not_set(self):
        interface = self.make_managed_interface()
        interface.ip_range_high = None
        self.assertIsNone(interface.get_dynamic_ip_range())

    def test_static_ip_range_returns_None_if_range__not_set(self):
        interface = self.make_managed_interface()
        interface.static_ip_range_low = None
        self.assertIsNone(interface.get_static_ip_range())

    def test_static_ip_range_returns_None_if_range_high_not_set(self):
        interface = self.make_managed_interface()
        interface.static_ip_range_high = None
        self.assertIsNone(interface.get_static_ip_range())

    def test_dynamic_ip_range_returns_IPRange_if_range_set(self):
        interface = self.make_managed_interface()
        ip_range = interface.get_dynamic_ip_range()
        self.assertIsNotNone(ip_range)
        self.assertEqual(
            IPAddress(ip_range.first).format(),
            interface.ip_range_low)
        self.assertEqual(
            IPAddress(ip_range.last).format(),
            interface.ip_range_high)

    def test_static_ip_range_returns_IPRange_if_range_set(self):
        interface = self.make_managed_interface()
        ip_range = interface.get_static_ip_range()
        self.assertIsNotNone(ip_range)
        self.assertEqual(
            IPAddress(ip_range.first).format(),
            interface.static_ip_range_low)
        self.assertEqual(
            IPAddress(ip_range.last).format(),
            interface.static_ip_range_high)
