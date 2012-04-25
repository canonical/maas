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
import os.path

from maastesting.factory import factory
from maastesting.testcase import TestCase
from testtools.matchers import (
    FileContains,
    FileExists,
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

    def test_getRandomDate_returns_datetime(self):
        self.assertIsInstance(factory.getRandomDate(), datetime)

    def test_getRandomMACAddress(self):
        mac_address = factory.getRandomMACAddress()
        self.assertIsInstance(mac_address, str)
        self.assertEqual(17, len(mac_address))
        for hex_octet in mac_address.split(":"):
            self.assertTrue(0 <= int(hex_octet, 16) <= 255)

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
