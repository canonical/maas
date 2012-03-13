# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the factory where appropriate.  Don't overdo this."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from random import randint

from maasserver.testing.factory import factory
from maastesting.testcase import TestCase


class TestFactory(TestCase):

    def test_getRandomString_respects_size(self):
        sizes = [1, 10, 100]
        random_strings = [factory.getRandomString(size) for size in sizes]
        self.assertEqual(sizes, [len(string) for string in random_strings])

    def test_getRandomBoolean_returns_bool(self):
        self.assertIsInstance(factory.getRandomBoolean(), bool)

    def test_getRandomEnum_returns_enum_value(self):
        random_value = randint(0, 99999)

        class Enum:
            VALUE = random_value
            OTHER_VALUE = random_value + 3

        self.assertIn(
            factory.getRandomEnum(Enum), [Enum.VALUE, Enum.OTHER_VALUE])

    def test_getRandomChoice_chooses_from_django_options(self):
        options = [(2, 'b'), (10, 'j')]
        self.assertIn(
            factory.getRandomChoice(options),
            [option[0] for option in options])
