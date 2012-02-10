# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver API."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import httplib
import json
import time

from django.test.client import Client
from maasserver.models import (
    MACAddress,
    Node,
    NODE_STATUS,
    )
from maasserver.testing import (
    LoggedInTestCase,
    TestCase,
    )
from maasserver.testing.factory import factory
from oauth.oauth import (
    generate_nonce,
    OAuthConsumer,
    OAuthRequest,
    OAuthSignatureMethod_PLAINTEXT,
    OAuthToken,
    )


class NodeAnonAPITest(TestCase):

    def test_anon_nodes_GET(self):
        # Anonymous requests to the API are denied.
        response = self.client.get('/api/nodes/')

        self.assertEqual(httplib.UNAUTHORIZED, response.status_code)

    def test_anon_api_doc(self):
        # The documentation is accessible to anon users.
        response = self.client.get('/api/doc/')

        self.assertEqual(httplib.OK, response.status_code)


class OAuthAuthenticatedClient(Client):
    def __init__(self, user):
        super(OAuthAuthenticatedClient, self).__init__()
        consumer = user.get_profile().get_authorisation_consumer()
        token = user.get_profile().get_authorisation_token()
        self.consumer = OAuthConsumer(str(consumer.key), str(consumer.secret))
        self.token = OAuthToken(str(token.key), str(token.secret))

    def get_extra(self, path):
        params = {
            'oauth_version': "1.0",
            'oauth_nonce': generate_nonce(),
            'oauth_timestamp': int(time.time()),
            'oauth_token': self.token.key,
            'oauth_consumer_key': self.consumer.key,
        }
        req = OAuthRequest(http_url=path, parameters=params)
        req.sign_request(
            OAuthSignatureMethod_PLAINTEXT(), self.consumer, self.token)
        return req.to_header()

    def request(self, **kwargs):
        # Get test url.
        environ = self._base_environ()
        url = '%s://%s' % (environ['wsgi.url_scheme'], kwargs['PATH_INFO'])
        # Add OAuth authorization information to the request.
        extra = self.get_extra(url)
        # Django uses the 'HTTP_AUTHORIZATION' to look up Authorization
        # credentials.
        extra['HTTP_AUTHORIZATION'] = extra['Authorization']
        kwargs.update(extra)

        return super(OAuthAuthenticatedClient, self).request(**kwargs)


class APITestCase(TestCase):
    """Extension to `TestCase`: log in first.

    :ivar logged_in_user: A user who is currently logged in and can access
        the API.
    :ivar client: Authenticated API client (unsurprisingly, logged in as
        `logged_in_user`).
    """

    def setUp(self):
        super(APITestCase, self).setUp()
        self.logged_in_user = factory.make_user(
            username='test', password='test')
        self.client = OAuthAuthenticatedClient(self.logged_in_user)


def extract_system_ids(parsed_result):
    """List the system_ids of the nodes in `parsed_result`."""
    return [node.get('system_id') for node in parsed_result]


class NodeAPILoggedInTest(LoggedInTestCase):

    def test_nodes_GET_logged_in(self):
        # A (Django) logged-in user can access the API.
        node = factory.make_node()
        response = self.client.get('/api/nodes/', {'op': 'list'})
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual([node.system_id], extract_system_ids(parsed_result))


