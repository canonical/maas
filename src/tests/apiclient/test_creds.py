# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for handling of MAAS API credentials."""

from unittest import TestCase

from apiclient.creds import convert_string_to_tuple, convert_tuple_to_string
from apiclient.testing.credentials import make_api_credentials


class TestCreds(TestCase):
    def test_convert_tuple_to_string_converts_tuple_to_string(self):
        creds_tuple = make_api_credentials()
        self.assertEqual(
            ":".join(creds_tuple), convert_tuple_to_string(creds_tuple)
        )

    def test_convert_tuple_to_string_rejects_undersized_tuple(self):
        self.assertRaises(
            ValueError, convert_tuple_to_string, make_api_credentials()[:-1]
        )

    def test_convert_tuple_to_string_rejects_oversized_tuple(self):
        self.assertRaises(
            ValueError,
            convert_tuple_to_string,
            make_api_credentials() + make_api_credentials()[:1],
        )

    def test_convert_string_to_tuple_converts_string_to_tuple(self):
        creds_tuple = make_api_credentials()
        creds_string = ":".join(creds_tuple)
        self.assertEqual(creds_tuple, convert_string_to_tuple(creds_string))

    def test_convert_string_to_tuple_detects_malformed_string(self):
        broken_tuple = make_api_credentials()[:-1]
        self.assertRaises(
            ValueError, convert_string_to_tuple, ":".join(broken_tuple)
        )

    def test_convert_string_to_tuple_detects_spurious_colons(self):
        broken_tuple = make_api_credentials() + make_api_credentials()[:1]
        self.assertRaises(
            ValueError, convert_string_to_tuple, ":".join(broken_tuple)
        )

    def test_convert_string_to_tuple_inverts_convert_tuple_to_string(self):
        creds_tuple = make_api_credentials()
        self.assertEqual(
            creds_tuple,
            convert_string_to_tuple(convert_tuple_to_string(creds_tuple)),
        )
