# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test AMP argument classes."""

__all__ = []

import random
import zlib

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.rpc import arguments
from provisioningserver.twisted.protocols import amp
from testtools import ExpectedException
from testtools.matchers import (
    Equals,
    IsInstance,
    LessThan,
)


class TestBytes(MAASTestCase):

    def test_round_trip(self):
        argument = arguments.Bytes()
        example = factory.make_bytes()
        encoded = argument.toString(example)
        self.assertThat(encoded, IsInstance(bytes))
        decoded = argument.fromString(encoded)
        self.assertThat(decoded, Equals(example))

    def test_error_when_input_is_not_a_byte_string(self):
        with ExpectedException(TypeError, "^Not a byte string: <.*"):
            arguments.Bytes().toString(object())


class TestChoice(MAASTestCase):

    def test_round_trip(self):
        choices = {
            factory.make_name("name"): factory.make_bytes()
            for _ in range(10)
        }
        argument = arguments.Choice(choices)
        choice = random.choice(list(choices))
        encoded = argument.toString(choice)
        self.assertThat(encoded, IsInstance(bytes))
        decoded = argument.fromString(encoded)
        self.assertThat(decoded, Equals(choice))

    def test_error_when_input_is_not_in_choices(self):
        with ExpectedException(KeyError, "^<object .*"):
            arguments.Choice({}).toString(object())

    def test_error_when_choices_is_not_mapping(self):
        with ExpectedException(TypeError, "^Not a mapping: \[\]"):
            arguments.Choice([])

    def test_error_when_choices_values_are_not_byte_strings(self):
        with ExpectedException(TypeError, "^Not byte strings: 'foo', 12345"):
            arguments.Choice({object(): 12345, object(): 'foo'})


class TestStructureAsJSON(MAASTestCase):

    example = {
        "an": "example", "structure": 12.34,
        "with": None, "and": ["lists", "of", "things"],
        "and": {"an": "embedded structure"},
    }

    def test_round_trip(self):
        argument = arguments.StructureAsJSON()
        encoded = argument.toString(self.example)
        self.assertThat(encoded, IsInstance(bytes))
        decoded = argument.fromString(encoded)
        self.assertThat(decoded, Equals(self.example))


class TestParsedURL(MAASTestCase):

    def test_round_trip(self):
        argument = arguments.ParsedURL()
        example = factory.make_parsed_url()
        encoded = argument.toString(example)
        self.assertThat(encoded, IsInstance(bytes))
        decoded = argument.fromString(encoded)
        self.assertThat(decoded.geturl(), Equals(example.geturl()))

    def test_error_when_input_is_not_a_url_object(self):
        with ExpectedException(TypeError, "^Not a URL-like object: <.*"):
            arguments.ParsedURL().toString(object())

    def test_netloc_containing_non_ascii_characters_is_encoded_to_idna(self):
        argument = arguments.ParsedURL()
        example = factory.make_parsed_url()._replace(
            netloc='\u24b8\u211d\U0001d538\u24b5\U0001d502')
        encoded = argument.toString(example)
        self.assertThat(encoded, IsInstance(bytes))
        decoded = argument.fromString(encoded)
        # The non-ASCII netloc was encoded using IDNA.
        expected = example._replace(netloc="cra(z)y")
        self.assertThat(decoded.geturl(), Equals(expected.geturl()))


class TestAmpList(MAASTestCase):

    def test_round_trip(self):
        argument = arguments.AmpList([(b"thing", amp.Unicode())])
        example = [{"thing": factory.make_name("thing")}]
        encoded = argument.toStringProto(example, proto=None)
        self.assertThat(encoded, IsInstance(bytes))
        decoded = argument.fromStringProto(encoded, proto=None)
        self.assertEqual(example, decoded)


class TestCompressedAmpList(MAASTestCase):

    def test_round_trip(self):
        argument = arguments.CompressedAmpList([("thing", amp.Unicode())])
        example = [{"thing": factory.make_name("thing")}]
        encoded = argument.toStringProto(example, proto=None)
        self.assertThat(encoded, IsInstance(bytes))
        decoded = argument.fromStringProto(encoded, proto=None)
        self.assertEqual(example, decoded)

    def test_compression_is_worth_it(self):
        argument = arguments.CompressedAmpList(
            [("ip", amp.Unicode()), ("mac", amp.Unicode())])
        # Create 3500 leases. We can get up to ~3750 and still satisfy the
        # post-conditions, but the randomness means we can't be sure about
        # test stability that close to the limit.
        leases = [
            {"ip": factory.make_ipv4_address(),
             "mac": factory.make_mac_address()}
            for _ in range(3500)
        ]
        encoded_compressed = argument.toStringProto(leases, proto=None)
        encoded_uncompressed = zlib.decompress(encoded_compressed)
        # The encoded leases compress to less than half the size of the
        # uncompressed leases, and under the AMP message limit of 64k.
        self.expectThat(
            len(encoded_compressed),
            LessThan(len(encoded_uncompressed) / 2))
        self.expectThat(
            len(encoded_compressed),
            LessThan(2 ** 16))
