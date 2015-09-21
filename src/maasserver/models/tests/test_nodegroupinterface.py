# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
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
from provisioningserver.utils.network import (
    inet_ntop,
    MAASIPSet,
    make_iprange,
)
from testtools.matchers import (
    Contains,
    Equals,
    HasLength,
    Not,
)


def make_interface(network=None):
    nodegroup = factory.make_NodeGroup(
        status=NODEGROUP_STATUS.ENABLED,
        management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
        network=network)
    [interface] = nodegroup.get_managed_interfaces()
    return interface


def find_by_network_for_static_allocation(network):
    network = IPNetwork(network)
    return list(
        NodeGroupInterface.objects
        .find_by_network_for_static_allocation(network))


def get_by_network_for_static_allocation(network):
    network = IPNetwork(network)
    return (
        NodeGroupInterface.objects
        .get_by_network_for_static_allocation(network))


class TestFindingByNetwork(MAASServerTestCase):
    """Tests for `find_by_network_for_static_allocation`, etc."""

    scenarios = (
        ("by_network_for_static_allocation",
         {"find": find_by_network_for_static_allocation,
          "get": get_by_network_for_static_allocation}),
    )

    def test__finds_matching_interface(self):
        interface = make_interface()
        self.assertSequenceEqual([interface], self.find(interface.network))
        self.assertEqual(interface, self.get(interface.network))

    def test__finds_all_matching_interfaces(self):
        network = factory.make_ipv4_network()
        interfaces = [make_interface(network=network) for _ in xrange(3)]
        self.assertSequenceEqual(interfaces, self.find(network))
        self.assertEqual(interfaces[0], self.get(network))

    def test__finds_only_matching_interfaces(self):
        network1 = factory.make_ipv4_network()
        network1_ifs = [make_interface(network=network1) for _ in xrange(3)]
        network2 = factory.make_ipv4_network(disjoint_from=[network1])
        network2_ifs = [make_interface(network=network2) for _ in xrange(3)]
        self.assertSequenceEqual(network1_ifs, self.find(network1))
        self.assertSequenceEqual(network2_ifs, self.find(network2))
        self.assertEqual(network1_ifs[0], self.get(network1))
        self.assertEqual(network2_ifs[0], self.get(network2))

    def test__does_not_find_non_matching_interface(self):
        interface = make_interface()
        network = factory.make_ipv4_network(disjoint_from=[interface.network])
        self.assertSequenceEqual([], self.find(network))
        self.assertIsNone(self.get(network))


def find_by_address(address):
    address = IPAddress(address)
    return list(
        NodeGroupInterface.objects
        .find_by_address(address))


def get_by_address(address):
    address = IPAddress(address)
    return (
        NodeGroupInterface.objects
        .get_by_address(address))


def find_by_address_for_static_allocation(address):
    address = IPAddress(address)
    return list(
        NodeGroupInterface.objects
        .find_by_address_for_static_allocation(address))


def get_by_address_for_static_allocation(address):
    address = IPAddress(address)
    return (
        NodeGroupInterface.objects
        .get_by_address_for_static_allocation(address))


class TestFindingByAddress(MAASServerTestCase):
    """Tests for `find_by_address`, etc."""

    scenarios = (
        ("by_address",
         {"find": find_by_address,
          "get": get_by_address}),
        ("by_address_for_static_allocation",
         {"find": find_by_address_for_static_allocation,
          "get": get_by_address_for_static_allocation}),
    )

    def test__finds_matching_interface(self):
        interface = make_interface()
        address = factory.pick_ip_in_network(interface.network)
        self.assertSequenceEqual([interface], self.find(address))
        self.assertEqual(interface, self.get(address))

    def test__finds_all_matching_interfaces(self):
        network = factory.make_ipv4_network()
        interfaces = [make_interface(network=network) for _ in xrange(3)]
        address = factory.pick_ip_in_network(network)
        self.assertSequenceEqual(interfaces, self.find(address))
        self.assertEqual(interfaces[0], self.get(address))

    def test__finds_only_matching_interfaces(self):
        network1 = factory.make_ipv4_network()
        network1_addr = factory.pick_ip_in_network(network1)
        network1_ifs = [make_interface(network=network1) for _ in xrange(3)]
        network2 = factory.make_ipv4_network(disjoint_from=[network1])
        network2_addr = factory.pick_ip_in_network(network2)
        network2_ifs = [make_interface(network=network2) for _ in xrange(3)]
        self.assertSequenceEqual(network1_ifs, self.find(network1_addr))
        self.assertSequenceEqual(network2_ifs, self.find(network2_addr))
        self.assertEqual(network1_ifs[0], self.get(network1_addr))
        self.assertEqual(network2_ifs[0], self.get(network2_addr))

    def test__does_not_find_non_matching_interface(self):
        interface = make_interface()
        network = factory.make_ipv4_network(disjoint_from=[interface.network])
        address = factory.pick_ip_in_network(network)
        self.assertSequenceEqual([], self.find(address))
        self.assertIsNone(self.get(address))


