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
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object


class TestNetwork(APITestCase):
    def get_url(self, name):
        """Return the URL for the network of the given name."""
        return reverse('network_handler', args=[name])

    def test_handler_path(self):
        name = factory.make_name('net')
        self.assertEqual('/api/1.0/networks/%s/' % name, self.get_url(name))

    def test_POST_is_prohibited(self):
        self.become_admin()
        network = factory.make_Network()
        response = self.client.post(
            self.get_url(network.name),
            {'description': "New description"})
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)

    def test_GET_returns_network(self):
        network = factory.make_Network()

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
                network.default_gateway,
            ),
            (
                parsed_result['name'],
                parsed_result['ip'],
                parsed_result['netmask'],
                parsed_result['vlan_tag'],
                parsed_result['description'],
                parsed_result['default_gateway'],
            ))

    def test_GET_returns_404_for_unknown_network(self):
        self.assertEqual(
            httplib.NOT_FOUND,
            self.client.get(self.get_url('nonesuch')).status_code)

    def test_PUT_updates_network(self):
        self.become_admin()
        network = factory.make_Network()
        new_net = factory.getRandomNetwork()
        new_values = {
            'name': factory.make_name('new'),
            'ip': '%s' % new_net.cidr.ip,
            'netmask': '%s' % new_net.netmask,
            'vlan_tag': factory.make_vlan_tag(),
            'description': "Changed description",
            'default_gateway': factory.getRandomIPAddress(),
            }

        response = self.client_put(self.get_url(network.name), new_values)
        self.assertEqual(httplib.OK, response.status_code)

        network = reload_object(network)
        self.assertAttributes(network, new_values)

    def test_PUT_requires_admin(self):
        description = "Original description"
        network = factory.make_Network(description=description)
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
        network = factory.make_Network()
        response = self.client.delete(self.get_url(network.name))
        self.assertEqual(httplib.NO_CONTENT, response.status_code)
        self.assertIsNone(reload_object(network))

    def test_DELETE_requires_admin(self):
        network = factory.make_Network()
        response = self.client.delete(self.get_url(network.name))
        self.assertEqual(httplib.FORBIDDEN, response.status_code)
        self.assertIsNotNone(reload_object(network))

    def test_DELETE_is_idempotent(self):
        name = factory.make_name('no-net')
        self.become_admin()
        response1 = self.client.delete(self.get_url(name))
        response2 = self.client.delete(self.get_url(name))
        self.assertEqual(response1.status_code, response2.status_code)

    def test_DELETE_works_with_MACs_attached(self):
        self.become_admin()
        network = factory.make_Network()
        mac = factory.make_MACAddress(networks=[network])
        response = self.client.delete(self.get_url(network.name))
        self.assertEqual(httplib.NO_CONTENT, response.status_code)
        self.assertIsNone(reload_object(network))
        mac = reload_object(mac)
        self.assertEqual([], list(mac.networks.all()))

    def test_POST_connect_macs_connects_macs_to_network(self):
        self.become_admin()
        network = factory.make_Network()
        macs = [factory.make_MACAddress(networks=[network]) for _ in range(2)]
        response = self.client.post(
            self.get_url(network.name),
            {
                'op': 'connect_macs',
                'macs': [mac.mac_address for mac in macs],
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual(set(macs), set(network.macaddress_set.all()))

    def test_POST_connect_macs_accepts_empty_macs_list(self):
        self.become_admin()
        network = factory.make_Network()
        response = self.client.post(
            self.get_url(network.name),
            {
                'op': 'connect_macs',
                'macs': [],
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual([], list(network.macaddress_set.all()))

    def test_POST_connect_macs_leaves_other_networks_unchanged(self):
        self.become_admin()
        network = factory.make_Network()
        other_network = factory.make_Network()
        mac = factory.make_MACAddress(networks=[other_network])
        response = self.client.post(
            self.get_url(network.name),
            {
                'op': 'connect_macs',
                'macs': [mac.mac_address],
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual({network, other_network}, set(mac.networks.all()))

    def test_POST_connect_macs_leaves_other_MACs_unchanged(self):
        self.become_admin()
        network = factory.make_Network()
        mac = factory.make_MACAddress(networks=[])
        other_mac = factory.make_MACAddress(networks=[network])
        response = self.client.post(
            self.get_url(network.name),
            {
                'op': 'connect_macs',
                'macs': [mac.mac_address],
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual({mac, other_mac}, set(network.macaddress_set.all()))

    def test_POST_connect_macs_ignores_MACs_already_on_network(self):
        self.become_admin()
        network = factory.make_Network()
        mac = factory.make_MACAddress(networks=[network])
        response = self.client.post(
            self.get_url(network.name),
            {
                'op': 'connect_macs',
                'macs': [mac.mac_address],
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual({mac}, set(network.macaddress_set.all()))

    def test_POST_connect_macs_requires_admin(self):
        network = factory.make_Network()
        response = self.client.post(
            self.get_url(network.name),
            {
                'op': 'connect_macs',
                'macs': [],
            })
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_POST_connect_macs_fails_on_unknown_MAC(self):
        self.become_admin()
        network = factory.make_Network()
        nonexistent_mac = factory.make_MAC()
        response = self.client.post(
            self.get_url(network.name),
            {
                'op': 'connect_macs',
                'macs': [nonexistent_mac],
            })
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual(
            {'macs': ["Unknown MAC address(es): %s." % nonexistent_mac]},
            json.loads(response.content))

    def test_POST_disconnect_macs_removes_MACs_from_network(self):
        self.become_admin()
        network = factory.make_Network()
        mac = factory.make_MACAddress(networks=[network])
        response = self.client.post(
            self.get_url(network.name),
            {
                'op': 'disconnect_macs',
                'macs': [mac.mac_address],
            })
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual([], list(mac.networks.all()))

    def test_POST_disconnect_macs_requires_admin(self):
        response = self.client.post(
            self.get_url(factory.make_Network().name),
            {
                'op': 'disconnect_macs',
                'macs': [factory.make_MACAddress().mac_address],
            })
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_POST_disconnect_macs_accepts_empty_MACs_list(self):
        self.become_admin()
        response = self.client.post(
            self.get_url(factory.make_Network().name),
            {
                'op': 'disconnect_macs',
                'macs': [],
            })
        self.assertEqual(httplib.OK, response.status_code)

    def test_POST_disconnect_macs_is_idempotent(self):
        self.become_admin()
        response = self.client.post(
            self.get_url(factory.make_Network().name),
            {
                'op': 'disconnect_macs',
                'macs': [factory.make_MACAddress().mac_address],
            })
        self.assertEqual(httplib.OK, response.status_code)

    def test_POST_disconnect_macs_leaves_other_MACs_unchanged(self):
        self.become_admin()
        network = factory.make_Network()
        other_mac = factory.make_MACAddress(networks=[network])
        response = self.client.post(
            self.get_url(network.name),
            {
                'op': 'disconnect_macs',
                'macs': [
                    factory.make_MACAddress(networks=[network]).mac_address
                    ],
            })
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual([network], list(other_mac.networks.all()))

    def test_POST_disconnect_macs_leaves_other_networks_unchanged(self):
        self.become_admin()
        network = factory.make_Network()
        other_network = factory.make_Network()
        mac = factory.make_MACAddress(networks=[network, other_network])
        response = self.client.post(
            self.get_url(network.name),
            {
                'op': 'disconnect_macs',
                'macs': [mac.mac_address],
            })
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual([other_network], list(mac.networks.all()))

    def test_POST_disconnect_macs_fails_on_unknown_mac(self):
        self.become_admin()
        nonexistent_mac = factory.make_MAC()
        response = self.client.post(
            self.get_url(factory.make_Network().name),
            {
                'op': 'disconnect_macs',
                'macs': [nonexistent_mac],
            })
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual(
            {'macs': ["Unknown MAC address(es): %s." % nonexistent_mac]},
            json.loads(response.content))


class TestListConnectedMACs(APITestCase):
    """Tests for /api/1.0/network/s<network>/?op=list_connected_macs."""

    def make_mac(self, networks=None, owner=None, node=None):
        """Create a MAC address.

        :param networks: Optional list of `Network` objects to connect the
            MAC to.  If omitted, the MAC will not be connected to any networks.
        :param node: Optional node that will have this MAC
            address.  If omitted, one will be created.
        :param owner: Optional owner for the node that will have this MAC
            address.  If omitted, one will be created.  The node will be in
            the "allocated" state.  This parameter is ignored if a node is
            provided.
        """
        if networks is None:
            networks = []
        if owner is None:
            owner = factory.make_user()
        if node is None:
            node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=owner)
        return factory.make_MACAddress(networks=networks, node=node)

    def request_connected_macs(self, network):
        """Request and return the MAC addresses attached to `network`."""
        url = reverse('network_handler', args=[network.name])
        response = self.client.get(url, {'op': 'list_connected_macs'})
        self.assertEqual(httplib.OK, response.status_code)
        return json.loads(response.content)

    def extract_macs(self, returned_macs):
        """Extract the textual MAC addresses from an API response."""
        return [item['mac_address'] for item in returned_macs]

    def test_returns_connected_macs(self):
        network = factory.make_Network()
        macs = [
            self.make_mac(networks=[network], owner=self.logged_in_user)
            for _ in range(3)
            ]
        self.assertEqual(
            {mac.mac_address for mac in macs},
            set(self.extract_macs(self.request_connected_macs(network))))

    def test_ignores_unconnected_macs(self):
        self.make_mac(
            networks=[factory.make_Network()], owner=self.logged_in_user)
        self.make_mac(networks=[], owner=self.logged_in_user)
        self.assertEqual(
            [],
            self.request_connected_macs(factory.make_Network()))

    def test_includes_MACs_for_nodes_visible_to_user(self):
        network = factory.make_Network()
        mac = self.make_mac(networks=[network], owner=self.logged_in_user)
        self.assertEqual(
            [mac.mac_address],
            self.extract_macs(self.request_connected_macs(network)))

    def test_excludes_MACs_for_nodes_not_visible_to_user(self):
        network = factory.make_Network()
        self.make_mac(networks=[network])
        self.assertEqual([], self.request_connected_macs(network))

    def test_returns_sorted_MACs(self):
        network = factory.make_Network()
        macs = [
            self.make_mac(
                networks=[network], node=factory.make_Node(sortable_name=True),
                owner=self.logged_in_user)
            for _ in range(4)
            ]
        # Create MACs connected to the same node.
        macs = macs + [
            self.make_mac(
                networks=[network], owner=self.logged_in_user,
                node=macs[0].node)
            for _ in range(3)
            ]
        sorted_macs = sorted(
            macs,
            key=lambda x: (x.node.hostname.lower(), x.mac_address.get_raw()))
        self.assertEqual(
            [mac.mac_address.get_raw() for mac in sorted_macs],
            self.extract_macs(self.request_connected_macs(network)))
