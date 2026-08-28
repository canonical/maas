# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test AMP argument classes."""

import copy
import random

import attr
import netaddr
from testtools import ExpectedException
from testtools.matchers import HasLength
from twisted.protocols import amp

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.rpc import arguments


class TestBytes(MAASTestCase):
    def test_round_trip(self):
        argument = arguments.Bytes()
        example = factory.make_bytes()
        encoded = argument.toString(example)
        self.assertIsInstance(encoded, bytes)
        decoded = argument.fromString(encoded)
        self.assertEqual(example, decoded)

    def test_error_when_input_is_not_a_byte_string(self):
        with ExpectedException(TypeError, "^Not a byte string: <.*"):
            arguments.Bytes().toString(object())


class TestChoice(MAASTestCase):
    def test_round_trip(self):
        choices = {
            factory.make_name("name"): factory.make_bytes() for _ in range(10)
        }
        argument = arguments.Choice(choices)
        choice = random.choice(list(choices))
        encoded = argument.toString(choice)
        self.assertIsInstance(encoded, bytes)
        decoded = argument.fromString(encoded)
        self.assertEqual(choice, decoded)

    def test_error_when_input_is_not_in_choices(self):
        with ExpectedException(KeyError, "^<object .*"):
            arguments.Choice({}).toString(object())

    def test_error_when_choices_is_not_mapping(self):
        with ExpectedException(TypeError, r"^Not a mapping: \[\]"):
            arguments.Choice([])

    def test_error_when_choices_values_are_not_byte_strings(self):
        with ExpectedException(TypeError, "^Not byte strings: 'foo', 12345"):
            arguments.Choice({object(): 12345, object(): "foo"})


class TestStructureAsJSON(MAASTestCase):
    example = {
        "an": "example",
        "structure": 12.34,
        "with": None,
        "and": ["lists", "of", "things"],
        "and also": {"an": "embedded structure"},
    }

    def test_round_trip(self):
        argument = arguments.StructureAsJSON()
        encoded = argument.toString(self.example)
        self.assertIsInstance(encoded, bytes)
        decoded = argument.fromString(encoded)
        self.assertEqual(self.example, decoded)


@attr.s
class SampleAttrs:
    foo = attr.ib(converter=str)
    bar = attr.ib(converter=int)


class TestAttrsClassArgument(MAASTestCase):
    def test_round_trip(self):
        sample = SampleAttrs(foo="foo", bar=10)
        argument = arguments.AttrsClassArgument(
            "provisioningserver.rpc.tests.test_arguments.SampleAttrs"
        )
        encoded = argument.toString(sample)
        self.assertIsInstance(encoded, bytes)
        decoded = argument.fromString(encoded)
        self.assertEqual(decoded, sample)


class TestParsedURL(MAASTestCase):
    def test_round_trip(self):
        argument = arguments.ParsedURL()
        example = factory.make_parsed_url()
        encoded = argument.toString(example)
        self.assertIsInstance(encoded, bytes)
        decoded = argument.fromString(encoded)
        self.assertEqual(example.geturl(), decoded.geturl())

    def test_error_when_input_is_not_a_url_object(self):
        with ExpectedException(TypeError, "^Not a URL-like object: <.*"):
            arguments.ParsedURL().toString(object())

    def test_netloc_containing_non_ascii_characters_is_encoded_to_idna(self):
        argument = arguments.ParsedURL()
        example = factory.make_parsed_url()._replace(
            netloc="\u24b8\u211d\U0001d538\u24b5\U0001d502"
        )
        encoded = argument.toString(example)
        self.assertIsInstance(encoded, bytes)
        decoded = argument.fromString(encoded)
        # The non-ASCII netloc was encoded using IDNA.
        expected = example._replace(netloc="cra(z)y")
        self.assertEqual(expected.geturl(), decoded.geturl())


class TestAmpList(MAASTestCase):
    def test_round_trip(self):
        argument = arguments.AmpList([(b"thing", amp.Unicode())])
        example = [{"thing": factory.make_name("thing")}]
        encoded = argument.toStringProto(example, proto=None)
        self.assertIsInstance(encoded, bytes)
        decoded = argument.fromStringProto(encoded, proto=None)
        self.assertEqual(example, decoded)


class TestCompressedAmpList(MAASTestCase):
    def test_round_trip(self):
        argument = arguments.CompressedAmpList([("thing", amp.Unicode())])
        arg_name = factory.make_name()
        b_arg_name = arg_name.encode()
        example = {arg_name: [{"thing": factory.make_name("thing")}]}

        box = {}
        argument.toBox(b_arg_name, box, example.copy(), None)
        self.assertIsInstance(box[b_arg_name], bytes)

        decoded = {}
        argument.fromBox(b_arg_name, box, decoded, None)
        self.assertEqual(example, decoded)

    def test_compression_is_worth_it(self):
        arg_name = "leases"
        b_arg_name = arg_name.encode()
        argument = arguments.CompressedAmpList(
            [("ip", amp.Unicode()), ("mac", amp.Unicode())]
        )
        leases = {
            arg_name: [
                {
                    "ip": factory.make_ipv4_address(),
                    "mac": factory.make_mac_address(),
                }
                for _ in range(10000)
            ]
        }

        expected = copy.deepcopy(leases)
        box = {}

        argument.toBox(b_arg_name, box, leases, None)
        self.assertEqual(len(box.keys()), 3)
        for v in box.values():
            self.assertLess(len(v), 2**16)

        decoded = {}
        argument.fromBox(b_arg_name, box, decoded, None)
        self.assertEqual(expected, decoded)


class TestIPAddress(MAASTestCase):
    argument = arguments.IPAddress()

    def test_round_trips_ipv4_address(self):
        address = netaddr.IPAddress("192.168.34.87")
        encoded = self.argument.toString(address)
        self.assertIsInstance(encoded, bytes)
        self.assertThat(encoded, HasLength(4))
        decoded = self.argument.fromString(encoded)
        self.assertEqual(address, decoded)

    def test_round_trips_ipv6_address(self):
        address = netaddr.IPAddress("fd28:8d1a:6c8e::345")
        encoded = self.argument.toString(address)
        self.assertIsInstance(encoded, bytes)
        self.assertThat(encoded, HasLength(16))
        decoded = self.argument.fromString(encoded)
        self.assertEqual(address, decoded)

    def test_round_trips_ipv6_mapped_ipv4_address(self):
        address = netaddr.IPAddress("::ffff:10.78.45.9")
        encoded = self.argument.toString(address)
        self.assertIsInstance(encoded, bytes)
        self.assertThat(encoded, HasLength(16))
        decoded = self.argument.fromString(encoded)
        self.assertEqual(address, decoded)


class TestIPNetwork(MAASTestCase):
    argument = arguments.IPNetwork()

    def test_round_trips_ipv4_address(self):
        network = factory.make_ipv4_network()
        encoded = self.argument.toString(network)
        self.assertIsInstance(encoded, bytes)
        self.assertThat(encoded, HasLength(5))
        decoded = self.argument.fromString(encoded)
        self.assertEqual(network, decoded)

    def test_round_trips_ipv6_address(self):
        network = factory.make_ipv6_network()
        encoded = self.argument.toString(network)
        self.assertIsInstance(encoded, bytes)
        self.assertThat(encoded, HasLength(17))
        decoded = self.argument.fromString(encoded)
        self.assertEqual(network, decoded)
