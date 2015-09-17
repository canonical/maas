# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the metadata progress reporting API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import base64
import bz2
import httplib
import json

from django.core.urlresolvers import reverse
from maasserver.enum import NODE_STATUS
from maasserver.models import (
    Event,
    Node,
    Tag,
)
from maasserver.testing.factory import factory
from maasserver.testing.oauthclient import OAuthAuthenticatedClient
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from metadataserver import api
from metadataserver.models import (
    NodeKey,
    NodeResult,
)
from metadataserver.nodeinituser import get_node_init_user
from mock import ANY


def make_node_client(node=None):
    """Create a test client logged in as if it were `node`."""
    if node is None:
        node = factory.make_Node()
    token = NodeKey.objects.get_token_for_node(node)
    return OAuthAuthenticatedClient(get_node_init_user(), token)


def call_status(client=None, node=None, payload=None):
    """Call the API's status endpoint.

    The API does not receive any form data, just a JSON encoding several
    values.
    """
    if node is None:
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
    if client is None:
        client = make_node_client(node)

    url = reverse('metadata-status', args=[node.system_id])

    return client.post(
        url, content_type='application/json', data=json.dumps(payload))


class TestStatusAPI(MAASServerTestCase):

    def test_other_user_than_node_cannot_signal_installation_result(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        client = OAuthAuthenticatedClient(factory.make_User())
        response = call_status(client, node)
        self.assertEqual(httplib.FORBIDDEN, response.status_code)
        self.assertEqual(
            NODE_STATUS.DEPLOYING, reload_object(node).status)
        # No node events were logged.
        self.assertFalse(Event.objects.filter(node=node).exists())

    def test_status_installation_result_does_not_affect_other_node(self):
        node1 = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        node2 = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        client = make_node_client(node1)
        payload = {
            'event_type': 'finish',
            'result': 'SUCCESS',
            'origin': 'curtin',
            'name': 'cmd-install',
            'description': 'Command Install',
        }
        response = call_status(client, node1, payload)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.DEPLOYING, reload_object(node2).status)
        # Check last node1 event.
        self.assertEqual(
            "'curtin' Command Install",
            Event.objects.filter(node=node1).last().description)
        # There must me no events for node2.
        self.assertFalse(Event.objects.filter(node=node2).exists())

    def test_status_installation_success_leaves_node_deploying(self):
        node = factory.make_Node(interface=True, status=NODE_STATUS.DEPLOYING)
        client = make_node_client(node=node)
        payload = {
            'event_type': 'finish',
            'result': 'SUCCESS',
            'origin': 'curtin',
            'name': 'cmd-install',
            'description': 'Command Install',
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(NODE_STATUS.DEPLOYING, reload_object(node).status)
        # Check last node event.
        self.assertEqual(
            "'curtin' Command Install",
            Event.objects.filter(node=node).last().description)

    def test_status_comissioning_success_populates_tags(self):
        populate_tags_for_single_node = self.patch(
            api, "populate_tags_for_single_node")
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING)
        client = make_node_client(node=node)
        payload = {
            'event_type': 'finish',
            'result': 'SUCCESS',
            'origin': 'curtin',
            'name': 'cmd-install',
            'description': 'Command Install',
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertThat(
            populate_tags_for_single_node,
            MockCalledOnceWith(ANY, node))

    def test_status_comissioning_success_sets_node_network_configuration(self):
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING)
        mock_set_initial_networking_configuration = self.patch_autospec(
            Node, "set_initial_networking_configuration")
        client = make_node_client(node=node)
        payload = {
            'event_type': 'finish',
            'result': 'SUCCESS',
            'origin': 'curtin',
            'name': 'cmd-install',
            'description': 'Command Install',
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertThat(
            mock_set_initial_networking_configuration,
            MockCalledOnceWith(node))

    def test_status_commissioning_failure_leaves_node_failed(self):
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING)
        client = make_node_client(node=node)
        payload = {
            'event_type': 'finish',
            'result': 'FAILURE',
            'origin': 'curtin',
            'name': 'commissioning',
            'description': 'Commissioning',
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.FAILED_COMMISSIONING, reload_object(node).status)
        # Check last node event.
        self.assertEqual(
            "'curtin' Commissioning",
            Event.objects.filter(node=node).last().description)

    def test_status_commissioning_failure_clears_owner(self):
        user = factory.make_User()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING, owner=user)
        client = make_node_client(node=node)
        payload = {
            'event_type': 'finish',
            'result': 'FAILURE',
            'origin': 'curtin',
            'name': 'commissioning',
            'description': 'Commissioning',
        }
        self.assertEqual(user, node.owner)  # Node has an owner
        response = call_status(client, node, payload)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.FAILED_COMMISSIONING, reload_object(node).status)
        self.assertIsNone(reload_object(node).owner)

    def test_status_installation_failure_leaves_node_failed(self):
        node = factory.make_Node(interface=True, status=NODE_STATUS.DEPLOYING)
        client = make_node_client(node=node)
        payload = {
            'event_type': 'finish',
            'result': 'FAILURE',
            'origin': 'curtin',
            'name': 'cmd-install',
            'description': 'Command Install',
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.FAILED_DEPLOYMENT, reload_object(node).status)
        # Check last node event.
        self.assertEqual(
            "'curtin' Command Install",
            Event.objects.filter(node=node).last().description)

    def test_status_installation_fail_leaves_node_failed(self):
        node = factory.make_Node(interface=True, status=NODE_STATUS.DEPLOYING)
        client = make_node_client(node=node)
        payload = {
            'event_type': 'finish',
            'result': 'FAIL',
            'origin': 'curtin',
            'name': 'cmd-install',
            'description': 'Command Install',
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.FAILED_DEPLOYMENT, reload_object(node).status)
        # Check last node event.
        self.assertEqual(
            "'curtin' Command Install",
            Event.objects.filter(node=node).last().description)

    def test_status_installation_failure_doesnt_clear_owner(self):
        user = factory.make_User()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.DEPLOYING, owner=user)
        client = make_node_client(node=node)
        payload = {
            'event_type': 'finish',
            'result': 'FAILURE',
            'origin': 'curtin',
            'name': 'cmd-install',
            'description': 'Command Install',
        }
        self.assertEqual(user, node.owner)  # Node has an owner
        response = call_status(client, node, payload)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.FAILED_DEPLOYMENT, reload_object(node).status)
        self.assertIsNotNone(reload_object(node).owner)

    def test_status_commissioning_failure_does_not_populate_tags(self):
        populate_tags_for_single_node = self.patch(
            api, "populate_tags_for_single_node")
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING)
        client = make_node_client(node=node)
        payload = {
            'event_type': 'finish',
            'result': 'FAILURE',
            'origin': 'curtin',
            'name': 'commissioning',
            'description': 'Commissioning',
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.FAILED_COMMISSIONING, reload_object(node).status)
        self.assertThat(populate_tags_for_single_node, MockNotCalled())

    def test_status_erasure_failure_leaves_node_failed(self):
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.DISK_ERASING)
        client = make_node_client(node=node)
        payload = {
            'event_type': 'finish',
            'result': 'FAILURE',
            'origin': 'curtin',
            'name': 'cmd-erase',
            'description': 'Erasing disk',
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.FAILED_DISK_ERASING, reload_object(node).status)
        # Check last node event.
        self.assertEqual(
            "'curtin' Erasing disk",
            Event.objects.filter(node=node).last().description)

    def test_status_erasure_failure_does_not_populate_tags(self):
        populate_tags_for_single_node = self.patch(
            api, "populate_tags_for_single_node")
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.DISK_ERASING)
        client = make_node_client(node=node)
        payload = {
            'event_type': 'finish',
            'result': 'FAILURE',
            'origin': 'curtin',
            'name': 'cmd-erase',
            'description': 'Erasing disk',
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.FAILED_DISK_ERASING, reload_object(node).status)
        self.assertThat(populate_tags_for_single_node, MockNotCalled())

    def test_status_erasure_failure_clears_owner(self):
        user = factory.make_User()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.DISK_ERASING, owner=user)
        client = make_node_client(node=node)
        payload = {
            'event_type': 'finish',
            'result': 'FAILURE',
            'origin': 'curtin',
            'name': 'cmd-erase',
            'description': 'Erasing disk',
        }
        self.assertEqual(user, node.owner)  # Node has an owner
        response = call_status(client, node, payload)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.FAILED_DISK_ERASING, reload_object(node).status)
        self.assertIsNone(reload_object(node).owner)

    def test_status_with_file_bad_encoder_fails(self):
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING)
        client = make_node_client(node=node)
        contents = 'These are the contents of the file.'
        encoded_content = base64.encodestring(bz2.compress(contents))
        payload = {
            'event_type': 'finish',
            'result': 'FAILURE',
            'origin': 'curtin',
            'name': 'commissioning',
            'description': 'Commissioning',
            'files': [
                {
                    "path": "sample.txt",
                    "encoding": "uuencode",
                    "compression": "bzip2",
                    "content": encoded_content
                }
            ]
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual('Invalid encoding: uuencode', response.content)

    def test_status_with_file_bad_compression_fails(self):
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING)
        client = make_node_client(node=node)
        contents = 'These are the contents of the file.'
        encoded_content = base64.encodestring(bz2.compress(contents))
        payload = {
            'event_type': 'finish',
            'result': 'FAILURE',
            'origin': 'curtin',
            'name': 'commissioning',
            'description': 'Commissioning',
            'files': [
                {
                    "path": "sample.txt",
                    "encoding": "base64",
                    "compression": "jpeg",
                    "content": encoded_content
                }
            ]
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual('Invalid compression: jpeg', response.content)

    def test_status_with_file_no_compression_succeeds(self):
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING)
        client = make_node_client(node=node)
        contents = 'These are the contents of the file.'
        encoded_content = base64.encodestring(contents)
        payload = {
            'event_type': 'finish',
            'result': 'FAILURE',
            'origin': 'curtin',
            'name': 'commissioning',
            'description': 'Commissioning',
            'files': [
                {
                    "path": "sample.txt",
                    "encoding": "base64",
                    "content": encoded_content
                }
            ]
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(contents, NodeResult.objects.get(node=node).data)

    def test_status_with_file_invalid_statuses_fails(self):
        """Adding files should fail for every status that's neither
        COMMISSIONING nor DEPLOYING"""
        for node_status in [
                NODE_STATUS.DEFAULT,
                NODE_STATUS.NEW,
                NODE_STATUS.FAILED_COMMISSIONING,
                NODE_STATUS.MISSING,
                NODE_STATUS.READY,
                NODE_STATUS.RESERVED,
                NODE_STATUS.DEPLOYED,
                NODE_STATUS.RETIRED,
                NODE_STATUS.BROKEN,
                NODE_STATUS.ALLOCATED,
                NODE_STATUS.FAILED_DEPLOYMENT,
                NODE_STATUS.RELEASING,
                NODE_STATUS.FAILED_RELEASING,
                NODE_STATUS.DISK_ERASING,
                NODE_STATUS.FAILED_DISK_ERASING]:
            node = factory.make_Node(interface=True, status=node_status)
            client = make_node_client(node=node)
            contents = 'These are the contents of the file.'
            encoded_content = base64.encodestring(bz2.compress(contents))
            payload = {
                'event_type': 'finish',
                'result': 'FAILURE',
                'origin': 'curtin',
                'name': 'commissioning',
                'description': 'Commissioning',
                'files': [
                    {
                        "path": "sample.txt",
                        "encoding": "base64",
                        "compression": "bzip2",
                        "content": encoded_content
                    }
                ]
            }
            response = call_status(client, node, payload)
            self.assertEqual(httplib.BAD_REQUEST, response.status_code)
            self.assertEqual(
                'Invalid status for saving files: %d' % node_status,
                response.content)

    def test_status_with_file_succeeds(self):
        """Adding files should succeed for every status that's either
        COMMISSIONING or DEPLOYING"""
        for node_status, target_status in [
                (NODE_STATUS.COMMISSIONING, NODE_STATUS.FAILED_COMMISSIONING),
                (NODE_STATUS.DEPLOYING, NODE_STATUS.FAILED_DEPLOYMENT)]:
            node = factory.make_Node(interface=True, status=node_status)
            client = make_node_client(node=node)
            contents = 'These are the contents of the file.'
            encoded_content = base64.encodestring(bz2.compress(contents))
            payload = {
                'event_type': 'finish',
                'result': 'FAILURE',
                'origin': 'curtin',
                'name': 'commissioning',
                'description': 'Commissioning',
                'files': [
                    {
                        "path": "sample.txt",
                        "encoding": "base64",
                        "compression": "bzip2",
                        "content": encoded_content
                    }
                ]
            }
            response = call_status(client, node, payload)
            self.assertEqual(httplib.OK, response.status_code)
            self.assertEqual(
                target_status, reload_object(node).status)
            # Check the node result.
            self.assertEqual(contents, NodeResult.objects.get(node=node).data)

    def test_status_with_results_succeeds(self):
        """Adding a script result should succeed"""
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING)
        client = make_node_client(node=node)
        contents = 'These are the contents of the file.'
        encoded_content = base64.encodestring(bz2.compress(contents))
        payload = {
            'event_type': 'finish',
            'result': 'FAILURE',
            'origin': 'curtin',
            'name': 'commissioning',
            'description': 'Commissioning',
            'files': [
                {
                    "path": "lshw",
                    "encoding": "base64",
                    "compression": "bzip2",
                    "content": encoded_content,
                    "result": -42
                }
            ]
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.OK, response.status_code)
        # Check the node result.
        node_result = NodeResult.objects.get(node=node)
        self.assertEqual(contents, node_result.data)
        self.assertEqual(-42, node_result.script_result)

    def test_status_with_results_no_script_result_defaults_to_zero(self):
        """Adding a script result should succeed without a return code defaults
        it to zero."""
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING)
        client = make_node_client(node=node)
        contents = 'These are the contents of the file.'
        encoded_content = base64.encodestring(bz2.compress(contents))
        payload = {
            'event_type': 'finish',
            'result': 'FAILURE',
            'origin': 'curtin',
            'name': 'commissioning',
            'description': 'Commissioning',
            'files': [
                {
                    "path": "lshw",
                    "encoding": "base64",
                    "compression": "bzip2",
                    "content": encoded_content,
                }
            ]
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.OK, response.status_code)
        # Check the node result.
        node_result = NodeResult.objects.get(node=node)
        self.assertEqual(0, node_result.script_result)

    def test_status_with_missing_event_type_fails(self):
        node = factory.make_Node(interface=True, status=NODE_STATUS.DEPLOYING)
        client = make_node_client(node=node)
        payload = {
            'result': 'SUCCESS',
            'origin': 'curtin',
            'name': 'cmd-install',
            'description': 'Command Install',
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertIn('Missing parameter in status message', response.content)

    def test_status_with_missing_origin_fails(self):
        node = factory.make_Node(interface=True, status=NODE_STATUS.DEPLOYING)
        client = make_node_client(node=node)
        payload = {
            'event_type': 'finish',
            'result': 'SUCCESS',
            'name': 'cmd-install',
            'description': 'Command Install',
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertIn('Missing parameter in status message', response.content)

    def test_status_with_missing_name_fails(self):
        node = factory.make_Node(interface=True, status=NODE_STATUS.DEPLOYING)
        client = make_node_client(node=node)
        payload = {
            'event_type': 'finish',
            'result': 'SUCCESS',
            'origin': 'curtin',
            'description': 'Command Install',
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertIn('Missing parameter in status message', response.content)

    def test_status_with_missing_description_fails(self):
        node = factory.make_Node(interface=True, status=NODE_STATUS.DEPLOYING)
        client = make_node_client(node=node)
        payload = {
            'event_type': 'finish',
            'result': 'SUCCESS',
            'origin': 'curtin',
            'name': 'cmd-install',
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertIn('Missing parameter in status message', response.content)

    def test_status_stores_virtual_tag_on_node_if_virtual(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        client = make_node_client(node=node)
        content = 'virtual'.encode('utf-8')
        payload = {
            'event_type': 'finish',
            'result': 'SUCCESS',
            'origin': 'curtin',
            'name': 'commissioning',
            'description': 'Commissioning',
            'files': [
                {
                    "path": "00-maas-02-virtuality.out",
                    "encoding": "base64",
                    "content": base64.encodestring(content),
                }
            ]
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(
            ["virtual"], [each_tag.name for each_tag in node.tags.all()])
        self.assertEqual(content, NodeResult.objects.get(node=node).data)
        self.assertEqual(
            "00-maas-02-virtuality.out",
            NodeResult.objects.get(node=node).name)

    def test_status_removes_virtual_tag_on_node_if_not_virtual(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        tag, _ = Tag.objects.get_or_create(name='virtual')
        node.tags.add(tag)
        client = make_node_client(node=node)
        content = 'notvirtual'.encode('utf-8')
        payload = {
            'event_type': 'finish',
            'result': 'SUCCESS',
            'origin': 'curtin',
            'name': 'commissioning',
            'description': 'Commissioning',
            'files': [
                {
                    "path": "00-maas-02-virtuality.out",
                    "encoding": "base64",
                    "content": base64.encodestring(content),
                }
            ]
        }
        response = call_status(client, node, payload)
        self.assertEqual(httplib.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(
            [], [each_tag.name for each_tag in node.tags.all()])
        self.assertEqual(content, NodeResult.objects.get(node=node).data)
        self.assertEqual(
            "00-maas-02-virtuality.out",
            NodeResult.objects.get(node=node).name)
