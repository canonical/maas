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
from random import randint

from django.core.exceptions import ValidationError
from maasserver.models import Network
from maasserver.models.network import parse_network_spec
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from netaddr import (
    IPAddress,
    IPNetwork,
    )


class TestParseNetworkSpec(MAASServerTestCase):
    """Tests for `parse_network_spec`."""

    def test_accepts_network_name(self):
        network = factory.make_network()
        self.assertEqual(
            ('name', network.name),
            parse_network_spec(network.name))

    def test_rejects_invalid_name(self):
        self.assertRaises(ValidationError, parse_network_spec, '#.!')

    def test_rejects_unknown_type_tag(self):
        self.assertRaises(ValidationError, parse_network_spec, 'foo:bar')

    def test_accepts_ip_address(self):
        self.assertEqual(
            ('ip', IPAddress('10.9.8.7')),
            parse_network_spec('ip:10.9.8.7'))

    def test_rejects_untagged_ip_address(self):
        # If this becomes a stumbling block, it would be possible to accept
        # plain IP addresses as network specifiers.
        network = factory.make_network()
        ip = unicode(network.ip)
        self.assertRaises(ValidationError, parse_network_spec, ip)

    def test_rejects_empty_ip_address(self):
        self.assertRaises(ValidationError, parse_network_spec, 'ip:')

    def test_rejects_malformed_ip_address(self):
        self.assertRaises(ValidationError, parse_network_spec, 'ip:abc')

    def test_accepts_vlan_tag_in_range(self):
        network = factory.make_network(vlan_tag=1)
        self.assertEqual(
            ('vlan', network.vlan_tag),
            parse_network_spec('vlan:%d' % network.vlan_tag))

        network = factory.make_network(vlan_tag=4094)
        self.assertEqual(
            ('vlan', network.vlan_tag),
            parse_network_spec('vlan:%d' % network.vlan_tag))

    def test_rejects_empty_vlan_tag(self):
        self.assertRaises(ValidationError, parse_network_spec, 'vlan:')

    def test_rejects_nonnumerical_vlan_tag(self):
        self.assertRaises(ValidationError, parse_network_spec, 'vlan:B')

    def test_rejects_hexadecimal_vlan_tag(self):
        # Hexadecimal VLAN tags are a separate planned feature.
        self.assertRaises(ValidationError, parse_network_spec, 'vlan:0x1a')

    def test_rejects_reserved_vlan_tags(self):
        self.assertRaises(ValidationError, parse_network_spec, 'vlan:0')
        self.assertRaises(ValidationError, parse_network_spec, 'vlan:4095')

    def test_rejects_vlan_tag_out_of_range(self):
        self.assertRaises(ValidationError, parse_network_spec, 'vlan:-1')
        self.assertRaises(ValidationError, parse_network_spec, 'vlan:4096')


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
        vlan_tag = randint(1, 0xffe)
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
        vlan_tag = randint(0, 0xffe)
        description = factory.getRandomString()

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
        self.assertRaises(
            ValidationError, factory.make_network, vlan_tag=0xFFF)

    def test_out_of_range_vlan_tags_do_not_validate(self):
        self.assertRaises(
            ValidationError, factory.make_network, vlan_tag=0x1000)
        self.assertRaises(
            ValidationError, factory.make_network, vlan_tag=-1)

    def test_vlan_tag_normalises_zero_to_None(self):
        self.assertIsNone(factory.make_network(vlan_tag=0).vlan_tag)

    def test_nonzero_vlan_tag_is_unique(self):
        tag = randint(1, 0xffe)
        factory.make_network(vlan_tag=tag)
        self.assertRaises(ValidationError, factory.make_network, vlan_tag=tag)

    def test_zero_vlan_tag_is_not_unique(self):
        networks = [factory.make_network(vlan_tag=0) for _ in range(3)]
        self.assertEqual(
            sorted(networks, key=attrgetter('id')),
            list(Network.objects.filter(vlan_tag=None).order_by('id')))

    def test_get_network_returns_network(self):
        net = factory.getRandomNetwork()
        self.assertEqual(net, factory.make_network(network=net).get_network())

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
        network = IPNetwork('%s/%s' % (factory.getRandomIPAddress(), netmask))
        self.assertEqual(
            unicode(network.netmask),
            factory.make_network(network=network).netmask)

    def test_netmask_validation_does_not_allow_extreme_cases(self):
        ip = factory.getRandomIPAddress()
        self.assertRaises(
            ValidationError, factory.make_network,
            network=IPNetwork('%s/255.255.255.255' % ip))
        self.assertRaises(
            ValidationError, factory.make_network,
            network=IPNetwork('%s/0.0.0.0' % ip))

    def test_netmask_validation_does_not_allow_mixed_zeroes_and_ones(self):
        # The factory won't let us create a Network with a nonsensical netmask,
        # so to test this by updating an existing Network object.
        network = factory.make_network()
        network.netmask = '255.254.255.0'
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
