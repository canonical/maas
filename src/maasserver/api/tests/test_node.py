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
    NODE_STATUS_CHOICES,
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
from maasserver.utils.orm import reload_object
from maastesting.matchers import (
    Equals,
    MockCalledOnceWith,
)
from metadataserver.models import NodeKey
from metadataserver.nodeinituser import get_node_init_user
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


class TestMarkBroken(APITestCase):
    """Tests for /api/2.0/nodes/<node>/?op=mark_broken"""

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse('node_handler', args=[node.system_id])

    def test_mark_broken_changes_status(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.logged_in_user)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'mark_broken'})
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.BROKEN, reload_object(node).status)

    def test_mark_broken_updates_error_description(self):
        # 'error_description' parameter was renamed 'comment' for consistency
        # make sure this comment updates the node's error_description
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.logged_in_user)
        comment = factory.make_name('comment')
        response = self.client.post(
            self.get_node_uri(node),
            {'op': 'mark_broken', 'comment': comment})
        self.assertEqual(http.client.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(
            (NODE_STATUS.BROKEN, comment),
            (node.status, node.error_description)
        )

    def test_mark_broken_updates_error_description_compatibility(self):
        # test old 'error_description' parameter is honored for compatibility
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.logged_in_user)
        error_description = factory.make_name('error_description')
        response = self.client.post(
            self.get_node_uri(node),
            {'op': 'mark_broken', 'error_description': error_description})
        self.assertEqual(http.client.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(
            (NODE_STATUS.BROKEN, error_description),
            (node.status, node.error_description)
        )

    def test_mark_broken_passes_comment(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.logged_in_user)
        node_mark_broken = self.patch(node_module.Node, 'mark_broken')
        comment = factory.make_name('comment')
        self.client.post(
            self.get_node_uri(node),
            {'op': 'mark_broken', 'comment': comment})
        self.assertThat(
            node_mark_broken,
            MockCalledOnceWith(self.logged_in_user, comment))

    def test_mark_broken_handles_missing_comment(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.logged_in_user)
        node_mark_broken = self.patch(node_module.Node, 'mark_broken')
        self.client.post(
            self.get_node_uri(node), {'op': 'mark_broken'})
        self.assertThat(
            node_mark_broken,
            MockCalledOnceWith(self.logged_in_user, None))

    def test_mark_broken_requires_ownership(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'mark_broken'})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_mark_broken_allowed_from_any_other_state(self):
        self.patch(node_module.Node, "_stop")
        for status, _ in NODE_STATUS_CHOICES:
            if status == NODE_STATUS.BROKEN:
                continue

            node = factory.make_Node(status=status, owner=self.logged_in_user)
            response = self.client.post(
                self.get_node_uri(node), {'op': 'mark_broken'})
            self.expectThat(
                response.status_code, Equals(http.client.OK), response)
            node = reload_object(node)
            self.expectThat(node.status, Equals(NODE_STATUS.BROKEN))


class TestMarkFixed(APITestCase):
    """Tests for /api/2.0/nodes/<node>/?op=mark_fixed"""

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse('node_handler', args=[node.system_id])

    def test_mark_fixed_changes_status(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'mark_fixed'})
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)

    def test_mark_fixed_requires_admin(self):
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'mark_fixed'})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_mark_fixed_passes_comment(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        node_mark_fixed = self.patch(node_module.Node, 'mark_fixed')
        comment = factory.make_name('comment')
        self.client.post(
            self.get_node_uri(node),
            {'op': 'mark_fixed', 'comment': comment})
        self.assertThat(
            node_mark_fixed,
            MockCalledOnceWith(self.logged_in_user, comment))

    def test_mark_fixed_handles_missing_comment(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        node_mark_fixed = self.patch(node_module.Node, 'mark_fixed')
        self.client.post(
            self.get_node_uri(node), {'op': 'mark_fixed'})
        self.assertThat(
            node_mark_fixed,
            MockCalledOnceWith(self.logged_in_user, None))
