# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test general utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from apiclient.utils import ascii_url
from maastesting.testcase import TestCase


class TestHelpers(TestCase):

    def test_ascii_url_leaves_ascii_bytes_unchanged(self):
        self.assertEqual(
            b'http://example.com/', ascii_url(b'http://example.com/'))
        self.assertIsInstance(ascii_url(b'http://example.com'), bytes)

    def test_ascii_url_asciifies_unicode(self):
        self.assertEqual(
            b'http://example.com/', ascii_url('http://example.com/'))
        self.assertIsInstance(ascii_url('http://example.com'), bytes)
