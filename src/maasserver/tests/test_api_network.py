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
from maasserver.enum import NODE_STATUS
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

    def test_POST_is_prohibited(self):
        self.become_admin()
        network = factory.make_network()
        response = self.client.post(
            self.get_url(network.name),
            {'description': "New description"})
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)

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

    def test_PUT_updates_network(self):
        self.become_admin()
        network = factory.make_network()
        new_net = factory.getRandomNetwork()
        new_values = {
            'name': factory.make_name('new'),
            'ip': '%s' % new_net.cidr.ip,
            'netmask': '%s' % new_net.netmask,
            'vlan_tag': factory.make_vlan_tag(),
            'description': "Changed description",
            }

        response = self.client_put(self.get_url(network.name), new_values)
        self.assertEqual(httplib.OK, response.status_code)

        network = reload_object(network)
        self.assertAttributes(network, new_values)

    def test_PUT_requires_admin(self):
        description = "Original description"
        network = factory.make_network(description=description)
        response = self.client_put(
            self.get_url(network.name), {'description': "Changed description"})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)
        self.assertEqual(description, reload_object(network).description)

    def test_PUT_returns_404_for_unknown_network(self):
        self.become_admin()
        self.assertEqual(
            httplib.NOT_FOUND,
            self.client_put(self.get_url('nonesuch')).status_code)

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

    def test_POST_connect_nodes_adds_nodes(self):
        self.become_admin()
        network = factory.make_network()
        nodes = [factory.make_node(networks=[]) for _ in range(2)]
        response = self.client.post(
            self.get_url(network.name),
            {
                'op': 'connect_nodes',
                'nodes': [node.system_id for node in nodes],
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual(set(nodes), set(network.node_set.all()))

    def test_POST_connect_nodes_accepts_empty_nodes_list(self):
        self.become_admin()
        network = factory.make_network()
        response = self.client.post(
            self.get_url(network.name),
            {
                'op': 'connect_nodes',
                'nodes': [],
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual([], list(network.node_set.all()))

    def test_POST_connect_nodes_leaves_other_networks_unchanged(self):
        self.become_admin()
        network = factory.make_network()
        other_network = factory.make_network()
        node = factory.make_node(networks=[other_network])
        response = self.client.post(
            self.get_url(network.name),
            {
                'op': 'connect_nodes',
                'nodes': [node.system_id],
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual({network, other_network}, set(node.networks.all()))

    def test_POST_connect_nodes_leaves_other_nodes_unchanged(self):
        self.become_admin()
        network = factory.make_network()
        node = factory.make_node(networks=[])
        other_node = factory.make_node(networks=[network])
        response = self.client.post(
            self.get_url(network.name),
            {
                'op': 'connect_nodes',
                'nodes': [node.system_id],
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual({node, other_node}, set(network.node_set.all()))

    def test_POST_connect_nodes_ignores_nodes_already_on_network(self):
        self.become_admin()
        network = factory.make_network()
        node = factory.make_node(networks=[network])
        response = self.client.post(
            self.get_url(network.name),
            {
                'op': 'connect_nodes',
                'nodes': [node.system_id],
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual({node}, set(network.node_set.all()))

    def test_POST_connect_nodes_requires_admin(self):
        network = factory.make_network()
        response = self.client.post(
            self.get_url(network.name),
            {
                'op': 'connect_nodes',
                'nodes': [],
            })
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_POST_connect_nodes_fails_on_unknown_node(self):
        self.become_admin()
        network = factory.make_network()
        nonexistent_node = factory.make_name('no-node')
        response = self.client.post(
            self.get_url(network.name),
            {
                'op': 'connect_nodes',
                'nodes': [nonexistent_node],
            })
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual(
            {'nodes': ["Unknown node(s): %s." % nonexistent_node]},
            json.loads(response.content))


class TestListConnectedNodes(APITestCase):
    """Tests for /api/1.0/network/s<network>/?op=list_connected_nodes."""

    def test_returns_connected_nodes(self):
        network = factory.make_network()
        visible_connected_nodes = [
            factory.make_node(networks=[network]) for i in range(5)]
        # Create another node, connected to the network but not visible
        # to the user.
        factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user(),
            networks=[network])
        # Create another node, not connected to any network.
        factory.make_node()

        url = reverse('network_handler', args=[network.name])
        response = self.client.get(url, {'op': 'list_connected_nodes'})

        self.assertEqual(httplib.OK, response.status_code)
        connected_nodes_system_ids = [
            node.system_id for node in visible_connected_nodes]
        self.assertItemsEqual(
            connected_nodes_system_ids,
            [node['system_id'] for node in json.loads(response.content)])
