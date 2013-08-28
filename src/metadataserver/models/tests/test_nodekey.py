# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :class:`NodeKey` model and manager."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver.testing.factory import factory
from maastesting.djangotestcase import DjangoTestCase
from metadataserver.models import NodeKey


class TestNodeKeyManager(DjangoTestCase):
    """Test NodeKeyManager."""

    def test_get_token_for_node_registers_node_key(self):
        node = factory.make_node()
        token = NodeKey.objects.get_token_for_node(node)
        nodekey = NodeKey.objects.get(node=node, key=token.key)
        self.assertNotEqual(None, nodekey)
        self.assertEqual(token, nodekey.token)

    def test_get_node_for_key_finds_node(self):
        node = factory.make_node()
        token = NodeKey.objects.get_token_for_node(node)
        self.assertEqual(node, NodeKey.objects.get_node_for_key(token.key))

    def test_get_node_for_key_raises_DoesNotExist_if_key_not_found(self):
        non_key = factory.getRandomString()
        self.assertRaises(
            NodeKey.DoesNotExist, NodeKey.objects.get_node_for_key, non_key)

    def test_get_token_for_node_creates_token(self):
        node = factory.make_node()
        token = NodeKey.objects.get_token_for_node(node)
        self.assertEqual(node, NodeKey.objects.get_node_for_key(token.key))

    def test_get_token_for_node_returns_existing_token(self):
        node = factory.make_node()
        original_token = NodeKey.objects.get_token_for_node(node)
        repeated_token = NodeKey.objects.get_token_for_node(node)
        self.assertEqual(original_token, repeated_token)

    def test_get_token_for_node_inverts_get_node_for_key(self):
        node = factory.make_node()
        self.assertEqual(
            node,
            NodeKey.objects.get_node_for_key(
                NodeKey.objects.get_token_for_node(node).key))

    def test_get_node_for_key_inverts_get_token_for_node(self):
        key = NodeKey.objects.get_token_for_node(factory.make_node()).key
        self.assertEqual(
            key,
            NodeKey.objects.get_token_for_node(
                NodeKey.objects.get_node_for_key(key)).key)
