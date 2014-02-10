# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `Network` API."""

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
from maasserver.testing import reload_object
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory


class TestNetwork(APITestCase):
    def get_url(self, name):
        """Return the URL for the network of the given name."""
        return reverse('network_handler', args=[name])

    def test_handler_path(self):
        name = factory.make_name('net')
        self.assertEqual('/api/1.0/networks/%s/' % name, self.get_url(name))

    def test_GET_returns_network(self):
        network = factory.make_network()

        response = self.client.get(self.get_url(network.name))
        self.assertEqual(httplib.OK, response.status_code)

        parsed_result = json.loads(response.content)
        self.assertEqual(
            (
                network.name,
                network.ip,
                network.netmask,
                network.vlan_tag,
                network.description,
            ),
            (
                parsed_result['name'],
                parsed_result['ip'],
                parsed_result['netmask'],
                parsed_result['vlan_tag'],
                parsed_result['description'],
            ))

    def test_GET_returns_404_for_unknown_network(self):
        self.assertEqual(
            httplib.NOT_FOUND,
            self.client.get(self.get_url('nonesuch')).status_code)

    def test_DELETE_deletes_network(self):
        self.become_admin()
        network = factory.make_network()
        response = self.client.delete(self.get_url(network.name))
        self.assertEqual(httplib.NO_CONTENT, response.status_code)
        self.assertIsNone(reload_object(network))

    def test_DELETE_requires_admin(self):
        network = factory.make_network()
        response = self.client.delete(self.get_url(network.name))
        self.assertEqual(httplib.FORBIDDEN, response.status_code)
        self.assertIsNotNone(reload_object(network))

    def test_DELETE_is_idempotent(self):
        name = factory.make_name('no-net')
        self.become_admin()
        response1 = self.client.delete(self.get_url(name))
        response2 = self.client.delete(self.get_url(name))
        self.assertEqual(response1.status_code, response2.status_code)

    def test_DELETE_works_with_nodes_attached(self):
        self.become_admin()
        network = factory.make_network()
        factory.make_node(networks=[network])
        response = self.client.delete(self.get_url(network.name))
        self.assertEqual(httplib.NO_CONTENT, response.status_code)
        self.assertIsNone(reload_object(network))
