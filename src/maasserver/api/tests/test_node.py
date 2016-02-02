# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Node API."""

__all__ = []

import http.client
from io import StringIO
import sys

import bson
from django.conf import settings
from django.core.urlresolvers import reverse
from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_STATUS_CHOICES_DICT,
)
from maasserver.models import (
    Node,
    node as node_module,
)
from maasserver.testing.api import APITestCase
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.oauthclient import OAuthAuthenticatedClient
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import json_load_bytes
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

    def setUp(self):
        super(NodeAnonAPITest, self).setUp()
        self.patch(node_module, 'power_on_node')
        self.patch(node_module, 'power_off_node')
        self.patch(node_module, 'power_driver_check')

    def test_anon_api_doc(self):
        # The documentation is accessible to anon users.
        self.patch(sys, "stderr", StringIO())
        response = self.client.get(reverse('api-doc'))
        self.assertEqual(http.client.OK, response.status_code)
        # No error or warning are emitted by docutils.
        self.assertEqual("", sys.stderr.getvalue())

    def test_node_init_user_cannot_access(self):
        token = NodeKey.objects.get_token_for_node(factory.make_Node())
        client = OAuthAuthenticatedClient(get_node_init_user(), token)
        response = client.get(reverse('nodes_handler'), {'op': 'list'})
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

    def setUp(self):
        super(TestNodeAPI, self).setUp()
        self.patch(node_module, 'power_on_node')
        self.patch(node_module, 'power_off_node')
        self.patch(node_module, 'power_driver_check')
        self.patch(node_module.Node, '_power_control_node')

    def test_handler_path(self):
        self.assertEqual(
            '/api/2.0/nodes/node-name/',
            reverse('node_handler', args=['node-name']))

    @staticmethod
    def get_node_uri(node):
        """Get the API URI for `node`."""
        return reverse('node_handler', args=[node.system_id])

    def test_GET_returns_node(self):
        # The api allows for fetching a single Node (using system_id).
        node = factory.make_Node()
        response = self.client.get(self.get_node_uri(node))

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        domain_name = node.domain.name
        self.assertEqual(
            "%s.%s" % (node.hostname, domain_name),
            parsed_result['hostname'])
        self.assertEqual(node.system_id, parsed_result['system_id'])

    def test_GET_returns_associated_tag(self):
        node = factory.make_Node()
        tag = factory.make_Tag()
        node.tags.add(tag)
        response = self.client.get(self.get_node_uri(node))

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual([tag.name], parsed_result['tag_names'])

    def test_GET_returns_associated_ip_addresses(self):
        node = factory.make_Node(disable_ipv4=False)
        nic = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        subnet = factory.make_Subnet()
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        lease = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=ip,
            interface=nic, subnet=subnet)
        response = self.client.get(self.get_node_uri(node))

        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual([lease.ip], parsed_result['ip_addresses'])

    def test_GET_returns_interface_set(self):
        node = factory.make_Node()
        response = self.client.get(self.get_node_uri(node))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertIn('interface_set', parsed_result)

    def test_GET_returns_zone(self):
        node = factory.make_Node()
        response = self.client.get(self.get_node_uri(node))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            [node.zone.name, node.zone.description],
            [
                parsed_result['zone']['name'],
                parsed_result['zone']['description']])

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

    def test_GET_returns_owner_name_when_allocated_to_self(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        response = self.client.get(self.get_node_uri(node))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(node.owner.username, parsed_result["owner"])

    def test_GET_returns_owner_name_when_allocated_to_other_user(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        response = self.client.get(self.get_node_uri(node))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(node.owner.username, parsed_result["owner"])

    def test_GET_returns_empty_owner_when_not_allocated(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        response = self.client.get(self.get_node_uri(node))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(None, parsed_result["owner"])

    def test_GET_returns_physical_block_devices(self):
        node = factory.make_Node(with_boot_disk=False)
        devices = [
            factory.make_PhysicalBlockDevice(node=node)
            for _ in range(3)
        ]
        response = self.client.get(self.get_node_uri(node))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        parsed_devices = [
            device['name']
            for device in parsed_result['physicalblockdevice_set']
        ]
        self.assertItemsEqual(
            [device.name for device in devices], parsed_devices)

    def test_GET_returns_min_hwe_kernel_and_hwe_kernel(self):
        node = factory.make_Node()
        response = self.client.get(self.get_node_uri(node))

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(None, parsed_result['min_hwe_kernel'])
        self.assertEqual(None, parsed_result['hwe_kernel'])

    def test_GET_returns_min_hwe_kernel(self):
        node = factory.make_Node(min_hwe_kernel="hwe-v")
        response = self.client.get(self.get_node_uri(node))

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual("hwe-v", parsed_result['min_hwe_kernel'])

    def test_GET_returns_substatus_message_with_most_recent_event(self):
        """Makes sure the most recent event from this node is shown in the
        substatus_message attribute."""
        # The first event won't be returned.
        event = factory.make_Event(description="Uninteresting event")
        node = event.node
        # The second (and last) event will be returned.
        message = "Interesting event"
        factory.make_Event(description=message, node=node)
        response = self.client.get(self.get_node_uri(node))
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(message, parsed_result['substatus_message'])

    def test_GET_returns_substatus_name(self):
        """GET should display the node status as a user-friendly string."""
        for status in NODE_STATUS_CHOICES_DICT:
            node = factory.make_Node(status=status)
            response = self.client.get(self.get_node_uri(node))
            parsed_result = json_load_bytes(response.content)
            self.assertEqual(NODE_STATUS_CHOICES_DICT[status],
                             parsed_result['substatus_name'])

    def test_resource_uri_points_back_at_node(self):
        self.become_admin()
        # When a Node is returned by the API, the field 'resource_uri'
        # provides the URI for this Node.
        node = factory.make_Node(
            hostname='diane', owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        response = self.client.post(
            self.get_node_uri(node), {'op': 'mark_broken'})
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            reverse('node_handler', args=[parsed_result['system_id']]),
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