class TestNodeAPI(APITestCase):
    """Tests for /api/nodes/<node>/."""

    def test_GET_returns_node(self):
        # The api allows for fetching a single Node (using system_id).
        node = factory.make_node(set_hostname=True)
        response = self.client.get('/api/nodes/%s/' % node.system_id)
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(node.hostname, parsed_result['hostname'])
        self.assertEqual(node.system_id, parsed_result['system_id'])

    def test_GET_refuses_to_access_invisible_node(self):
        # The request to fetch a single node is denied if the node isn't
        # visible by the user.
        other_node = factory.make_node(
            status=NODE_STATUS.DEPLOYED, owner=factory.make_user())

        response = self.client.get('/api/nodes/%s/' % other_node.system_id)

        self.assertEqual(httplib.UNAUTHORIZED, response.status_code)

    def test_GET_refuses_to_access_nonexistent_node(self):
        # When fetching a Node, the api returns a 'Not Found' (404) error
        # if no node is found.
        response = self.client.get('/api/nodes/invalid-uuid/')

        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_PUT_updates_node(self):
        # The api allows to update a Node.
        node = factory.make_node(hostname='diane')
        response = self.client.put(
            '/api/nodes/%s/' % node.system_id, {'hostname': 'francis'})
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual('francis', parsed_result['hostname'])
        self.assertEqual(0, Node.objects.filter(hostname='diane').count())
        self.assertEqual(1, Node.objects.filter(hostname='francis').count())

    def test_resource_uri_points_back_at_node(self):
        # When a Node is returned by the API, the field 'resource_uri'
        # provides the URI for this Node.
        node = factory.make_node(hostname='diane')
        response = self.client.put(
            '/api/nodes/%s/' % node.system_id, {'hostname': 'francis'})
        parsed_result = json.loads(response.content)

        self.assertEqual(
            '/api/nodes/%s/' % (parsed_result['system_id']),
            parsed_result['resource_uri'])

    def test_PUT_rejects_invalid_data(self):
        # If the data provided to update a node is invalid, a 'Bad request'
        # response is returned.
        node = factory.make_node(hostname='diane')
        response = self.client.put(
            '/api/nodes/%s/' % node.system_id,
            {'hostname': 'too long' * 100})

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)

    def test_PUT_refuses_to_update_invisible_node(self):
        # The request to update a single node is denied if the node isn't
        # visible by the user.
        other_node = factory.make_node(
            status=NODE_STATUS.DEPLOYED, owner=factory.make_user())

        response = self.client.put('/api/nodes/%s/' % other_node.system_id)

        self.assertEqual(httplib.UNAUTHORIZED, response.status_code)

    def test_PUT_refuses_to_update_nonexistent_node(self):
        # When updating a Node, the api returns a 'Not Found' (404) error
        # if no node is found.
        response = self.client.put('/api/nodes/no-node-here/')

        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_DELETE_deletes_node(self):
        # The api allows to delete a Node.
        node = factory.make_node(set_hostname=True)
        system_id = node.system_id
        response = self.client.delete('/api/nodes/%s/' % node.system_id)

        self.assertEqual(204, response.status_code)
        self.assertEqual(
            [], list(Node.objects.filter(system_id=system_id)))

    def test_DELETE_refuses_to_delete_invisible_node(self):
        # The request to delete a single node is denied if the node isn't
        # visible by the user.
        other_node = factory.make_node(
            status=NODE_STATUS.DEPLOYED, owner=factory.make_user())

        response = self.client.delete('/api/nodes/%s/' % other_node.system_id)

        self.assertEqual(httplib.UNAUTHORIZED, response.status_code)

    def test_DELETE_refuses_to_delete_nonexistent_node(self):
        # When deleting a Node, the api returns a 'Not Found' (404) error
        # if no node is found.
        response = self.client.delete('/api/nodes/no-node-here/')

        self.assertEqual(httplib.NOT_FOUND, response.status_code)


