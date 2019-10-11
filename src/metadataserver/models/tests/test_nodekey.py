# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :class:`NodeKey` model and manager."""

__all__ = []

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from metadataserver.models import NodeKey
from testtools.matchers import HasLength


class TestNodeKeyManager(MAASServerTestCase):
    """Test NodeKeyManager."""

    def test_get_token_for_node_registers_node_key(self):
        node = factory.make_Node()
        token = NodeKey.objects.get_token_for_node(node)
        nodekey = NodeKey.objects.get(node=node, key=token.key)
        self.assertNotEqual(None, nodekey)
        self.assertEqual(token, nodekey.token)

    def test_get_node_for_key_finds_node(self):
        node = factory.make_Node()
        token = NodeKey.objects.get_token_for_node(node)
        self.assertEqual(node, NodeKey.objects.get_node_for_key(token.key))

    def test_get_node_for_key_raises_DoesNotExist_if_key_not_found(self):
        non_key = factory.make_string()
        self.assertRaises(
            NodeKey.DoesNotExist, NodeKey.objects.get_node_for_key, non_key
        )

    def test_get_token_for_node_creates_token(self):
        node = factory.make_Node()
        token = NodeKey.objects.get_token_for_node(node)
        self.assertEqual(node, NodeKey.objects.get_node_for_key(token.key))

    def test_get_token_for_node_returns_existing_token(self):
        node = factory.make_Node()
        original_token = NodeKey.objects.get_token_for_node(node)
        repeated_token = NodeKey.objects.get_token_for_node(node)
        self.assertEqual(original_token, repeated_token)

    def test_get_token_for_node_inverts_get_node_for_key(self):
        node = factory.make_Node()
        self.assertEqual(
            node,
            NodeKey.objects.get_node_for_key(
                NodeKey.objects.get_token_for_node(node).key
            ),
        )

    def test_clear_token_for_node_deletes_related_NodeKey(self):
        node = factory.make_Node()
        NodeKey.objects.get_token_for_node(node)
        NodeKey.objects.clear_token_for_node(node)
        self.assertThat(NodeKey.objects.filter(node=node), HasLength(0))

    def test_get_node_for_key_inverts_get_token_for_node(self):
        key = NodeKey.objects.get_token_for_node(factory.make_Node()).key
        self.assertEqual(
            key,
            NodeKey.objects.get_token_for_node(
                NodeKey.objects.get_node_for_key(key)
            ).key,
        )
