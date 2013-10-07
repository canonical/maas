# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test encoding requests as JSON."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from apiclient.encode_json import encode_json_data
from maastesting.testcase import MAASTestCase


class TestEncodeJSONData(MAASTestCase):

    def assertEncodeJSONData(self, expected_body, expected_headers, params):
        self.assertEqual(
            (expected_body, expected_headers),
            encode_json_data(params))

    def test_encode_empty_dict(self):
        self.assertEncodeJSONData(
            '{}', {'Content-Length': '2', 'Content-Type': 'application/json'},
            {})

    def test_encode_dict(self):
        self.assertEncodeJSONData(
            '{"alt": [1, 2, 3, 4], "param": "value"}',
            {'Content-Length': '39', 'Content-Type': 'application/json'},
            {'param': 'value', 'alt': [1, 2, 3, 4]})
