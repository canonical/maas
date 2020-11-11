# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test encoding requests as JSON."""

import json
from unittest import TestCase

from apiclient.encode_json import encode_json_data


class TestEncodeJSONData(TestCase):
    def assertEncodeJSONData(self, expected_body, expected_headers):
        observed_body, observed_headers = encode_json_data(expected_body)
        self.assertEqual(observed_headers, expected_headers)
        self.assertEqual(json.loads(observed_body), expected_body)

    def test_encode_empty_dict(self):
        body, headers = encode_json_data({})
        self.assertEqual(json.loads(body), {})
        self.assertEqual(
            headers,
            {"Content-Length": "2", "Content-Type": "application/json"},
        )

    def test_encode_dict(self):
        data = {"param": "value", "alt": [1, 2, 3, 4]}
        body, headers = encode_json_data(data)
        self.assertEqual(json.loads(body), data)
        self.assertEqual(
            headers,
            {"Content-Length": "39", "Content-Type": "application/json"},
        )
