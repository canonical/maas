# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver API version."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


import httplib
import json

from django.core.urlresolvers import reverse
from maasserver.api import API_CAPABILITIES_LIST
from maasserver.testing.testcase import MAASServerTestCase


class TestFindingResources(MAASServerTestCase):
    """Tests for /version/ API."""

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/version/', reverse('version'))

    def test_GET_returns_details(self):
        response = self.client.get(reverse('version'))
        self.assertEqual(httplib.OK, response.status_code)

        parsed_result = json.loads(response.content)
        self.assertEqual(
            {
                'capabilities': API_CAPABILITIES_LIST,
            },
            parsed_result)
