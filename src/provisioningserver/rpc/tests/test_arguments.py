# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test AMP argument classes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.rpc import arguments
from testtools import ExpectedException
from testtools.matchers import (
    Equals,
    IsInstance,
    )


class TestBytes(MAASTestCase):

    def test_round_trip(self):
        argument = arguments.Bytes()
        example = factory.getRandomBytes()
        encoded = argument.toString(example)
        self.assertThat(encoded, IsInstance(bytes))
        decoded = argument.fromString(encoded)
        self.assertThat(decoded, Equals(example))

    def test_error_when_input_is_not_a_byte_string(self):
        with ExpectedException(TypeError, "^Not a byte string: <.*"):
            arguments.Bytes().toString(object())


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
            netloc=u'\u24b8\u211d\U0001d538\u24b5\U0001d502')
        encoded = argument.toString(example)
        self.assertThat(encoded, IsInstance(bytes))
        decoded = argument.fromString(encoded)
        # The non-ASCII netloc was encoded using IDNA.
        expected = example._replace(netloc="cra(z)y")
        self.assertThat(decoded.geturl(), Equals(expected.geturl()))
