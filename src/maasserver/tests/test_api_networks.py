# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for networks API."""

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
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory


class TestNetworksAPI(APITestCase):

    def test_handler_path(self):
        self.assertEqual('/api/1.0/networks/', reverse('networks_handler'))

    def test_list_returns_networks(self):
        original_network = factory.make_network()

        response = self.client.get(reverse('networks_handler'))
        self.assertEqual(httplib.OK, response.status_code, response.content)

        parsed_result = json.loads(response.content)
        self.assertEqual(1, len(parsed_result))
        [returned_network] = parsed_result
        fields = {'name', 'ip', 'netmask', 'vlan_tag', 'description'}
        self.assertEqual(fields, set(returned_network.keys()))
        self.assertEqual(
            {
                field: getattr(original_network, field)
                for field in fields
            },
            returned_network)

    def test_list_returns_empty_if_no_networks(self):
        response = self.client.get(reverse('networks_handler'))
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual([], json.loads(response.content))

    def test_list_sorts_by_name(self):
        original_names = [factory.make_name('net').lower() for _ in range(3)]
        for name in original_names:
            factory.make_network(name=name)

        response = self.client.get(reverse('networks_handler'))
        self.assertEqual(httplib.OK, response.status_code, response.content)

        self.assertEqual(
            sorted(original_names),
            [network['name'] for network in json.loads(response.content)])
