# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for MAC-address management in the API."""

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
from maasserver.models import MACAddress
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory


class MACAddressAPITest(APITestCase):

    def test_macs_handler_path(self):
        self.assertEqual(
            '/api/1.0/nodes/node-id/macs/',
            reverse('node_macs_handler', args=['node-id']))

    def test_mac_handler_path(self):
        self.assertEqual(
            '/api/1.0/nodes/node-id/macs/mac/',
            reverse('node_mac_handler', args=['node-id', 'mac']))

    def createNodeWithMacs(self, owner=None):
        node = factory.make_node(owner=owner)
        mac1 = node.add_mac_address('aa:bb:cc:dd:ee:ff')
        mac2 = node.add_mac_address('22:bb:cc:dd:aa:ff')
        return node, mac1, mac2

    def test_macs_GET(self):
        # The api allows for fetching the list of the MAC address for a node.
        node, mac1, mac2 = self.createNodeWithMacs()
        response = self.client.get(
            reverse('node_macs_handler', args=[node.system_id]))
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(2, len(parsed_result))
        self.assertEqual(mac1.mac_address, parsed_result[0]['mac_address'])
        self.assertEqual(mac2.mac_address, parsed_result[1]['mac_address'])

    def test_macs_GET_not_found(self):
        # When fetching MAC addresses, the api returns a 'Not Found' (404)
        # error if no node is found.
        url = reverse('node_macs_handler', args=['invalid-id'])
        response = self.client.get(url)

        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_macs_GET_node_not_found(self):
        # When fetching a MAC address, the api returns a 'Not Found' (404)
        # error if the MAC address does not exist.
        node = factory.make_node()
        response = self.client.get(
            reverse(
                'node_mac_handler',
                args=[node.system_id, '00-aa-22-cc-44-dd']))

        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_macs_GET_node_bad_request(self):
        # When fetching a MAC address, the api returns a 'Bad Request' (400)
        # error if the MAC address is not valid.
        node = factory.make_node()
        url = reverse('node_mac_handler', args=[node.system_id, 'invalid-mac'])
        response = self.client.get(url)

        self.assertEqual(400, response.status_code)

    def test_macs_POST_add_mac(self):
        # The api allows to add a MAC address to an existing node.
        node = factory.make_node(owner=self.logged_in_user)
        nb_macs = MACAddress.objects.filter(node=node).count()
        response = self.client.post(
            reverse('node_macs_handler', args=[node.system_id]),
            {'mac_address': '01:BB:CC:DD:EE:FF'})
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual('01:BB:CC:DD:EE:FF', parsed_result['mac_address'])
        self.assertEqual(
            nb_macs + 1,
            MACAddress.objects.filter(node=node).count())

    def test_macs_POST_add_mac_without_edit_perm(self):
        # Adding a MAC address to a node requires the NODE_PERMISSION.EDIT
        # permission.
        node = factory.make_node()
        response = self.client.post(
            reverse('node_macs_handler', args=[node.system_id]),
            {'mac_address': '01:BB:CC:DD:EE:FF'})

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_macs_POST_add_mac_invalid(self):
        # A 'Bad Request' response is returned if one tries to add an invalid
        # MAC address to a node.
        node = self.createNodeWithMacs(self.logged_in_user)[0]
        response = self.client.post(
            reverse('node_macs_handler', args=[node.system_id]),
            {'mac_address': 'invalid-mac'})
        parsed_result = json.loads(response.content)

        self.assertEqual(400, response.status_code)
        self.assertEqual(['mac_address'], list(parsed_result))
        self.assertEqual(
            ["Enter a valid MAC address (e.g. AA:BB:CC:DD:EE:FF)."],
            parsed_result['mac_address'])

    def test_macs_DELETE_mac(self):
        # The api allows to delete a MAC address.
        node, mac1, mac2 = self.createNodeWithMacs(self.logged_in_user)
        nb_macs = node.macaddress_set.count()
        response = self.client.delete(
            reverse(
                'node_mac_handler',
                args=[node.system_id, mac1.mac_address]))

        self.assertEqual(204, response.status_code)
        self.assertEqual(
            nb_macs - 1,
            node.macaddress_set.count())

    def test_macs_DELETE_mac_forbidden(self):
        # When deleting a MAC address, the api returns a 'Forbidden' (403)
        # error if the node is not visible to the logged-in user.
        node, mac1, _ = self.createNodeWithMacs()
        factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        response = self.client.delete(
            reverse(
                'node_mac_handler',
                args=[node.system_id, mac1.mac_address]))

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_macs_DELETE_not_found(self):
        # When deleting a MAC address, the api returns a 'Not Found' (404)
        # error if no existing MAC address is found.
        node = factory.make_node(owner=self.logged_in_user)
        response = self.client.delete(
            reverse(
                'node_mac_handler',
                args=[node.system_id, '00-aa-22-cc-44-dd']))

        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_macs_DELETE_forbidden(self):
        # When deleting a MAC address, the api returns a 'Forbidden'
        # (403) error if the user does not have the 'edit' permission on the
        # node.
        node = factory.make_node(owner=self.logged_in_user)
        response = self.client.delete(
            reverse(
                'node_mac_handler',
                args=[node.system_id, '00-aa-22-cc-44-dd']))

        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_macs_DELETE_bad_request(self):
        # When deleting a MAC address, the api returns a 'Bad Request' (400)
        # error if the provided MAC address is not valid.
        node = factory.make_node()
        response = self.client.delete(
            reverse(
                'node_mac_handler',
                args=[node.system_id, 'invalid-mac']))

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
