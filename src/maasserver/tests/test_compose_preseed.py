# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.compose_preseed`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver.compose_preseed import compose_preseed
from maasserver.enum import NODE_STATUS
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from maasserver.utils import absolute_reverse
from metadataserver.models import NodeKey
from testtools.matchers import (
    KeysEqual,
    StartsWith,
    )
import yaml


class TestComposePreseed(TestCase):

    def test_compose_preseed_for_commissioning_node_produces_yaml(self):
        node = factory.make_node(status=NODE_STATUS.COMMISSIONING)
        preseed = yaml.safe_load(compose_preseed(node))
        self.assertIn('datasource', preseed)
        self.assertIn('MAAS', preseed['datasource'])
        self.assertThat(
            preseed['datasource']['MAAS'],
            KeysEqual(
                'metadata_url', 'consumer_key', 'token_key', 'token_secret'))

    def test_compose_preseed_for_commissioning_node_has_header(self):
        node = factory.make_node(status=NODE_STATUS.COMMISSIONING)
        self.assertThat(compose_preseed(node), StartsWith("#cloud-config\n"))

    def test_compose_preseed_includes_metadata_url(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        self.assertIn(absolute_reverse('metadata'), compose_preseed(node))

    def test_compose_preseed_for_commissioning_includes_metadata_url(self):
        node = factory.make_node(status=NODE_STATUS.COMMISSIONING)
        preseed = yaml.safe_load(compose_preseed(node))
        self.assertEqual(
            absolute_reverse('metadata'),
            preseed['datasource']['MAAS']['metadata_url'])

    def test_compose_preseed_includes_node_oauth_token(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        preseed = compose_preseed(node)
        token = NodeKey.objects.get_token_for_node(node)
        self.assertIn('oauth_consumer_key=%s' % token.consumer.key, preseed)
        self.assertIn('oauth_token_key=%s' % token.key, preseed)
        self.assertIn('oauth_token_secret=%s' % token.secret, preseed)

    def test_compose_preseed_for_commissioning_includes_auth_token(self):
        node = factory.make_node(status=NODE_STATUS.COMMISSIONING)
        preseed = yaml.safe_load(compose_preseed(node))
        maas_dict = preseed['datasource']['MAAS']
        token = NodeKey.objects.get_token_for_node(node)
        self.assertEqual(token.consumer.key, maas_dict['consumer_key'])
        self.assertEqual(token.key, maas_dict['token_key'])
        self.assertEqual(token.secret, maas_dict['token_secret'])
