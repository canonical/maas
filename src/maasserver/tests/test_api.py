# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    print_function,
    unicode_literals,
    )

"""Test maasserver API."""

__metaclass__ = type
__all__ = []

import json

from maas.testing import TestCase
from maasserver.models import (
    MACAddress,
    Node,
    )
from maasserver.testing.factory import factory


class NodeAPITest(TestCase):

    def test_nodes_GET(self):
        """
        The api allows for fetching the list of Nodes.

        """
        node1 = factory.make_node(set_hostname=True)
        node2 = factory.make_node(set_hostname=True)
        response = self.client.get('/api/nodes/')
        parsed_result = json.loads(response.content)

        self.assertEqual(200, response.status_code)
        expected = [
            {u'macaddress_set': [], "system_id": node1.system_id,
                "hostname": node1.hostname},
            {u'macaddress_set': [], "system_id": node2.system_id,
                "hostname": node2.hostname},
            ]
        self.assertEqual(expected, parsed_result)

    def test_node_GET(self):
        """
        The api allows for fetching a single Node (using system_id).

        """
        node = factory.make_node(set_hostname=True)
        response = self.client.get('/api/nodes/%s/' % node.system_id)
        parsed_result = json.loads(response.content)

        self.assertEqual(200, response.status_code)
        self.assertEqual(node.hostname, parsed_result['hostname'])
        self.assertEqual(node.system_id, parsed_result['system_id'])

    def test_node_GET_404(self):
        """
        When fetching a Node, the api returns a 'Not Found' (404) error
        if no node is found.

        """
        response = self.client.get('/api/nodes/invalid-uuid/')

        self.assertEqual(404, response.status_code)

    def test_nodes_POST(self):
        """
        The api allows to create a Node.

        """
        response = self.client.post(
            '/api/nodes/', {'hostname': 'diane'})
        parsed_result = json.loads(response.content)

        self.assertEqual(200, response.status_code)
        self.assertEqual('diane', parsed_result['hostname'])
        self.assertEqual(1, Node.objects.filter(hostname='diane').count())

    def test_node_PUT(self):
        """
        The api allows to update a Node.

        """
        node = factory.make_node(hostname='diane')
        response = self.client.put(
            '/api/nodes/%s/' % node.system_id, {'hostname': 'francis'})
        parsed_result = json.loads(response.content)

        self.assertEqual(200, response.status_code)
        self.assertEqual('francis', parsed_result['hostname'])
        self.assertEqual(0, Node.objects.filter(hostname='diane').count())
        self.assertEqual(1, Node.objects.filter(hostname='francis').count())

    def test_node_PUT_404(self):
        """
        When updating a Node, the api returns a 'Not Found' (404) error
        if no node is found.

        """
        response = self.client.put('/api/nodes/no-node-here/')

        self.assertEqual(404, response.status_code)

    def test_nodes_POST_set_status_invalid(self):
        """
        The status of a newly created Node cannot be set (if will default to
        'NEW').

        """
        response = self.client.post(
            '/api/nodes/', {'status': 'new'})

        self.assertEqual(400, response.status_code)
        self.assertEqual(
            'Bad Request: Cannot set the status for a node.', response.content)

    def test_node_DELETE(self):
        """
        The api allows to delete a Node.

        """
        node = factory.make_node(set_hostname=True)
        system_id = node.system_id
        response = self.client.delete('/api/nodes/%s/' % node.system_id)

        self.assertEqual(204, response.status_code)
        self.assertEqual(
            [], list(Node.objects.filter(system_id=system_id)))

    def test_node_DELETE_404(self):
        """
        When deleting a Node, the api returns a 'Not Found' (404) error
        if no node is found.

        """
        response = self.client.delete('/api/nodes/no-node-here/')

        self.assertEqual(404, response.status_code)