class TestNodesAPI(APITestCase):
    """Tests for /api/nodes/."""

    def test_GET_list_lists_nodes(self):
        # The api allows for fetching the list of Nodes.
        node1 = factory.make_node()
        node2 = factory.make_node(
            set_hostname=True, status=NODE_STATUS.DEPLOYED,
            owner=self.logged_in_user)
        response = self.client.get('/api/nodes/', {'op': 'list'})
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        self.assertItemsEqual(
            [node1.system_id, node2.system_id],
            extract_system_ids(parsed_result))

    def test_GET_list_without_nodes_returns_empty_list(self):
        # If there are no nodes to list, the "list" op still works but
        # returns an empty list.
        response = self.client.get('/api/nodes/', {'op': 'list'})
        self.assertItemsEqual([], json.loads(response.content))

    def test_GET_list_orders_by_id(self):
        # Nodes are returned in id order.
        nodes = [factory.make_node() for counter in range(3)]
        response = self.client.get('/api/nodes/', {'op': 'list'})
        parsed_result = json.loads(response.content)
        self.assertSequenceEqual(
            [node.system_id for node in nodes],
            extract_system_ids(parsed_result))

    def test_GET_list_with_id_returns_matching_nodes(self):
        # The "list" operation takes optional "id" parameters.  Only
        # nodes with matching ids will be returned.
        ids = [factory.make_node().system_id for counter in range(3)]
        matching_id = ids[0]
        response = self.client.get('/api/nodes/', {
            'op': 'list',
            'id': [matching_id],
        })
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [matching_id], extract_system_ids(parsed_result))

    def test_GET_list_with_nonexistent_id_returns_empty_list(self):
        # Trying to list a nonexistent node id returns a list containing
        # no nodes -- even if other (non-matching) nodes exist.
        existing_id = factory.make_node().system_id
        nonexistent_id = existing_id + factory.getRandomString()
        response = self.client.get('/api/nodes/', {
            'op': 'list',
            'id': [nonexistent_id],
        })
        self.assertItemsEqual([], json.loads(response.content))

    def test_GET_list_with_ids_orders_by_id(self):
        # Even when ids are passed to "list," nodes are returned in id
        # order, not necessarily in the order of the id arguments.
        ids = [factory.make_node().system_id for counter in range(3)]
        response = self.client.get('/api/nodes/', {
            'op': 'list',
            'id': list(reversed(ids)),
        })
        parsed_result = json.loads(response.content)
        self.assertSequenceEqual(ids, extract_system_ids(parsed_result))

    def test_GET_list_with_some_matching_ids_returns_matching_nodes(self):
        # If some nodes match the requested ids and some don't, only the
        # matching ones are returned.
        existing_id = factory.make_node().system_id
        nonexistent_id = existing_id + factory.getRandomString()
        response = self.client.get('/api/nodes/', {
            'op': 'list',
            'id': [existing_id, nonexistent_id],
        })
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [existing_id], extract_system_ids(parsed_result))

    def test_POST_new_creates_node(self):
        # The API allows a Node to be created and associated with MAC
        # Addresses.
        response = self.client.post(
            '/api/nodes/',
            {
                'op': 'new',
                'hostname': 'diane',
                'after_commissioning_action': '2',
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', '22:bb:cc:dd:ee:ff'],
            })
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        self.assertIn('application/json', response['Content-Type'])
        self.assertEqual('diane', parsed_result['hostname'])
        self.assertNotEqual(0, len(parsed_result.get('system_id')))
        [diane] = Node.objects.filter(hostname='diane')
        self.assertEqual(2, diane.after_commissioning_action)
        self.assertItemsEqual(
            ['aa:bb:cc:dd:ee:ff', '22:bb:cc:dd:ee:ff'],
            [mac.mac_address for mac in diane.macaddress_set.all()])

    def test_POST_fails_without_operation(self):
        # If there is no operation ('op=operation_name') specified in the
        # request data, a 'Bad request' response is returned.
        response = self.client.post(
            '/api/nodes/',
            {
                'hostname': 'diane',
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', 'invalid'],
            })

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertIn('text/html', response['Content-Type'])
        self.assertEqual("Unknown operation.", response.content)

    def test_POST_fails_with_bad_operation(self):
        # If the operation ('op=operation_name') specified in the
        # request data is unknown, a 'Bad request' response is returned.
        response = self.client.post(
            '/api/nodes/',
            {
                'op': 'invalid_operation',
                'hostname': 'diane',
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', 'invalid'],
            })

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual(
            "Unknown operation: 'invalid_operation'.", response.content)

    def test_POST_new_rejects_invalid_data(self):
        # If the data provided to create a node with an invalid MAC
        # Address, a 'Bad request' response is returned.
        response = self.client.post(
            '/api/nodes/',
            {
                'op': 'new',
                'hostname': 'diane',
                'mac_addresses': ['aa:bb:cc:dd:ee:ff', 'invalid'],
            })
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertIn('application/json', response['Content-Type'])
        self.assertItemsEqual(['mac_addresses'], parsed_result)
        self.assertEqual(
            ["One or more MAC Addresses is invalid."],
            parsed_result['mac_addresses'])


