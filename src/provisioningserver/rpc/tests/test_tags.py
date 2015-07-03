# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~provisioningserver.rpc.dhcp`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from apiclient.maas_client import (
    MAASClient,
    MAASDispatcher,
    MAASOAuth,
)
from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import (
    ANY,
    sentinel,
)
from provisioningserver.rpc import tags
from provisioningserver.testing.config import ClusterConfigurationFixture


class TestEvaluateTag(MAASTestCase):

    def setUp(self):
        super(TestEvaluateTag, self).setUp()
        self.mock_cluster_uuid = factory.make_UUID()
        self.mock_url = factory.make_simple_http_url()
        self.useFixture(ClusterConfigurationFixture(
            cluster_uuid=self.mock_cluster_uuid, maas_url=self.mock_url))

    def test__calls_process_node_tags(self):
        credentials = "aaa", "bbb", "ccc"
        process_node_tags = self.patch_autospec(tags, "process_node_tags")
        tags.evaluate_tag(
            sentinel.tag_name, sentinel.tag_definition, sentinel.tag_nsmap,
            credentials)
        self.assertThat(
            process_node_tags, MockCalledOnceWith(
                tag_name=sentinel.tag_name,
                tag_definition=sentinel.tag_definition,
                tag_nsmap=sentinel.tag_nsmap, client=ANY,
                nodegroup_uuid=self.mock_cluster_uuid))

    def test__constructs_client_with_credentials(self):
        consumer_key = factory.make_name("ckey")
        resource_token = factory.make_name("rtok")
        resource_secret = factory.make_name("rsec")
        credentials = consumer_key, resource_token, resource_secret

        self.patch_autospec(tags, "process_node_tags")
        self.patch_autospec(tags, "MAASOAuth").side_effect = MAASOAuth

        tags.evaluate_tag(
            sentinel.tag_name, sentinel.tag_definition, sentinel.tag_nsmap,
            credentials)

        client = tags.process_node_tags.call_args[1]["client"]
        self.assertIsInstance(client, MAASClient)
        self.assertEqual(self.mock_url, client.url)
        self.assertIsInstance(client.dispatcher, MAASDispatcher)
        self.assertIsInstance(client.auth, MAASOAuth)
        self.assertThat(tags.MAASOAuth, MockCalledOnceWith(
            consumer_key, resource_token, resource_secret))
