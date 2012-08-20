# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the factory where appropriate.  Don't overdo this."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from datetime import datetime
from itertools import count
import os.path
from random import randint

from maastesting.factory import factory
from maastesting.testcase import TestCase
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


class TestFactory(TestCase):

    def test_getRandomString_respects_size(self):
        sizes = [1, 10, 100]
        random_strings = [factory.getRandomString(size) for size in sizes]
        self.assertEqual(sizes, [len(string) for string in random_strings])

    def test_getRandomBoolean_returns_bool(self):
        self.assertIsInstance(factory.getRandomBoolean(), bool)

    def test_getRandomPort_returns_int(self):
        self.assertIsInstance(factory.getRandomPort(), int)

    def test_getRandomIPAddress(self):
        ip_address = factory.getRandomIPAddress()
        self.assertIsInstance(ip_address, str)
        octets = ip_address.split('.')
        self.assertEqual(4, len(octets))
        for octet in octets:
            self.assertTrue(0 <= int(octet) <= 255)

    def test_getRandomNetwork(self):
        network = factory.getRandomNetwork()
        self.assertIsInstance(network, IPNetwork)

    def test_getRandomIPInNetwork(self):
        network = factory.getRandomNetwork()
        ip = factory.getRandomIPInNetwork(network)
        self.assertTrue(
            network.first <= IPAddress(ip).value <= network.last)

    def test_getRandomDate_returns_datetime(self):
        self.assertIsInstance(factory.getRandomDate(), datetime)

    def test_getRandomMACAddress(self):
        mac_address = factory.getRandomMACAddress()
        self.assertIsInstance(mac_address, str)
        self.assertEqual(17, len(mac_address))
        for hex_octet in mac_address.split(":"):
            self.assertTrue(0 <= int(hex_octet, 16) <= 255)

    def test_getRandomMACAddress_alternative_delimiter(self):
        self.patch(factory, "random_octets", count(0x3a))
        mac_address = factory.getRandomMACAddress(delimiter=b"-")
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
        contents = factory.getRandomString().encode('ascii')
        self.assertThat(
            factory.make_file(self.make_dir(), contents=contents),
            FileContains(contents))

    def test_make_file_makes_up_contents_if_none_given(self):
        with open(factory.make_file(self.make_dir())) as temp_file:
            contents = temp_file.read()
        self.assertNotEqual('', contents)

    def test_make_file_uses_given_name(self):
        name = factory.getRandomString()
        self.assertEqual(
            name,
            os.path.basename(factory.make_file(self.make_dir(), name=name)))

    def test_make_file_uses_given_dir(self):
        directory = self.make_dir()
        name = factory.getRandomString()
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
        prefix = factory.getRandomString(3)
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
