# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Node API."""

__all__ = []

import http.client

import bson
from django.conf import settings
from django.core.urlresolvers import reverse
from maasserver.enum import (
    NODE_STATUS,
    POWER_STATE,
)
from maasserver.models import (
    Node,
    node as node_module,
)
from maasserver.testing.api import APITestCase
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.oauthclient import OAuthAuthenticatedClient
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import json_load_bytes
from metadataserver.models import NodeKey
from metadataserver.nodeinituser import get_node_init_user
from mock import Mock
from provisioningserver.refresh.node_info_scripts import (
    LLDP_OUTPUT_NAME,
    LSHW_OUTPUT_NAME,
)


class NodeAnonAPITest(MAASServerTestCase):

    def test_node_init_user_cannot_access(self):
        token = NodeKey.objects.get_token_for_node(factory.make_Node())
        client = OAuthAuthenticatedClient(get_node_init_user(), token)
        response = client.get(reverse('nodes_handler'))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)


class NodesAPILoggedInTest(MAASServerTestCase):

    def setUp(self):
        super(NodesAPILoggedInTest, self).setUp()
        self.patch(node_module, 'wait_for_power_command')

    def test_nodes_GET_logged_in(self):
        # A (Django) logged-in user can access the API.
        self.client_log_in()
        node = factory.make_Node()
        response = self.client.get(reverse('nodes_handler'))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            [node.system_id],
            [parsed_node.get('system_id') for parsed_node in parsed_result])


class TestNodeAPI(APITestCase):
    """Tests for /api/2.0/nodes/<node>/."""

    def test_handler_path(self):
        self.assertEqual(
            '/api/2.0/nodes/node-name/',
            reverse('node_handler', args=['node-name']))

    @staticmethod
    def get_node_uri(node):
        """Get the API URI for `node`."""
        return reverse('node_handler', args=[node.system_id])

    def test_GET_refuses_to_access_nonexistent_node(self):
        # When fetching a Node, the api returns a 'Not Found' (404) error
        # if no node is found.
        url = reverse('node_handler', args=['invalid-uuid'])

        response = self.client.get(url)

        self.assertEqual(http.client.NOT_FOUND, response.status_code)
        self.assertEqual(
            "Not Found", response.content.decode(settings.DEFAULT_CHARSET))

    def test_GET_returns_404_if_node_name_contains_invalid_characters(self):
        # When the requested name contains characters that are invalid for
        # a hostname, the result of the request is a 404 response.
        url = reverse('node_handler', args=['invalid-uuid-#...'])

        response = self.client.get(url)

        self.assertEqual(http.client.NOT_FOUND, response.status_code)
        self.assertEqual(
            "Not Found", response.content.decode(settings.DEFAULT_CHARSET))

    def test_resource_uri_points_back_at_machine(self):
        self.become_admin()
        # When a Machine is returned by the API, the field 'resource_uri'
        # provides the URI for this Machine.
        machine = factory.make_Node(
            hostname='diane', owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        response = self.client.get(self.get_node_uri(machine))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            reverse('machine_handler', args=[parsed_result['system_id']]),
            parsed_result['resource_uri'])

    def test_resource_uri_points_back_at_device(self):
        self.become_admin()
        # When a Device is returned by the API, the field 'resource_uri'
        # provides the URI for this Device.
        device = factory.make_Device(
            hostname='diane', owner=self.logged_in_user)
        response = self.client.get(self.get_node_uri(device))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            reverse('device_handler', args=[parsed_result['system_id']]),
            parsed_result['resource_uri'])

    def test_resource_uri_points_back_at_rack_controller(self):
        self.become_admin()
        # When a Device is returned by the API, the field 'resource_uri'
        # provides the URI for this Device.
        rack = factory.make_RackController(
            hostname='diane', owner=self.logged_in_user)
        response = self.client.get(self.get_node_uri(rack))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            reverse(
                'rackcontroller_handler',
                args=[parsed_result['system_id']]),
            parsed_result['resource_uri'])

    def test_DELETE_deletes_node(self):
        # The api allows to delete a Node.
        self.become_admin()
        node = factory.make_Node(owner=self.logged_in_user)
        system_id = node.system_id
        response = self.client.delete(self.get_node_uri(node))

        self.assertEqual(204, response.status_code)
        self.assertItemsEqual([], Node.objects.filter(system_id=system_id))

    def test_DELETE_deletes_node_fails_if_not_admin(self):
        # Only superusers can delete nodes.
        node = factory.make_Node(owner=self.logged_in_user)
        response = self.client.delete(self.get_node_uri(node))

        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_DELETE_forbidden_without_edit_permission(self):
        # A user without the edit permission cannot delete a Node.
        node = factory.make_Node()
        response = self.client.delete(self.get_node_uri(node))

        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_DELETE_refuses_to_delete_invisible_node(self):
        # The request to delete a single node is denied if the node isn't
        # visible by the user.
        other_node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())

        response = self.client.delete(self.get_node_uri(other_node))

        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_DELETE_refuses_to_delete_nonexistent_node(self):
        # When deleting a Node, the api returns a 'Not Found' (404) error
        # if no node is found.
        url = reverse('node_handler', args=['invalid-uuid'])
        response = self.client.delete(url)

        self.assertEqual(http.client.NOT_FOUND, response.status_code)

    def test_CREATE_disabled(self):
        response = self.client.post(
            reverse('node_handler', args=['invalid-uuid']), {})
        self.assertEqual(http.client.METHOD_NOT_ALLOWED, response.status_code)

    def test_UPDATE_disabled(self):
        machine = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        response = self.client.put(
            self.get_node_uri(machine), {'hostname': 'francis'})
        self.assertEqual(
            http.client.METHOD_NOT_ALLOWED, response.status_code)


