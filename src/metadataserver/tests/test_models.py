# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model tests for metadata server."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver.testing.factory import factory
from maastesting import TestCase
from metadataserver.models import (
    NodeKey,
    NodeUserData,
    )


class TestNodeKeyManager(TestCase):
    """Test NodeKeyManager."""

    def test_create_key_registers_node_key(self):
        node = factory.make_node()
        token = NodeKey.objects.create_token(node)
        nodekey = NodeKey.objects.get(node=node, key=token.key)
        self.assertNotEqual(None, nodekey)

    def test_get_node_for_key_finds_node(self):
        node = factory.make_node()
        token = NodeKey.objects.create_token(node)
        self.assertEqual(node, NodeKey.objects.get_node_for_key(token.key))

    def test_get_node_for_key_raises_DoesNotExist_if_key_not_found(self):
        non_key = factory.getRandomString()
        self.assertRaises(
            NodeKey.DoesNotExist, NodeKey.objects.get_node_for_key, non_key)


class TestNodeUserDataManager(TestCase):
    """Test NodeUserDataManager."""

    def test_set_user_data_creates_new_nodeuserdata_if_needed(self):
        node = factory.make_node()
        data = b'foo'
        NodeUserData.objects.set_user_data(node, data)
        self.assertEqual(data, NodeUserData.objects.get(node=node).data)

    def test_set_user_data_overwrites_existing_userdata(self):
        node = factory.make_node()
        data = b'bar'
        NodeUserData.objects.set_user_data(node, b'old data')
        NodeUserData.objects.set_user_data(node, data)
        self.assertEqual(data, NodeUserData.objects.get(node=node).data)

    def test_set_user_data_leaves_data_for_other_nodes_alone(self):
        node = factory.make_node()
        NodeUserData.objects.set_user_data(node, b'intact')
        NodeUserData.objects.set_user_data(factory.make_node(), b'unrelated')
        self.assertEqual(b'intact', NodeUserData.objects.get(node=node).data)

    def test_get_user_data_retrieves_data(self):
        node = factory.make_node()
        data = b'splat'
        NodeUserData.objects.set_user_data(node, data)
        self.assertEqual(data, NodeUserData.objects.get_user_data(node))

    def test_get_user_data_raises_DoesNotExist_if_not_found(self):
        node = factory.make_node()
        self.assertRaises(
            NodeUserData.DoesNotExist,
            NodeUserData.objects.get_user_data, node)

    def test_get_user_data_ignores_other_nodes(self):
        node = factory.make_node()
        data = b'bzzz'
        NodeUserData.objects.set_user_data(node, data)
        NodeUserData.objects.set_user_data(factory.make_node(), b'unrelated')
        self.assertEqual(data, NodeUserData.objects.get_user_data(node))

    def test_has_user_data_returns_False_if_node_has_no_user_data(self):
        self.assertFalse(
            NodeUserData.objects.has_user_data(factory.make_node()))

    def test_has_user_data_returns_True_if_node_has_user_data(self):
        node = factory.make_node()
        NodeUserData.objects.set_user_data(node, b"This node has user data.")
        self.assertTrue(NodeUserData.objects.has_user_data(node))
