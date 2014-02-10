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
from maasserver.models import Network
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.orm import get_one


class TestNetworksAPI(APITestCase):

    def test_handler_path(self):
        self.assertEqual('/api/1.0/networks/', reverse('networks_handler'))

    def test_POST_creates_network(self):
        self.become_admin()
        net = factory.getRandomNetwork()
        params = {
            'name': factory.make_name('net'),
            'ip': '%s' % net.cidr.ip,
            'netmask': '%s' % net.netmask,
            'vlan_tag': factory.make_vlan_tag(),
            'description': factory.getRandomString(),
        }
        response = self.client.post(reverse('networks_handler'), params)
        self.assertEqual(httplib.OK, response.status_code)
        network = Network.objects.get(name=params['name'])
        self.assertAttributes(network, params)

    def test_POST_requires_admin(self):
        name = factory.make_name('no-net')
        response = self.client.post(
            reverse('networks_handler'),
            {'name': name})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)
        self.assertIsNone(get_one(Network.objects.filter(name=name)))

    def test_GET_returns_networks(self):
        original_network = factory.make_network()

        response = self.client.get(reverse('networks_handler'))
        self.assertEqual(httplib.OK, response.status_code, response.content)

        parsed_result = json.loads(response.content)
        self.assertEqual(1, len(parsed_result))
        [returned_network] = parsed_result
        fields = {'name', 'ip', 'netmask', 'vlan_tag', 'description'}
        self.assertEqual(
            fields.union({'resource_uri'}),
            set(returned_network.keys()))
        expected_values = {
            field: getattr(original_network, field)
            for field in fields
            if field != 'resource_uri'
        }
        expected_values['resource_uri'] = reverse(
            'network_handler', args=[original_network.name])
        self.assertEqual(expected_values, returned_network)

    def test_GET_returns_empty_if_no_networks(self):
        response = self.client.get(reverse('networks_handler'))
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual([], json.loads(response.content))

    def test_GET_sorts_by_name(self):
        original_names = [factory.make_name('net').lower() for _ in range(3)]
        for name in original_names:
            factory.make_network(name=name)

        response = self.client.get(reverse('networks_handler'))
        self.assertEqual(httplib.OK, response.status_code, response.content)

        self.assertEqual(
            sorted(original_names),
            [network['name'] for network in json.loads(response.content)])