class TestGetDetails(APITestCase):
    """Tests for /api/2.0/nodes/<node>/?op=details."""

    def make_lshw_result(self, node, script_result=0):
        return factory.make_NodeResult_for_commissioning(
            node=node, name=LSHW_OUTPUT_NAME,
            script_result=script_result)

    def make_lldp_result(self, node, script_result=0):
        return factory.make_NodeResult_for_commissioning(
            node=node, name=LLDP_OUTPUT_NAME, script_result=script_result)

    def get_details(self, node):
        url = reverse('node_handler', args=[node.system_id])
        response = self.client.get(url, {'op': 'details'})
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual('application/bson', response['content-type'])
        return bson.BSON(response.content).decode()

    def test_GET_returns_empty_details_when_there_are_none(self):
        node = factory.make_Node()
        self.assertDictEqual(
            {"lshw": None, "lldp": None},
            self.get_details(node))

    def test_GET_returns_all_details(self):
        node = factory.make_Node()
        lshw_result = self.make_lshw_result(node)
        lldp_result = self.make_lldp_result(node)
        self.assertDictEqual(
            {"lshw": lshw_result.data,
             "lldp": lldp_result.data},
            self.get_details(node))

    def test_GET_returns_only_those_details_that_exist(self):
        node = factory.make_Node()
        lshw_result = self.make_lshw_result(node)
        self.assertDictEqual(
            {"lshw": lshw_result.data,
             "lldp": None},
            self.get_details(node))

    def test_GET_returns_not_found_when_node_does_not_exist(self):
        url = reverse('node_handler', args=['does-not-exist'])
        response = self.client.get(url, {'op': 'details'})
        self.assertEqual(http.client.NOT_FOUND, response.status_code)


class TestPowerParameters(APITestCase):
    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse('node_handler', args=[node.system_id])

    def test_get_power_parameters(self):
        self.become_admin()
        power_parameters = {factory.make_string(): factory.make_string()}
        node = factory.make_Node(power_parameters=power_parameters)
        response = self.client.get(
            self.get_node_uri(node), {'op': 'power_parameters'})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_params = json_load_bytes(response.content)
        self.assertEqual(node.power_parameters, parsed_params)

    def test_get_power_parameters_empty(self):
        self.become_admin()
        node = factory.make_Node()
        response = self.client.get(
            self.get_node_uri(node), {'op': 'power_parameters'})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_params = json_load_bytes(response.content)
        self.assertEqual({}, parsed_params)

    def test_power_parameters_requires_admin(self):
        node = factory.make_Node()
        response = self.client.get(
            self.get_node_uri(node), {'op': 'power_parameters'})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content)


class TestQueryPowerState(APITestCase):
    """Tests for /api/2.0/nodes/<node>/?op=query_power_state"""

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse('node_handler', args=[node.system_id])

    def test_query_power_state(self):
        node = factory.make_Node()
        mock__power_control_node = self.patch(
            node_module.Node, "power_query").return_value
        mock__power_control_node.wait = Mock(return_value=POWER_STATE.ON)
        response = self.client.get(
            self.get_node_uri(node), {'op': 'query_power_state'})
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(POWER_STATE.ON, parsed_result['state'])


class TestSetOwnerData(APITestCase):
    """Tests for op=set_owner_data for both machines and devices."""

    scenarios = (
        ("machine", {
            "handler": "machine_handler",
            "maker": factory.make_Node,
        }),
        ("device", {
            "handler": "device_handler",
            "maker": factory.make_Device,
        }),
    )

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse(self.handler, args=[node.system_id])

    def test_must_be_able_to_edit(self):
        node = self.maker(status=NODE_STATUS.READY)
        owner_data = {
            factory.make_name("key"): factory.make_name("value")
            for _ in range(3)
        }
        params = dict(owner_data)
        params["op"] = "set_owner_data"
        response = self.client.post(self.get_node_uri(node), params)
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_adds_data(self):
        node = self.maker(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        owner_data = {
            factory.make_name("key"): factory.make_name("value")
            for _ in range(3)
        }
        params = dict(owner_data)
        params["op"] = "set_owner_data"
        response = self.client.post(self.get_node_uri(node), params)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            owner_data, json_load_bytes(response.content)['owner_data'])

    def test_updates_data(self):
        owner_data = {
            factory.make_name("key"): factory.make_name("value")
            for _ in range(3)
        }
        node = self.maker(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user,
            owner_data=owner_data)
        for key in owner_data.keys():
            owner_data[key] = factory.make_name("value")
        params = dict(owner_data)
        params["op"] = "set_owner_data"
        response = self.client.post(self.get_node_uri(node), params)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            owner_data, json_load_bytes(response.content)['owner_data'])

    def test_removes_data(self):
        owner_data = {
            factory.make_name("key"): factory.make_name("value")
            for _ in range(3)
        }
        node = self.maker(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user,
            owner_data=owner_data)
        for key in owner_data.keys():
            owner_data[key] = ''
        params = dict(owner_data)
        params["op"] = "set_owner_data"
        response = self.client.post(self.get_node_uri(node), params)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            {}, json_load_bytes(response.content)['owner_data'])