class MACAddressAPITest(APITestCase):

    def setUp(self):
        super(MACAddressAPITest, self).setUp()
        self.node = factory.make_node()
        self.mac1 = self.node.add_mac_address('aa:bb:cc:dd:ee:ff')
        self.mac2 = self.node.add_mac_address('22:bb:cc:dd:aa:ff')

    def test_macs_GET(self):
        # The api allows for fetching the list of the MAC Addresss for a node.
        response = self.client.get('/api/nodes/%s/macs/' % self.node.system_id)
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(2, len(parsed_result))
        self.assertEqual(
            self.mac1.mac_address, parsed_result[0]['mac_address'])
        self.assertEqual(
            self.mac2.mac_address, parsed_result[1]['mac_address'])

    def test_macs_GET_forbidden(self):
        # When fetching MAC Addresses, the api returns a 'Unauthorized' (401)
        # error if the node is not visible to the logged-in user.
        other_node = factory.make_node(
            status=NODE_STATUS.DEPLOYED, owner=factory.make_user())
        response = self.client.get(
            '/api/nodes/%s/macs/' % other_node.system_id)

        self.assertEqual(httplib.UNAUTHORIZED, response.status_code)

    def test_macs_GET_not_found(self):
        # When fetching MAC Addresses, the api returns a 'Not Found' (404)
        # error if no node is found.
        response = self.client.get('/api/nodes/invalid-id/macs/')

        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_macs_GET_node_not_found(self):
        # When fetching a MAC Address, the api returns a 'Not Found' (404)
        # error if the MAC Address does not exist.
        response = self.client.get(
            '/api/nodes/%s/macs/00-aa-22-cc-44-dd/' % self.node.system_id)

        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_macs_GET_node_forbidden(self):
        # When fetching a MAC Address, the api returns a 'Unauthorized' (401)
        # error if the node is not visible to the logged-in user.
        other_node = factory.make_node(
            status=NODE_STATUS.DEPLOYED, owner=factory.make_user())
        response = self.client.get(
            '/api/nodes/%s/macs/0-aa-22-cc-44-dd/' % other_node.system_id)

        self.assertEqual(httplib.UNAUTHORIZED, response.status_code)

    def test_macs_GET_node_bad_request(self):
        # When fetching a MAC Address, the api returns a 'Bad Request' (400)
        # error if the MAC Address is not valid.
        response = self.client.get(
            '/api/nodes/%s/macs/invalid-mac/' % self.node.system_id)

        self.assertEqual(400, response.status_code)

    def test_macs_POST_add_mac(self):
        # The api allows to add a MAC Address to an existing node.
        nb_macs = MACAddress.objects.filter(node=self.node).count()
        response = self.client.post(
            '/api/nodes/%s/macs/' % self.node.system_id,
            {'mac_address': 'AA:BB:CC:DD:EE:FF'})
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual('AA:BB:CC:DD:EE:FF', parsed_result['mac_address'])
        self.assertEqual(
            nb_macs + 1,
            MACAddress.objects.filter(node=self.node).count())

    def test_macs_POST_add_mac_invalid(self):
        # A 'Bad Request' response is returned if one tries to add an invalid
        # MAC Address to a node.
        response = self.client.post(
            '/api/nodes/%s/macs/' % self.node.system_id,
            {'mac_address': 'invalid-mac'})
        parsed_result = json.loads(response.content)

        self.assertEqual(400, response.status_code)
        self.assertEqual(['mac_address'], list(parsed_result))
        self.assertEqual(
            ["Enter a valid MAC address (e.g. AA:BB:CC:DD:EE:FF)."],
            parsed_result['mac_address'])

    def test_macs_DELETE_mac(self):
        # The api allows to delete a MAC Address.
        nb_macs = self.node.macaddress_set.count()
        response = self.client.delete(
            '/api/nodes/%s/macs/%s/' % (
                self.node.system_id, self.mac1.mac_address))

        self.assertEqual(204, response.status_code)
        self.assertEqual(
            nb_macs - 1,
            self.node.macaddress_set.count())

    def test_macs_DELETE_mac_forbidden(self):
        # When deleting a MAC Address, the api returns a 'Unauthorized' (401)
        # error if the node is not visible to the logged-in user.
        other_node = factory.make_node(
            status=NODE_STATUS.DEPLOYED, owner=factory.make_user())
        response = self.client.delete(
            '/api/nodes/%s/macs/%s/' % (
                other_node.system_id, self.mac1.mac_address))

        self.assertEqual(httplib.UNAUTHORIZED, response.status_code)

    def test_macs_DELETE_not_found(self):
        # When deleting a MAC Address, the api returns a 'Not Found' (404)
        # error if no existing MAC Address is found.
        response = self.client.delete(
            '/api/nodes/%s/macs/%s/' % (
                self.node.system_id, '00-aa-22-cc-44-dd'))

        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_macs_DELETE_bad_request(self):
        # When deleting a MAC Address, the api returns a 'Bad Request' (400)
        # error if the provided MAC Address is not valid.
        response = self.client.delete(
            '/api/nodes/%s/macs/%s/' % (
                self.node.system_id, 'invalid-mac'))

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