class TestFindingByAddressForStaticAllocation(MAASServerTestCase):
    """Tests for `{find,get}_by_address_for_static_allocation` specifically."""

    def test__finds_only_interfaces_with_static_range(self):
        network = factory.make_ipv4_network()
        address = factory.pick_ip_in_network(network)
        interfaces = [make_interface(network) for _ in xrange(4)]

        if1, if2, if3, if4 = interfaces
        # if1 is left alone.
        self.assertIsNotNone(if1.static_ip_range_low)
        self.assertIsNotNone(if1.static_ip_range_high)
        # if2 doesn't have a lower bound on its static network range.
        if2.static_ip_range_low = None
        if2.save()
        # if3 doesn't have an upper bound on its static network range.
        if3.static_ip_range_high = None
        if3.save()
        # if3 doesn't have any bounds on its static network range.
        if4.static_ip_range_low = None
        if4.static_ip_range_high = None
        if4.save()

        # find_by_address_for_static_allocation() matches only if1.
        self.assertSequenceEqual(
            [if1], find_by_address_for_static_allocation(address))
        # find_by_address() matches them all.
        self.assertSequenceEqual(
            interfaces, find_by_address(address))

        # get_by_address_for_static_allocation() returns if1.
        self.assertEqual(if1, get_by_address_for_static_allocation(address))
        # get_by_address() returns if1 too.
        self.assertEqual(if1, get_by_address(address))

        if1.delete()
        # Delete if1 and get_by_address_for_static_allocation() returns None.
        self.assertIs(None, get_by_address_for_static_allocation(address))
        # get_by_address() returns *if2* now.
        self.assertEqual(if2, get_by_address(address))


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
        cluster = factory.make_NodeGroup()
        self.assertEqual(
            'eth0',
            factory.make_NodeGroupInterface(cluster, name='eth0').name)

    def test_name_accepts_network_interface_name_with_alias(self):
        cluster = factory.make_NodeGroup()
        self.assertEqual(
            'eth0:1',
            factory.make_NodeGroupInterface(cluster, name='eth0:1').name)

    def test_name_accepts_vlan_interface(self):
        cluster = factory.make_NodeGroup()
        self.assertEqual(
            'eth0.1',
            factory.make_NodeGroupInterface(cluster, name='eth0.1').name)

    def test_name_accepts_dashes(self):
        cluster = factory.make_NodeGroup()
        self.assertEqual(
            'eth0-1',
            factory.make_NodeGroupInterface(cluster, name='eth0-1').name)

    def test_name_rejects_other_unusual_characters(self):
        cluster = factory.make_NodeGroup()
        self.assertRaises(
            ValidationError,
            factory.make_NodeGroupInterface, cluster, name='eth 0')

    def test_clean_network_config_if_managed_accepts_empty_static_range(self):
        network = IPNetwork('192.168.0.3/24')
        checked_fields = [
            'static_ip_range_low',
            'static_ip_range_high',
            ]
        for field in checked_fields:
            nodegroup = factory.make_NodeGroup(
                network=network,
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
            [interface] = nodegroup.get_managed_interfaces()
            setattr(interface, field, '')
            # This doesn't raise a validation error.
            interface.full_clean()
            self.assertEqual('', getattr(interface, field))

    def test_clean_network_config_if_managed_accepts_empty_router_ip(self):
        network = IPNetwork('192.168.0.3/24')
        nodegroup = factory.make_NodeGroup(
            network=network,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        [interface] = nodegroup.get_managed_interfaces()
        setattr(interface.subnet, 'gateway_ip', '')
        # This doesn't raise a validation error.
        interface.full_clean()
        self.assertEqual('', getattr(interface.subnet, 'gateway_ip'))

    def test_clean_network_config_sets_default_if_netmask_not_given(self):
        network = factory.make_ipv4_network()
        nodegroup = factory.make_NodeGroup(
            network=network,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        [interface] = nodegroup.get_managed_interfaces()
        interface.full_clean()
        self.assertEqual(unicode(network.broadcast), interface.broadcast_ip)

    def test_clean_network_config_sets_no_broadcast_without_netmask(self):
        network = factory.make_ipv4_network()
        nodegroup = factory.make_NodeGroup(
            network=network,
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        interface = NodeGroupInterface.objects.get(nodegroup=nodegroup)
        interface.subnet_mask = None
        interface.broadcast_ip = None
        interface.full_clean()
        self.assertEqual(interface.broadcast_ip, '')

    def test_default_broadcast_ip_saves_cleanly(self):
        # When the default value for broadcast_ip was introduced, it broke
        # the form but not tests.  The reason: the default was an IPAddress,
        # but GenericIPAddressValidation expects a string.
        nodegroup = factory.make_NodeGroup()
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

    def test_clean_overlapping_networks_rejects_overlaps(self):
        network_1 = IPNetwork("10.1.0.0/16")
        interface_1 = make_interface(network_1)
        interface_1.save()

        network_2 = IPNetwork("10.1.0.0/24")
        interface_2 = NodeGroupInterface(
            nodegroup=interface_1.nodegroup,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            ip=IPAddress(network_2.first).format(),
            subnet_mask=network_2.netmask.format(),
            interface=factory.make_name(), router_ip="10.1.0.1",
            ip_range_low="10.1.0.2", ip_range_high="10.1.0.3")
        exception = self.assertRaises(ValidationError, interface_2.full_clean)
        message = (
            "This interface's network must not overlap with other "
            "networks on this cluster.")
        # Is it really OK that we're testing subnet_mask here, which is a
        # "virtual" field in this model class? (should this test be moved
        # to the form?)
        errors = {
            'ip': [message],
            'subnet_mask': [message],
        }
        self.assertEqual(errors, exception.message_dict)

    def test_clean_overlapping_networks_ignores_unmanaged_interface(self):
        network_1 = IPNetwork("10.1.0.0/16")
        interface_1 = make_interface(network_1)
        interface_1.save()

        interface_2 = NodeGroupInterface(
            nodegroup=interface_1.nodegroup,
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED,
            ip="10.1.0.1")
        interface_2.save()
        self.assertEqual(
            NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED,
            interface_2.management)

    def test_clean_overlapping_networks_ignores_other_unmanaged_iface(self):
        nodegroup = factory.make_NodeGroup()
        interface_1 = NodeGroupInterface(
            nodegroup=nodegroup,
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED,
            ip="10.1.0.1", subnet_mask="255.255.255.0")
        interface_1.save()

        interface_2 = NodeGroupInterface(
            nodegroup=nodegroup,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            ip="10.1.0.1", subnet_mask="255.255.255.0",
            ip_range_high="10.1.0.255", ip_range_low="10.1.0.2",
            router_ip="10.1.0.1", interface=factory.make_name("eth"),
            name=factory.make_name("interface"))
        interface_2.save()
        self.assertEqual(
            NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            interface_2.management)

    def test_clean_overlapping_networks_ignores_other_clusters(self):
        network_1 = IPNetwork("10.1.0.0/16")
        interface_1 = make_interface(network_1)
        interface_1.save()

        network_2 = IPNetwork("10.1.0.0/24")
        interface_2 = make_interface(network_2)
        interface_2.save()

        self.assertThat(
            interface_2.nodegroup, Not(Equals(interface_1.nodegroup)))
        self.assertEqual(network_2, interface_2.network)

    def test_manages_static_range_returns_False_if_not_managed(self):
        cluster = factory.make_NodeGroup()
        network = IPNetwork("10.9.9.0/24")
        interface = factory.make_NodeGroupInterface(
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
        cluster = factory.make_NodeGroup()
        network = IPNetwork("10.9.9.0/24")
        interface = factory.make_NodeGroupInterface(
            cluster, network=network,
            ip_range_low='10.9.9.10', ip_range_high='10.9.9.50',
            static_ip_range_low='10.9.9.100',
            static_ip_range_high='10.9.9.200',
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        self.assertTrue(interface.manages_static_range())

    @staticmethod
    def make_managed_interface():
        return factory.make_NodeGroupInterface(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            nodegroup=factory.make_NodeGroup())

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

    def test_validation_accepts_IPv4_and_IPv6_on_same_net_interface(self):
        cluster = factory.make_NodeGroup()
        net_interface = factory.make_name('eth')
        factory.make_NodeGroupInterface(
            cluster, interface=net_interface,
            network=factory.make_ipv4_network())
        factory.make_NodeGroupInterface(
            cluster, interface=net_interface,
            network=factory.make_ipv6_network())
        self.assertThat(cluster.nodegroupinterface_set.all(), HasLength(2))

    def test_validation_accepts_two_IPv4_on_different_net_interfaces(self):
        cluster = factory.make_NodeGroup()
        factory.make_NodeGroupInterface(
            cluster, interface=factory.make_name('eth1'),
            network=factory.make_ipv4_network())
        factory.make_NodeGroupInterface(
            cluster, interface=factory.make_name('eth2'),
            network=factory.make_ipv6_network())
        self.assertThat(cluster.nodegroupinterface_set.all(), HasLength(2))

    def test_validation_accepts_two_IPv4_on_different_clusters(self):
        net_interface = factory.make_name('eth')
        factory.make_NodeGroupInterface(
            factory.make_NodeGroup(), interface=net_interface,
            network=factory.make_ipv4_network())
        factory.make_NodeGroupInterface(
            factory.make_NodeGroup(), interface=net_interface,
            network=factory.make_ipv4_network())
        self.assertThat(
            NodeGroupInterface.objects.filter(interface=net_interface),
            HasLength(2))

    def test_validation_rejects_two_IPv4_interfaces_on_net_interface(self):
        cluster = factory.make_NodeGroup()
        net_interface = factory.make_name('eth')
        factory.make_NodeGroupInterface(
            cluster, interface=net_interface,
            network=factory.make_ipv4_network())
        network = factory.make_ipv4_network()
        extra_interface = NodeGroupInterface(
            nodegroup=cluster, interface=net_interface,
            ip=factory.pick_ip_in_network(network))

        error = self.assertRaises(ValidationError, extra_interface.save)
        self.assertEqual(
            [
                "Another cluster interface already connects "
                "network interface %s to an IPv4 network."
                % net_interface
            ],
            error.messages)

    def test_validation_accepts_two_IPv6_interfaces_on_net_interface(self):
        cluster = factory.make_NodeGroup()
        net_interface = factory.make_name('eth')
        factory.make_NodeGroupInterface(
            cluster, interface=net_interface,
            network=factory.make_ipv6_network())
        network = factory.make_ipv6_network()
        extra_interface = NodeGroupInterface(
            nodegroup=cluster, interface=net_interface,
            ip=factory.pick_ip_in_network(network))
        extra_interface.save()
        self.assertThat(cluster.nodegroupinterface_set.all(), HasLength(2))

    def test_validation_rejects_two_IPv6_static_ranges_on_net_interface(self):
        cluster = factory.make_NodeGroup()
        net_interface = factory.make_name('eth')
        factory.make_NodeGroupInterface(
            cluster, interface=net_interface,
            network=factory.make_ipv6_network(slash=64))
        network = factory.make_ipv6_network(slash=64)
        static_low = unicode(IPAddress(network.first + 1))
        static_high = unicode(IPAddress(network.last - 1))
        extra_interface = NodeGroupInterface(
            nodegroup=cluster, interface=net_interface,
            ip=factory.pick_ip_in_network(network),
            static_ip_range_low=static_low,
            static_ip_range_high=static_high)

        error = self.assertRaises(ValidationError, extra_interface.save)
        self.assertEqual(
            [
                "Another cluster interface with a static address range "
                "already connects network interface %s to an IPv6 network."
                % net_interface
            ],
            error.messages)

    def test_validation_knows_update_from_new_interface(self):
        cluster = factory.make_NodeGroup()
        network = factory.make_ipv4_network()
        interface = factory.make_NodeGroupInterface(cluster, network=network)
        interface.ip = factory.pick_ip_in_network(network)
        interface.save()
        self.assertEqual(interface, reload_object(interface))


class TestNodeGroupInterfaceGetIPRangesInUse(MAASServerTestCase):

    def test__returns_cluster_ip(self):
        ng = factory.make_NodeGroup()
        ngi = factory.make_NodeGroupInterface(ng)
        ranges = MAASIPSet(ngi.get_ipranges_in_use_on_ipnetwork(
            ngi.subnet.get_ipnetwork()))
        expected_range = make_iprange(ngi.ip)
        self.assertThat(ranges, Contains(expected_range))
        self.assertThat(
            ranges[expected_range].purpose, Contains("cluster-ip"))

    def test__returns_static_range(self):
        ng = factory.make_NodeGroup()
        ngi = factory.make_NodeGroupInterface(ng)
        ranges = ngi.get_ipranges_in_use_on_ipnetwork(
            ngi.subnet.get_ipnetwork())
        self.assertThat(ranges, Contains(make_iprange(ngi.ip)))

    def test__finds_used_ranges(self):
        ng = factory.make_NodeGroup()
        subnet = factory.make_Subnet(
            gateway_ip='', dns_servers=[], host_bits=8)
        net = subnet.get_ipnetwork()
        free_ip_1 = inet_ntop(net.first + 1)
        cluster_ip = inet_ntop(net.first + 2)
        free_ip_2 = inet_ntop(net.first + 3)
        free_ip_3 = inet_ntop(net.first + 9)
        dynamic_range_low = inet_ntop(net.first + 10)
        dynamic_range_high = inet_ntop(net.first + 49)
        static_range_low = inet_ntop(net.first + 50)
        static_range_high = inet_ntop(net.first + 99)
        free_ip_4 = inet_ntop(net.first + 100)
        ngi = factory.make_NodeGroupInterface(
            ng, subnet=subnet, ip=cluster_ip,
            ip_range_low=dynamic_range_low,
            ip_range_high=dynamic_range_high,
            static_ip_range_low=static_range_low,
            static_ip_range_high=static_range_high)
        s = MAASIPSet(ngi.get_ipranges_in_use_on_ipnetwork(net))
        self.assertThat(s, Contains(cluster_ip))
        self.assertThat(s, Contains(dynamic_range_low))
        self.assertThat(s, Contains(dynamic_range_high))
        self.assertThat(s, Contains(static_range_low))
        self.assertThat(s, Contains(static_range_high))
        self.assertThat(s, Not(Contains(free_ip_1)))
        self.assertThat(s, Not(Contains(free_ip_2)))
        self.assertThat(s, Not(Contains(free_ip_3)))
        self.assertThat(s, Not(Contains(free_ip_4)))
        self.assertThat(s[cluster_ip].purpose, Contains('cluster-ip'))
        self.assertThat(s[static_range_low].purpose, Contains('static-range'))
        self.assertThat(
            s[dynamic_range_low].purpose, Contains('dynamic-range'))

    def test__finds_used_ranges_excludes_static_ranges_if_requested(self):
        ng = factory.make_NodeGroup()
        subnet = factory.make_Subnet(
            gateway_ip='', dns_servers=[], host_bits=8)
        net = subnet.get_ipnetwork()
        free_ip_1 = inet_ntop(net.first + 1)
        cluster_ip = inet_ntop(net.first + 2)
        free_ip_2 = inet_ntop(net.first + 3)
        free_ip_3 = inet_ntop(net.first + 9)
        dynamic_range_low = inet_ntop(net.first + 10)
        dynamic_range_high = inet_ntop(net.first + 49)
        static_range_low = inet_ntop(net.first + 50)
        static_range_high = inet_ntop(net.first + 99)
        free_ip_4 = inet_ntop(net.first + 100)
        ngi = factory.make_NodeGroupInterface(
            ng, subnet=subnet, ip=cluster_ip,
            ip_range_low=dynamic_range_low,
            ip_range_high=dynamic_range_high,
            static_ip_range_low=static_range_low,
            static_ip_range_high=static_range_high)
        s = MAASIPSet(ngi.get_ipranges_in_use_on_ipnetwork(
            net, include_static_range=False))
        self.assertThat(s, Contains(cluster_ip))
        self.assertThat(s, Contains(dynamic_range_low))
        self.assertThat(s, Contains(dynamic_range_high))
        self.assertThat(s, Not(Contains(static_range_low)))
        self.assertThat(s, Not(Contains(static_range_high)))
        self.assertThat(s, Not(Contains(free_ip_1)))
        self.assertThat(s, Not(Contains(free_ip_2)))
        self.assertThat(s, Not(Contains(free_ip_3)))
        self.assertThat(s, Not(Contains(free_ip_4)))
        self.assertThat(s[cluster_ip].purpose, Contains('cluster-ip'))
        self.assertThat(
            s[dynamic_range_low].purpose, Contains('dynamic-range'))

    def test__finds_used_ranges_excludes_outside_addresses(self):
        ng = factory.make_NodeGroup()
        subnet = factory.make_Subnet(
            gateway_ip='', dns_servers=['8.8.8.8'], cidr='10.0.0.0/8')
        net = subnet.get_ipnetwork()
        free_ip_1 = inet_ntop(net.first + 1)
        cluster_ip = inet_ntop(net.first + 2)
        free_ip_2 = inet_ntop(net.first + 3)
        free_ip_3 = inet_ntop(net.first + 9)
        dynamic_range_low = inet_ntop(net.first + 10)
        dynamic_range_high = inet_ntop(net.first + 49)
        static_range_low = inet_ntop(net.first + 50)
        static_range_high = inet_ntop(net.first + 99)
        free_ip_4 = inet_ntop(net.first + 100)
        ngi = factory.make_NodeGroupInterface(
            ng, subnet=subnet, ip=cluster_ip,
            ip_range_low=dynamic_range_low,
            ip_range_high=dynamic_range_high,
            static_ip_range_low=static_range_low,
            static_ip_range_high=static_range_high)
        s = MAASIPSet(ngi.get_ipranges_in_use_on_ipnetwork(
            net, include_static_range=False))
        self.assertThat(s, Contains(cluster_ip))
        self.assertThat(s, Contains(dynamic_range_low))
        self.assertThat(s, Contains(dynamic_range_high))
        self.assertThat(s, Not(Contains(static_range_low)))
        self.assertThat(s, Not(Contains(static_range_high)))
        self.assertThat(s, Not(Contains(free_ip_1)))
        self.assertThat(s, Not(Contains(free_ip_2)))
        self.assertThat(s, Not(Contains(free_ip_3)))
        self.assertThat(s, Not(Contains(free_ip_4)))
        self.assertThat(s[cluster_ip].purpose, Contains('cluster-ip'))
        self.assertThat(
            s[dynamic_range_low].purpose, Contains('dynamic-range'))


class TestNodeGroupInterfacePostSaveHandler(MAASServerTestCase):

    def test__saves_related_subnet_when_nodegroupinterface_updated(self):
        ng = factory.make_NodeGroup()
        ngi = factory.make_NodeGroupInterface(
            ng, ip='10.0.0.1', subnet_mask='255.255.255.0')
        subnet = reload_object(ngi.subnet)
        self.assertThat(
            unicode(subnet.get_ipnetwork().netmask), Equals('255.255.255.0'))
        ngi.subnet_mask = '255.255.0.0'
        ngi.save()
        subnet = reload_object(ngi.subnet)
        self.assertThat(
            unicode(subnet.get_ipnetwork().netmask), Equals('255.255.0.0'))
