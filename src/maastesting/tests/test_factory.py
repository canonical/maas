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

from maastesting.factory import factory
from maastesting.testcase import TestCase


class TestFactory(TestCase):

    def test_getRandomString_respects_size(self):
        sizes = [1, 10, 100]
        random_strings = [factory.getRandomString(size) for size in sizes]
        self.assertEqual(sizes, [len(string) for string in random_strings])

    def test_getRandomBoolean_returns_bool(self):
        self.assertIsInstance(factory.getRandomBoolean(), bool)

    def test_getRandomPort_returns_int(self):
        self.assertIsInstance(factory.getRandomPort(), int)

    def test_getRandomMACAddress(self):
        mac_address = factory.getRandomMACAddress()
        self.assertIsInstance(mac_address, str)
        self.assertEqual(17, len(mac_address))
        for hex_octet in mac_address.split(":"):
            self.assertTrue(0 <= int(hex_octet, 16) <= 255)
