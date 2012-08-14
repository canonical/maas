# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for handling of MAAS API credentials."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from apiclient.creds import (
    convert_string_to_tuple,
    convert_tuple_to_string,
    )
from maastesting.factory import factory
from maastesting.testcase import TestCase


class TestCreds(TestCase):

    def make_tuple(self):
        return (
            factory.make_name('consumer-key'),
            factory.make_name('resource-token'),
            factory.make_name('resource-secret'),
            )

    def test_convert_tuple_to_string_converts_tuple_to_string(self):
        creds_tuple = self.make_tuple()
        self.assertEqual(
            ':'.join(creds_tuple), convert_tuple_to_string(creds_tuple))

    def test_convert_tuple_to_string_rejects_undersized_tuple(self):
        self.assertRaises(
            ValueError,
            convert_tuple_to_string,
            self.make_tuple()[:-1])

    def test_convert_tuple_to_string_rejects_oversized_tuple(self):
        self.assertRaises(
            ValueError,
            convert_tuple_to_string,
            self.make_tuple() + self.make_tuple()[:1])

    def test_convert_string_to_tuple_converts_string_to_tuple(self):
        creds_tuple = self.make_tuple()
        creds_string = ':'.join(creds_tuple)
        self.assertEqual(creds_tuple, convert_string_to_tuple(creds_string))

    def test_convert_string_to_tuple_detects_malformed_string(self):
        broken_tuple = self.make_tuple()[:-1]
        self.assertRaises(
            ValueError,
            convert_string_to_tuple,
            ':'.join(broken_tuple))

    def test_convert_string_to_tuple_detects_spurious_colons(self):
        broken_tuple = self.make_tuple() + self.make_tuple()[:1]
        self.assertRaises(
            ValueError,
            convert_string_to_tuple,
            ':'.join(broken_tuple))

    def test_convert_string_to_tuple_inverts_convert_tuple_to_string(self):
        creds_tuple = self.make_tuple()
        self.assertEqual(
            creds_tuple,
            convert_string_to_tuple(convert_tuple_to_string(creds_tuple)))
