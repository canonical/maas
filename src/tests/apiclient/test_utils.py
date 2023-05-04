# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest import TestCase
from urllib.parse import unquote

from django.utils.encoding import smart_str

from apiclient.utils import ascii_url, urlencode


class TestHelpers(TestCase):
    def test_ascii_url_leaves_ascii_bytes_unchanged(self):
        self.assertEqual(
            b"http://example.com/", ascii_url(b"http://example.com/")
        )
        self.assertIsInstance(ascii_url(b"http://example.com"), bytes)

    def test_ascii_url_asciifies_unicode(self):
        self.assertEqual(
            b"http://example.com/", ascii_url("http://example.com/")
        )
        self.assertIsInstance(ascii_url("http://example.com"), bytes)

    def test_urlencode_encodes_utf8_and_quotes(self):
        # urlencode UTF-8 encodes unicode strings and applies standard query
        # string quoting rules, and always returns a byte string.
        data = [("=\u1234", "&\u4321")]
        query = urlencode(data)
        self.assertEqual(query, "%3D%E1%88%B4=%26%E4%8C%A1")

    def test_urlencode_roundtrip_through_django(self):
        # Check that urlencode's approach works with Django, as described on
        # https://docs.djangoproject.com/en/dev/ref/unicode/.
        data = [("=\u1234", "&\u4321")]
        query = urlencode(data)
        name, value = query.split("=")
        name, value = unquote(name), unquote(value)
        name, value = smart_str(name), smart_str(value)
        self.assertEqual(data, [(name, value)])
