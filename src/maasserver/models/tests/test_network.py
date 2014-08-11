# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :class:`Network`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from operator import attrgetter

from django.core.exceptions import ValidationError
from django.db.models.query import QuerySet
from maasserver.models import Network
from maasserver.models.network import (
    get_name_and_vlan_from_cluster_interface,
    get_specifier_type,
    IPSpecifier,
    NameSpecifier,
    parse_network_spec,
    VLANSpecifier,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from mock import sentinel
from netaddr import (
    IPAddress,
    IPNetwork,
    )
from provisioningserver.utils.network import make_network


class TestNameSpecifier(MAASServerTestCase):

    def test_accepts_network_name(self):
        name = factory.make_name('net')
        self.assertEqual(name, NameSpecifier(name).name)

    def test_rejects_invalid_name(self):
        self.assertRaises(ValidationError, NameSpecifier, '#.!')

    def test_fails_if_wrong_type(self):
        self.assertRaises(ValidationError, NameSpecifier, 'vlan:8')


class TestIPSpecifier(MAASServerTestCase):

    def test_accepts_IPv4_address(self):
        ip = factory.getRandomIPAddress()
        self.assertEqual(IPAddress(ip), IPSpecifier('ip:' + unicode(ip)).ip)

    def test_accepts_IPv6_address(self):
        ip = factory.make_ipv6_address()
        self.assertEqual(IPAddress(ip), IPSpecifier('ip:' + unicode(ip)).ip)

    def test_rejects_empty_ip_address(self):
        self.assertRaises(ValidationError, IPSpecifier, 'ip:')

    def test_rejects_malformed_ip_address(self):
        self.assertRaises(ValidationError, IPSpecifier, 'ip:abc')

    def test_fails_if_wrong_type(self):
        self.assertRaises(AssertionError, IPSpecifier, 'vlan:8')


class TestVLANSpecifier(MAASServerTestCase):

    def test_accepts_vlan_tag_in_range(self):
        self.assertEqual(12, VLANSpecifier('vlan:12').vlan_tag)
        self.assertEqual(1, VLANSpecifier('vlan:1').vlan_tag)
        self.assertEqual(4094, VLANSpecifier('vlan:4094').vlan_tag)

    def test_rejects_empty_vlan_tag(self):
        self.assertRaises(ValidationError, VLANSpecifier, 'vlan:')

    def test_rejects_nonnumerical_vlan_tag(self):
        self.assertRaises(ValidationError, VLANSpecifier, 'vlan:B')
        self.assertRaises(ValidationError, VLANSpecifier, 'vlan:0x1g')

    def test_accepts_hexadecimal_vlan_tag(self):
        self.assertEqual(0xf0f, VLANSpecifier('vlan:0xf0f').vlan_tag)
        self.assertEqual(0x1ac, VLANSpecifier('vlan:0x1AC').vlan_tag)

    def test_rejects_reserved_vlan_tags(self):
        self.assertRaises(ValidationError, VLANSpecifier, 'vlan:0')
        self.assertRaises(ValidationError, VLANSpecifier, 'vlan:4095')

    def test_rejects_vlan_tag_out_of_range(self):
        self.assertRaises(ValidationError, VLANSpecifier, 'vlan:-1')
        self.assertRaises(ValidationError, VLANSpecifier, 'vlan:4096')

    def test_fails_if_wrong_type(self):
        self.assertRaises(AssertionError, VLANSpecifier, 'ip:10.1.1.1')


class TestGetSpecifierType(MAASServerTestCase):
    """Tests for `get_specifier_type`."""

    def test_returns_type_identified_by_type_tag(self):
        self.assertEqual(IPSpecifier, get_specifier_type('ip:10.0.0.0'))
        self.assertEqual(VLANSpecifier, get_specifier_type('vlan:99'))

    def test_defaults_to_name_if_no_type_tag_found(self):
        self.assertEqual(NameSpecifier, get_specifier_type('hello'))

    def test_rejects_unsupported_tag(self):
        self.assertRaises(ValidationError, get_specifier_type, 'foo:bar')


class TestParseNetworkSpec(MAASServerTestCase):
    """Tests for `parse_network_spec`."""

    def test_rejects_unknown_type_tag(self):
        self.assertRaises(ValidationError, parse_network_spec, 'foo:bar')

    def test_accepts_valid_specifier(self):
        spec = parse_network_spec('ip:10.8.8.8')
        self.assertIsInstance(spec, IPSpecifier)
        self.assertEqual(IPAddress('10.8.8.8'), spec.ip)

    def test_rejects_untagged_ip_address(self):
        # If this becomes a stumbling block, it would be possible to accept
        # plain IP addresses as network specifiers.
        self.assertRaises(ValidationError, parse_network_spec, '10.4.4.4')


class TestGetNameAndVlanFromClusterInterface(MAASServerTestCase):
    """Tests for `get_name_and_vlan_from_cluster_interface`."""

    def make_interface_name(self, basename):
        interface = sentinel.interface
        interface.nodegroup = sentinel.nodegroup
        interface.nodegroup.name = factory.make_name('name')
        interface.interface = basename
        return interface

    def test_returns_simple_name_unaltered(self):
        interface = self.make_interface_name(factory.make_name('iface'))
        name, vlan_tag = get_name_and_vlan_from_cluster_interface(interface)
        expected_name = '%s-%s' % (
            interface.nodegroup.name, interface.interface)
        self.assertEqual((expected_name, None), (name, vlan_tag))

    def test_substitutes_colon(self):
        interface = self.make_interface_name('eth0:0')
        name, vlan_tag = get_name_and_vlan_from_cluster_interface(interface)
        expected_name = '%s-eth0-0' % interface.nodegroup.name
        self.assertEqual((expected_name, None), (name, vlan_tag))

    def test_returns_with_vlan_tag(self):
        interface = self.make_interface_name('eth0.5')
        name, vlan_tag = get_name_and_vlan_from_cluster_interface(interface)
        expected_name = '%s-eth0-5' % interface.nodegroup.name
        self.assertEqual((expected_name, '5'), (name, vlan_tag))

    def test_returns_name_with_crazy_colon_and_vlan(self):
        # For truly twisted network admins.
        interface = self.make_interface_name('eth0:2.3')
        name, vlan_tag = get_name_and_vlan_from_cluster_interface(interface)
        expected_name = '%s-eth0-2-3' % interface.nodegroup.name
        self.assertEqual((expected_name, '3'), (name, vlan_tag))


class TestNetworkManager(MAASServerTestCase):

    def test_get_from_spec_validates_first(self):
        self.assertRaises(ValidationError, Network.objects.get_from_spec, '??')

    def test_get_from_spec_finds_by_name(self):
        network = factory.make_network()
        self.assertEqual(network, Network.objects.get_from_spec(network.name))

    def test_get_from_spec_fails_on_unknown_name(self):
        self.assertRaises(
            Network.DoesNotExist,
            Network.objects.get_from_spec, factory.make_name('no'))

    def test_get_from_spec_finds_by_ip(self):
        network = factory.make_network()
        self.assertEqual(
            network,
            Network.objects.get_from_spec('ip:%s' % network.ip))

    def test_get_from_spec_finds_by_any_ip_in_range(self):
        network = factory.make_network(network=IPNetwork('10.99.99.0/24'))
        self.assertEqual(
            network,
            Network.objects.get_from_spec('ip:10.99.99.255'))

    def test_get_from_spec_fails_on_unknown_ip(self):
        factory.make_network(network=IPNetwork('10.99.99.0/24'))
        self.assertRaises(
            Network.DoesNotExist,
            Network.objects.get_from_spec, 'ip:10.99.100.1')

    def test_get_from_spec_finds_by_vlan_tag(self):
        vlan_tag = factory.make_vlan_tag()
        network = factory.make_network(vlan_tag=vlan_tag)
        self.assertEqual(
            network,
            Network.objects.get_from_spec('vlan:%s' % network.vlan_tag))

    def test_get_from_spec_fails_on_unknown_vlan(self):
        self.assertRaises(
            Network.DoesNotExist,
            Network.objects.get_from_spec, 'vlan:999')


class TestNetwork(MAASServerTestCase):

    def test_instantiation(self):
        name = factory.make_name('net')
        network = factory.getRandomNetwork()
        vlan_tag = factory.make_vlan_tag(allow_none=True)
        description = factory.make_string()

        network = factory.make_network(
            name=name, network=network, vlan_tag=vlan_tag,
            description=description)

        self.assertAttributes(
            network,
            {
                'name': name,
                'ip': network.ip,
                'netmask': network.netmask,
                'vlan_tag': vlan_tag,
                'description': description,
            })

    def test_clean_strips_non_network_bits_off_ip(self):
        network = factory.make_network()
        network.netmask = '255.255.0.0'
        network.ip = '10.9.8.7'
        network.save()
        self.assertEqual('10.9.0.0', network.ip)

    def test_vlan_tag_can_be_zero_through_hex_ffe(self):
        self.assertIsNone(factory.make_network(vlan_tag=0).vlan_tag)
        self.assertEqual(1, factory.make_network(vlan_tag=1).vlan_tag)
        max_tag = 0xfff - 1
        self.assertEqual(
            max_tag, factory.make_network(vlan_tag=max_tag).vlan_tag)

    def test_reserved_vlan_tag_does_not_validate(self):
        error = self.assertRaises(
            ValidationError, factory.make_network, vlan_tag=0xFFF)
        self.assertEqual(
            error.message_dict,
            {'vlan_tag': ["Cannot use reserved value 0xFFF."]})

    def test_out_of_range_vlan_tags_do_not_validate(self):
        out_of_range_msg = (
            "Value must be between 0x000 and 0xFFF (12 bits)")
        error = self.assertRaises(
            ValidationError, factory.make_network, vlan_tag=0x1000)
        self.assertEqual(
            error.message_dict, {'vlan_tag': [out_of_range_msg]})

        error = self.assertRaises(
            ValidationError, factory.make_network, vlan_tag=-1)
        self.assertEqual(
            error.message_dict, {'vlan_tag': [out_of_range_msg]})

    def test_vlan_tag_normalises_zero_to_None(self):
        self.assertIsNone(factory.make_network(vlan_tag=0).vlan_tag)

    def test_nonzero_vlan_tag_is_unique(self):
        tag = factory.make_vlan_tag(allow_none=False)
        factory.make_network(vlan_tag=tag)
        error = self.assertRaises(
            ValidationError, factory.make_network, vlan_tag=tag)
        self.assertEqual(
            error.message_dict,
            {'vlan_tag': ['Network with this Vlan tag already exists.']})

    def test_zero_vlan_tag_is_not_unique(self):
        networks = factory.make_networks(3, with_vlans=False)
        self.assertEqual(
            sorted(networks, key=attrgetter('id')),
            list(Network.objects.filter(vlan_tag=None).order_by('id')))

    def test_get_network_returns_network(self):
        net = factory.getRandomNetwork()
        self.assertEqual(net, factory.make_network(network=net).get_network())

    def test_accepts_ipv6_network(self):
        net = factory.make_ipv6_network()
        self.assertEqual(net, factory.make_network(network=net).get_network())

    def test_get_connected_nodes_returns_QuerySet(self):
        network = factory.make_network()
        self.assertIsInstance(network.get_connected_nodes(), QuerySet)

    def test_get_connected_nodes_returns_connected_nodes(self):
        network = factory.make_network()
        macs = [factory.make_mac_address(networks=[network]) for _ in range(4)]
        nodes = [mac.node for mac in macs]
        # Create a handful of MAC addresses not connected to the network.
        [factory.make_mac_address() for _ in range(3)]
        self.assertItemsEqual(nodes, network.get_connected_nodes())

    def test_get_connected_nodes_doesnt_count_multiple_connections_twice(self):
        network = factory.make_network()
        node1 = factory.make_node()
        node2 = factory.make_node()
        [factory.make_mac_address(
            node=node1, networks=[network]) for _ in range(3)]
        [factory.make_mac_address(
            node=node2, networks=[network]) for _ in range(3)]
        self.assertItemsEqual([node1, node2], network.get_connected_nodes())

    def test_name_validation_allows_identifier_characters(self):
        name = 'x_9-y'
        self.assertEqual(name, factory.make_network(name=name).name)

    def test_name_validation_disallows_special_characters(self):
        self.assertRaises(ValidationError, factory.make_network, name='a/b')
        self.assertRaises(ValidationError, factory.make_network, name='a@b')
        self.assertRaises(ValidationError, factory.make_network, name='a?b')
        self.assertRaises(ValidationError, factory.make_network, name='a\\b')
        self.assertRaises(ValidationError, factory.make_network, name='a@b')

    def test_netmask_validation_accepts_netmask(self):
        netmask = '255.255.255.128'
        network = make_network(factory.getRandomIPAddress(), netmask)
        self.assertEqual(
            unicode(network.netmask),
            factory.make_network(network=network).netmask)

    def test_netmask_validation_does_not_allow_extreme_cases(self):
        ip = factory.getRandomIPAddress()
        self.assertRaises(
            ValidationError, factory.make_network,
            network=make_network(ip, '255.255.255.255'))
        self.assertRaises(
            ValidationError, factory.make_network,
            network=make_network(ip, '0.0.0.0'))

    def test_netmask_validation_does_not_allow_too_small_ipv6_netmask(self):
        ip = factory.make_ipv6_address()
        self.assertRaises(
            ValidationError, factory.make_network,
            network=make_network(
                ip, 'ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff'))

    def test_netmask_validation_does_not_allow_too_large_ipv6_netmask(self):
        ip = factory.make_ipv6_address()
        self.assertRaises(
            ValidationError, factory.make_network,
            network=make_network(
                ip, '0000:0000:0000:0000:0000:0000:0000:0000'))

    def test_netmask_valid_doesnt_allow_short_allow_all_ipv6_netmask(self):
        ip = factory.make_ipv6_address()
        self.assertRaises(
            ValidationError, factory.make_network,
            network=make_network(ip, '::'))

    def test_netmask_validation_does_not_allow_mixed_zeroes_and_ones(self):
        # The factory won't let us create a Network with a nonsensical netmask,
        # so to test this by updating an existing Network object.
        network = factory.make_network()
        network.netmask = '255.254.255.0'
        self.assertRaises(ValidationError, network.save)

    def test_netmask_validation_accepts_ipv6_netmask(self):
        net = factory.make_ipv6_network()
        network = factory.make_network(network=net)
        network.netmask = "ffff:ffff:ffff:ffff:ffff:ffff:ffff:0000"
        # This shouldn't error.
        network.save()

    def test_netmask_validation_errors_on_mixed_v4_and_v6_values(self):
        network = factory.make_network()
        network.ip = unicode(factory.make_ipv6_address())
        network.netmask = '255.255.255.0'
        self.assertRaises(ValidationError, network.save)

    def test_unicode_returns_cidr_if_tag_is_zero(self):
        cidr = '10.9.0.0/16'
        network = factory.make_network(network=IPNetwork(cidr))
        # Set vlan_tag to zero here.  If we do it while creating the Network
        # object, it would be normalised to None.
        network.vlan_tag = 0
        self.assertEqual("%s:%s" % (network.name, cidr), unicode(network))

    def test_unicode_returns_cidr_if_tag_is_None(self):
        cidr = '10.9.0.0/16'
        network = factory.make_network(network=IPNetwork(cidr), vlan_tag=None)
        self.assertEqual("%s:%s" % (network.name, cidr), unicode(network))

    def test_unicode_includes_tag_if_set(self):
        cidr = '10.9.0.0/16'
        network = factory.make_network(network=IPNetwork(cidr), vlan_tag=0xabc)
        self.assertEqual(
            "%s:%s(tag:abc)" % (network.name, cidr), unicode(network))

    def test_unicode_treats_unclean_zero_tag_as_unset(self):
        net = IPNetwork('10.1.1.0/24')
        network = factory.make_network(network=net)
        network.vlan_tag = None
        proper_unicode = unicode(network)
        network.vlan_tag = 0
        unclean_unicode = unicode(network)
        self.assertEqual(proper_unicode, unclean_unicode)

    def test_disallows_identical_networks_with_same_netmask(self):
        existing_network = factory.make_network()
        self.assertRaises(
            ValidationError, factory.make_network,
            network=existing_network.get_network())

    def test_unique_network_validation_check_doesnt_use_name(self):
        # The check for network uniqueness skips the network being
        # validated even if its name has been changed.
        network = factory.make_network()
        network.name = factory.make_name('new-network-name')
        self.assertIsNone(network.save())
        # The check is that network.save() doesn't raise.

    def test_disallows_identical_networks_with_different_netmasks(self):
        factory.make_network(network=IPNetwork('10.0.0.0/16'))
        self.assertRaises(
            ValidationError, factory.make_network,
            network=IPNetwork('10.0.0.0/8'))
        self.assertRaises(
            ValidationError, factory.make_network,
            network=IPNetwork('10.0.0.0/24'))

    def test_disallows_same_network_specified_using_different_addresses(self):
        factory.make_network(network=IPNetwork('10.1.2.3/16'))
        self.assertRaises(
            ValidationError, factory.make_network,
            network=IPNetwork('10.1.0.0/16'))

    def test_disallows_nested_networks_with_different_base_addresses(self):
        factory.make_network(network=IPNetwork('10.0.0.0/16'))
        self.assertRaises(
            ValidationError, factory.make_network,
            network=IPNetwork('10.0.1.0/24'))
