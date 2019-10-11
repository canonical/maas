# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test encoding requests as JSON."""

__all__ = []

import json

from apiclient.encode_json import encode_json_data
from maastesting.testcase import MAASTestCase
from testtools.matchers import Equals


class TestEncodeJSONData(MAASTestCase):
    def assertEncodeJSONData(self, expected_body, expected_headers):
        observed_body, observed_headers = encode_json_data(expected_body)
        self.expectThat(observed_headers, Equals(expected_headers))
        self.expectThat(json.loads(observed_body), Equals(expected_body))

    def test_encode_empty_dict(self):
        self.assertEncodeJSONData(
            {}, {"Content-Length": "2", "Content-Type": "application/json"}
        )

    def test_encode_dict(self):
        self.assertEncodeJSONData(
            {"param": "value", "alt": [1, 2, 3, 4]},
            {"Content-Length": "39", "Content-Type": "application/json"},
        )
