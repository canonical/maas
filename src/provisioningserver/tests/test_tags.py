# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for tag updating."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from apiclient.maas_client import MAASClient
import httplib
from lxml import etree
from maastesting.factory import factory
from maastesting.fakemethod import (
    FakeMethod,
    MultiFakeMethod,
    )
from mock import MagicMock
from provisioningserver.auth import (
    get_recorded_nodegroup_uuid,
    )
from provisioningserver.testing.testcase import PservTestCase
from provisioningserver import tags


class FakeResponse:

    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content


class TestTagUpdating(PservTestCase):

    def test_get_cached_knowledge_knows_nothing(self):
        # If we haven't given it any secrets, we should get back nothing
        self.assertEqual((None, None), tags.get_cached_knowledge())

    def test_get_cached_knowledge_with_only_url(self):
        self.set_maas_url()
        self.assertEqual((None, None), tags.get_cached_knowledge())

    def test_get_cached_knowledge_with_only_url_creds(self):
        self.set_maas_url()
        self.set_api_credentials()
        self.assertEqual((None, None), tags.get_cached_knowledge())

    def test_get_cached_knowledge_with_all_info(self):
        self.set_maas_url()
        self.set_api_credentials()
        self.set_node_group_uuid()
        client, uuid = tags.get_cached_knowledge()
        self.assertIsNot(None, client)
        self.assertIsInstance(client, MAASClient)
        self.assertIsNot(None, uuid)
        self.assertEqual(get_recorded_nodegroup_uuid(), uuid)

    def fake_client(self):
        return MAASClient(None, None, self.make_maas_url())

    def fake_cached_knowledge(self):
        nodegroup_uuid = factory.make_name('nodegroupuuid')
        return self.fake_client(), nodegroup_uuid

    def test_get_nodes_calls_correct_api_and_parses_result(self):
        client, uuid = self.fake_cached_knowledge()
        response = FakeResponse(httplib.OK, '["system-id1", "system-id2"]')
        mock = MagicMock(return_value=response)
        self.patch(client, 'get', mock)
        result = tags.get_nodes_for_node_group(client, uuid)
        self.assertEqual(['system-id1', 'system-id2'], result)
        url = 'api/1.0/nodegroup/%s/' % (uuid,)
        mock.assert_called_once_with(url, op='list_nodes')

    def test_get_hardware_details_calls_correct_api_and_parses_result(self):
        client, uuid = self.fake_cached_knowledge()
        xml_data = "<test><data /></test>"
        content = '[["system-id1", "%s"]]' % (xml_data,)
        response = FakeResponse(httplib.OK, content)
        mock = MagicMock(return_value=response)
        self.patch(client, 'get', mock)
        result = tags.get_hardware_details_for_nodes(
            client, uuid, ['system-id1', 'system-id2'])
        self.assertEqual([['system-id1', xml_data]], result)
        url = 'api/1.0/nodegroup/%s/' % (uuid,)
        mock.assert_called_once_with(
            url, op='node_hardware_details',
            system_ids=["system-id1", "system-id2"])

    def test_update_node_tags_calls_correct_api_and_parses_result(self):
        client, uuid = self.fake_cached_knowledge()
        content = '{"added": 1, "removed": 2}'
        response = FakeResponse(httplib.OK, content)
        mock = MagicMock(return_value=response)
        self.patch(client, 'post', mock)
        name = factory.make_name('tag')
        result = tags.update_node_tags(client, name, uuid,
            ['add-system-id'], ['remove-1', 'remove-2'])
        self.assertEqual({'added': 1, 'removed': 2}, result)
        url = 'api/1.0/tags/%s/' % (name,)
        mock.assert_called_once_with(
            url, op='update_nodes',
            add=['add-system-id'], remove=['remove-1', 'remove-2'])

    def test_process_batch_evaluates_xpath(self):
        # Yay, something that doesn't need patching...
        xpath = etree.XPath('//node')
        node_details = [['a', '<node />'],
                        ['b', '<not-node />'],
                        ['c', '<parent><node /></parent>'],
                       ]
        self.assertEqual(
            (['a', 'c'], ['b']),
            tags.process_batch(xpath, node_details))

    def test_process_node_tags_no_secrets(self):
        self.patch(MAASClient, 'get')
        self.patch(MAASClient, 'post')
        tag_name = factory.make_name('tag')
        tags.process_node_tags(tag_name, '//node')
        self.assertFalse(MAASClient.get.called)
        self.assertFalse(MAASClient.post.called)

    def test_process_node_tags_integration(self):
        self.set_secrets()
        get_nodes = FakeMethod(
            result=FakeResponse(httplib.OK, '["system-id1", "system-id2"]'))
        get_hw_details = FakeMethod(
            result=FakeResponse(httplib.OK,
                '[["system-id1", "<node />"], ["system-id2", "<no-node />"]]'))
        get_fake = MultiFakeMethod([get_nodes, get_hw_details])
        post_fake = FakeMethod(
            result=FakeResponse(httplib.OK, '{"added": 1, "removed": 1}'))
        self.patch(MAASClient, 'get', get_fake)
        self.patch(MAASClient, 'post', post_fake)
        tag_name = factory.make_name('tag')
        nodegroup_uuid = get_recorded_nodegroup_uuid()
        tags.process_node_tags(tag_name, '//node')
        nodegroup_url = 'api/1.0/nodegroup/%s/' % (nodegroup_uuid,)
        tag_url = 'api/1.0/tags/%s/' % (tag_name,)
        self.assertEqual([((nodegroup_url,), {'op': 'list_nodes'})],
                         get_nodes.calls)
        self.assertEqual([((nodegroup_url,),
                          {'op': 'node_hardware_details',
                           'system_ids': ['system-id1', 'system-id2']})],
                         get_hw_details.calls)
        self.assertEqual([((tag_url,),
                          {'op': 'update_nodes',
                           'add': ['system-id1'],
                           'remove': ['system-id2'],
                          })], post_fake.calls)

    def test_process_node_tags_requests_details_in_batches(self):
        client = object()
        uuid = factory.make_name('nodegroupuuid')
        self.patch(
            tags, 'get_cached_knowledge',
            MagicMock(return_value=(client, uuid)))
        self.patch(
            tags, 'get_nodes_for_node_group',
            MagicMock(return_value=['a', 'b', 'c']))
        fake_first = FakeMethod(
            result=[['a', '<node />'], ['b', '<not-node />']])
        fake_second = FakeMethod(
            result=[['c', '<parent><node /></parent>']])
        self.patch(tags, 'get_hardware_details_for_nodes',
            MultiFakeMethod([fake_first, fake_second]))
        self.patch(tags, 'update_node_tags')
        tag_name = factory.make_name('tag')
        tags.process_node_tags(tag_name, '//node', batch_size=2)
        tags.get_cached_knowledge.assert_called_once_with()
        tags.get_nodes_for_node_group.assert_called_once_with(client, uuid)
        self.assertEqual([((client, uuid, ['a', 'b']), {})], fake_first.calls)
        self.assertEqual([((client, uuid, ['c']), {})], fake_second.calls)
        tags.update_node_tags.assert_called_once_with(
            client, tag_name, uuid, ['a', 'c'], ['b'])