class MACAddressAPITest(TestCase):

    def setUp(self):
        super(MACAddressAPITest, self).setUp()
        self.node = factory.make_node()
        self.mac1 = self.node.add_mac_address('aa:bb:cc:dd:ee:ff')
        self.mac2 = self.node.add_mac_address('22:bb:cc:dd:aa:ff')

    def test_macs_GET(self):
        """
        The api allows for fetching the list of the MAC Addresss for a node.

        """
        response = self.client.get('/api/nodes/%s/macs/' % self.node.system_id)
        parsed_result = json.loads(response.content)

        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(parsed_result))
        self.assertEqual(
            self.mac1.mac_address, parsed_result[0]['mac_address'])
        self.assertEqual(
            self.mac2.mac_address, parsed_result[1]['mac_address'])

    def test_macs_GET_404(self):
        """
        When fetching MAC Addresses, the api returns a 'Not Found' (404)
        error if no node is found.

        """
        response = self.client.get('/api/nodes/invalid-id/macs/')

        self.assertEqual(404, response.status_code)

    def test_macs_GET_node_404(self):
        """
        When fetching a MAC Address, the api returns a 'Not Found' (404)
        error if the MAC Address does not exist.

        """
        response = self.client.get(
            '/api/nodes/%s/macs/00-aa-22-cc-44-dd/' % self.node.system_id)

        self.assertEqual(404, response.status_code)

    def test_macs_GET_node_400(self):
        """
        When fetching a MAC Address, the api returns a 'Bad Request' (400)
        error if the MAC Address is not valid.

        """
        response = self.client.get(
            '/api/nodes/%s/macs/invalid-mac/' % self.node.system_id)

        self.assertEqual(400, response.status_code)

    def test_macs_POST_add_mac(self):
        """
        The api allows to add a MAC Address to an existing node.

        """
        nb_macs = MACAddress.objects.filter(node=self.node).count()
        response = self.client.post(
            '/api/nodes/%s/macs/' % self.node.system_id,
            {'mac_address': 'AA:BB:CC:DD:EE:FF'})
        parsed_result = json.loads(response.content)

        self.assertEqual(200, response.status_code)
        self.assertEqual('AA:BB:CC:DD:EE:FF', parsed_result['mac_address'])
        self.assertEqual(
            nb_macs + 1,
            MACAddress.objects.filter(node=self.node).count())

    def test_macs_POST_add_mac_invalid(self):
        """
        A 'Bad Request' response is returned if one tries to add an invalid
        MAC Address to a node.

        """
        response = self.client.post(
            '/api/nodes/%s/macs/' % self.node.system_id,
            {'mac_address': 'invalid-mac'})

        self.assertEqual(400, response.status_code)
        self.assertEqual(
            'Bad Request: Invalid input: mac_address: Enter a valid MAC '
            'address (e.g. AA:BB:CC:DD:EE:FF).', response.content)

    def test_macs_DELETE_mac(self):
        """
        The api allows to delete a MAC Address.

        """
        nb_macs = self.node.macaddress_set.count()
        response = self.client.delete(
            '/api/nodes/%s/macs/%s/' % (
                self.node.system_id, self.mac1.mac_address))

        self.assertEqual(204, response.status_code)
        self.assertEqual(
            nb_macs - 1,
            self.node.macaddress_set.count())

    def test_macs_DELETE_404(self):
        """
        When deleting a MAC Address, the api returns a 'Not Found' (404)
        error if no existing MAC Address is found.

        """
        response = self.client.delete(
            '/api/nodes/%s/macs/%s/' % (
                self.node.system_id, '00-aa-22-cc-44-dd'))

        self.assertEqual(404, response.status_code)

    def test_macs_DELETE_400(self):
        """
        When deleting a MAC Address, the api returns a 'Bad Request' (400)
        error if the provided MAC Address is not valid.

        """
        response = self.client.delete(
            '/api/nodes/%s/macs/%s/' % (
                self.node.system_id, 'invalid-mac'))

        self.assertEqual(400, response.status_code)
