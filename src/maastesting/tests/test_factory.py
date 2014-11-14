# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the

# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the factory where appropriate.  Don't overdo this."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from datetime import datetime
from itertools import count
import os.path
import random
from random import randint
import subprocess

from maastesting.factory import (
    factory,
    TooManyRandomRetries,
    )
from maastesting.testcase import MAASTestCase
from maastesting.utils import FakeRandInt
from netaddr import (
    IPAddress,
    IPNetwork,
    )
from testtools.matchers import (
    Contains,
    FileContains,
    FileExists,
    MatchesAll,
    Not,
    StartsWith,
    )


class TestFactory(MAASTestCase):

    def test_make_string_respects_size(self):
        sizes = [1, 10, 100]
        random_strings = [factory.make_string(size) for size in sizes]
        self.assertEqual(sizes, [len(string) for string in random_strings])

    def test_pick_bool_returns_bool(self):
        self.assertIsInstance(factory.pick_bool(), bool)

    def test_pick_port_returns_int(self):
        self.assertIsInstance(factory.pick_port(), int)

    def test_make_vlan_tag_excludes_None_by_default(self):
        # Artificially limit randint to a very narrow range, to guarantee
        # some repetition in its output, and virtually guarantee that we test
        # both outcomes of the flip-a-coin call in make_vlan_tag.
        self.patch(random, 'randint', FakeRandInt(random.randint, 0, 1))
        outcomes = {factory.make_vlan_tag() for _ in range(1000)}
        self.assertEqual({1}, outcomes)

    def test_make_vlan_tag_includes_None_if_allow_none(self):
        self.patch(random, 'randint', FakeRandInt(random.randint, 0, 1))
        self.assertEqual(
            {None, 1},
            {
                factory.make_vlan_tag(allow_none=True)
                for _ in range(1000)
            })

    def test_make_ipv4_address(self):
        ip_address = factory.make_ipv4_address()
        self.assertIsInstance(ip_address, unicode)
        octets = ip_address.split('.')
        self.assertEqual(4, len(octets))
        for octet in octets:
            self.assertTrue(0 <= int(octet) <= 255)

    def test_make_ipv4_address_but_not(self):
        # We want to look for clashes between identical IPs and/or netmasks.
        # Narrow down the range of randomness so we have a decent chance of
        # triggering a clash, but not so far that we'll loop for very long
        # trying to find a network we haven't seen already.
        self.patch(
            factory, 'make_ipv4_address',
            lambda: '10.%d.0.0' % randint(1, 200))
        networks = []
        for _ in range(100):
            networks.append(factory.make_ipv4_network(but_not=networks))
        self.assertEquals(len(networks), len(set(networks)))

    def test_make_UUID(self):
        uuid = factory.make_UUID()
        self.assertIsInstance(uuid, unicode)
        self.assertEqual(36, len(uuid))

    def test_make_ipv4_network(self):
        network = factory.make_ipv4_network()
        self.assertIsInstance(network, IPNetwork)

    def test_make_ipv4_network_respects_but_not(self):
        self.patch(factory, 'make_ipv4_address').return_value = IPAddress(
            '10.1.1.0')
        self.assertRaises(
            TooManyRandomRetries,
            factory.make_ipv4_network,
            slash=24, but_not=[IPNetwork('10.1.1.0/24')])

    def test_make_ipv4_network_returns_network_not_in_but_not(self):
        self.patch(factory, 'make_ipv4_address').return_value = IPAddress(
            '10.1.1.0')
        self.assertEqual(
            IPNetwork('10.1.1.0/24'),
            factory.make_ipv4_network(
                slash=24, but_not=[IPNetwork('10.9.9.0/24')]))

    def test_make_ipv4_network_may_overlap_but_not(self):
        self.patch(factory, 'make_ipv4_address').return_value = IPAddress(
            '10.1.1.0')
        self.assertEqual(
            IPNetwork('10.1.1.0/24'),
            factory.make_ipv4_network(
                slash=24, but_not=[IPNetwork('10.1.0.0/16')]))

    def test_make_ipv4_network_avoids_network_in_disjoint_from(self):
        self.patch(factory, 'make_ipv4_address').return_value = IPAddress(
            '10.1.1.0')
        self.assertRaises(
            TooManyRandomRetries,
            factory.make_ipv4_network,
            slash=24, disjoint_from=[IPNetwork('10.1.1.0/24')])

    def test_make_ipv4_network_avoids_network_overlapping_disjoint_from(self):
        self.patch(factory, 'make_ipv4_address').return_value = IPAddress(
            '10.1.1.0')
        self.assertRaises(
            TooManyRandomRetries,
            factory.make_ipv4_network,
            slash=24, disjoint_from=[IPNetwork('10.1.0.0/16')])

    def test_make_ipv4_network_returns_network_disjoint_from(self):
        existing_network = factory.make_ipv4_network()
        new_network = factory.make_ipv4_network(
            disjoint_from=[existing_network])
        self.assertNotEqual(existing_network, new_network)
        self.assertNotIn(new_network, existing_network)
        self.assertNotIn(existing_network, new_network)

    def test_pick_ip_in_network(self):
        network = factory.make_ipv4_network()
        ip = factory.pick_ip_in_network(network)
        self.assertTrue(
            network.first <= IPAddress(ip).value <= network.last)

    def test_make_ip_range_returns_IPs(self):
        low, high = factory.make_ip_range()
        self.assertIsInstance(low, IPAddress)
        self.assertIsInstance(high, IPAddress)
        self.assertLess(low, high)

    def test_make_ip_range_obeys_network(self):
        network = factory.make_ipv4_network()
        low, high = factory.make_ip_range(network)
        self.assertIn(low, network)
        self.assertIn(high, network)

    def test_make_ip_range_returns_low_and_high(self):
        # Make a very very small network, to maximise the chances of exposure
        # if the method gets this wrong e.g. by returning identical addresses.
        low, high = factory.make_ip_range(factory.make_ipv4_network(slash=31))
        self.assertLess(low, high)

    def test_make_ip_range_obeys_but_not(self):
        # Make a very very small network, to maximise the chances of exposure
        # if the method gets this wrong.
        network = factory.make_ipv4_network(slash=30)
        first_low, first_high = factory.make_ip_range(network)
        second_low, second_high = factory.make_ip_range(
            network, but_not=(first_low, first_high))
        self.assertNotEqual((first_low, first_high), (second_low, second_high))

    def test_make_date_returns_datetime(self):
        self.assertIsInstance(factory.make_date(), datetime)

    def test_make_mac_address(self):
        mac_address = factory.make_mac_address()
        self.assertIsInstance(mac_address, unicode)
        self.assertEqual(17, len(mac_address))
        for hex_octet in mac_address.split(":"):
            self.assertTrue(0 <= int(hex_octet, 16) <= 255)

    def test_make_mac_address_alternative_delimiter(self):
        self.patch(factory, "random_octets", count(0x3a))
        mac_address = factory.make_mac_address(delimiter="-")
        self.assertEqual("3a-3b-3c-3d-3e-3f", mac_address)

    def test_make_random_leases_maps_ips_to_macs(self):
        [(ip, mac)] = factory.make_random_leases().items()
        self.assertEqual(
            4, len(ip.split('.')),
            "IP address does not look like an IP address: '%s'" % ip)
        self.assertEqual(
            6, len(mac.split(':')),
            "MAC address does not look like a MAC address: '%s'" % mac)

    def test_make_random_leases_randomizes_ips(self):
        self.assertNotEqual(
            factory.make_random_leases().keys(),
            factory.make_random_leases().keys())

    def test_make_random_leases_randomizes_macs(self):
        self.assertNotEqual(
            factory.make_random_leases().values(),
            factory.make_random_leases().values())

    def test_make_random_leases_returns_requested_number_of_leases(self):
        num_leases = randint(0, 3)
        self.assertEqual(
            num_leases,
            len(factory.make_random_leases(num_leases)))

    def test_make_file_creates_file(self):
        self.assertThat(factory.make_file(self.make_dir()), FileExists())

    def test_make_file_writes_contents(self):
        contents = factory.make_string().encode('ascii')
        self.assertThat(
            factory.make_file(self.make_dir(), contents=contents),
            FileContains(contents))

    def test_make_file_makes_up_contents_if_none_given(self):
        with open(factory.make_file(self.make_dir())) as temp_file:
            contents = temp_file.read()
        self.assertNotEqual('', contents)

    def test_make_file_uses_given_name(self):
        name = factory.make_string()
        self.assertEqual(
            name,
            os.path.basename(factory.make_file(self.make_dir(), name=name)))

    def test_make_file_uses_given_dir(self):
        directory = self.make_dir()
        name = factory.make_string()
        self.assertEqual(
            (directory, name),
            os.path.split(factory.make_file(directory, name=name)))

    def test_make_name_returns_unicode(self):
        self.assertIsInstance(factory.make_name(), unicode)

    def test_make_name_includes_prefix_and_separator(self):
        self.assertThat(factory.make_name('abc'), StartsWith('abc-'))

    def test_make_name_includes_random_text_of_requested_length(self):
        size = randint(1, 99)
        self.assertEqual(
            len('prefix') + len('-') + size,
            len(factory.make_name('prefix', size=size)))

    def test_make_name_includes_random_text(self):
        self.assertNotEqual(
            factory.make_name(size=100), factory.make_name(size=100))

    def test_make_name_uses_configurable_separator(self):
        sep = 'SEPARATOR'
        prefix = factory.make_string(3)
        self.assertThat(
            factory.make_name(prefix, sep=sep),
            StartsWith(prefix + sep))

    def test_make_name_does_not_require_prefix(self):
        size = randint(1, 99)
        unprefixed_name = factory.make_name(sep='-', size=size)
        self.assertEqual(size, len(unprefixed_name))
        self.assertThat(unprefixed_name, Not(StartsWith('-')))

    def test_make_name_does_not_include_weird_characters(self):
        self.assertThat(
            factory.make_name(size=100),
            MatchesAll(*[Not(Contains(char)) for char in '/ \t\n\r\\']))

    def test_make_names_calls_make_name_with_each_prefix(self):
        self.patch(factory, "make_name", lambda prefix: prefix + "-xxx")
        self.assertSequenceEqual(
            ["abc-xxx", "def-xxx", "ghi-xxx"],
            list(factory.make_names("abc", "def", "ghi")))

    def test_make_tarball_writes_tarball(self):
        filename = factory.make_name()
        contents = {filename: factory.make_string()}

        tarball = factory.make_tarball(self.make_dir(), contents)

        dest = self.make_dir()
        subprocess.check_call(['tar', '-xzf', tarball, '-C', dest])
        self.assertThat(
            os.path.join(dest, filename),
            FileContains(contents[filename]))

    def test_make_tarball_makes_up_content_if_None(self):
        filename = factory.make_name()
        tarball = factory.make_tarball(self.make_dir(), {filename: None})

        dest = self.make_dir()
        subprocess.check_call(['tar', '-xzf', tarball, '-C', dest])
        self.assertThat(os.path.join(dest, filename), FileExists())
        with open(os.path.join(dest, filename), 'rb') as unpacked_file:
            contents = unpacked_file.read()
        self.assertGreater(len(contents), 0)
