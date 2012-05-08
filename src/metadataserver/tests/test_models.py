# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model tests for metadata server."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from django.core.exceptions import ValidationError
from django.http import Http404
from maasserver.testing.factory import factory
from maastesting.djangotestcase import DjangoTestCase
from metadataserver.models import (
    NodeCommissionResult,
    NodeKey,
    NodeUserData,
    )


class TestNodeKeyManager(DjangoTestCase):
    """Test NodeKeyManager."""

    def setUp(self):
        super(TestNodeKeyManager, self).setUp()

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


class TestNodeUserDataManager(DjangoTestCase):
    """Test NodeUserDataManager."""

    def setUp(self):
        super(TestNodeUserDataManager, self).setUp()

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

    def test_set_user_data_to_None_removes_user_data(self):
        node = factory.make_node()
        NodeUserData.objects.set_user_data(node, b'original')
        NodeUserData.objects.set_user_data(node, None)
        self.assertItemsEqual([], NodeUserData.objects.filter(node=node))

    def test_set_user_data_to_None_when_none_exists_does_nothing(self):
        node = factory.make_node()
        NodeUserData.objects.set_user_data(node, None)
        self.assertItemsEqual([], NodeUserData.objects.filter(node=node))

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


class TestNodeCommissionResult(DjangoTestCase):
    """Test the NodeCommissionResult model."""

    def test_can_store_data(self):
        node = factory.make_node()
        name = factory.getRandomString(100)
        data = factory.getRandomString(1025)
        factory.make_node_commission_result(node=node, name=name, data=data)

        ncr = NodeCommissionResult.objects.get(name=name)
        self.assertAttributes(ncr, dict(node=node, data=data))

    def test_node_name_uniqueness(self):
        # You cannot have two result rows with the same name for the
        # same node.
        node = factory.make_node()
        factory.make_node_commission_result(node=node, name="foo")
        self.assertRaises(
            ValidationError,
            factory.make_node_commission_result, node=node, name="foo")

    def test_different_nodes_can_have_same_data_name(self):
        node = factory.make_node()
        ncr1 = factory.make_node_commission_result(node=node, name="foo")
        node2 = factory.make_node()
        ncr2 = factory.make_node_commission_result(node=node2, name="foo")
        self.assertEqual(ncr1.name, ncr2.name)


class TestNodeCommissionResultManager(DjangoTestCase):
    """Test the manager utility for NodeCommissionResult."""

    def test_clear_results_removes_rows(self):
        # clear_results should remove all a node's results.
        node = factory.make_node()
        factory.make_node_commission_result(node=node)
        factory.make_node_commission_result(node=node)
        factory.make_node_commission_result(node=node)

        NodeCommissionResult.objects.clear_results(node)
        self.assertItemsEqual(
            [],
            NodeCommissionResult.objects.filter(node=node))

    def test_clear_results_ignores_other_nodes(self):
        # clear_results should only remove results for the supplied
        # node.
        node1 = factory.make_node()
        factory.make_node_commission_result(node=node1)
        node2 = factory.make_node()
        factory.make_node_commission_result(node=node2)

        NodeCommissionResult.objects.clear_results(node1)
        self.assertTrue(
            NodeCommissionResult.objects.filter(node=node2).exists())

    def test_store_data(self):
        node = factory.make_node()
        name = factory.getRandomString(100)
        data = factory.getRandomString(1024 * 1024)
        NodeCommissionResult.objects.store_data(
            node, name=name, data=data)

        results = NodeCommissionResult.objects.filter(node=node)
        [ncr] = results
        self.assertAttributes(ncr, dict(name=name, data=data))

    def test_store_data_updates_existing(self):
        node = factory.make_node()
        name = factory.getRandomString(100)
        factory.make_node_commission_result(node=node, name=name)
        data = factory.getRandomString(1024 * 1024)
        NodeCommissionResult.objects.store_data(
            node, name=name, data=data)

        results = NodeCommissionResult.objects.filter(node=node)
        [ncr] = results
        self.assertAttributes(ncr, dict(name=name, data=data))

    def test_get_data(self):
        ncr = factory.make_node_commission_result()
        result = NodeCommissionResult.objects.get_data(ncr.node, ncr.name)
        self.assertEqual(ncr.data, result)

    def test_get_data_404s_when_not_found(self):
        ncr = factory.make_node_commission_result()
        self.assertRaises(
            Http404,
            NodeCommissionResult.objects.get_data, ncr.node, "bad name")
