# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :class:`NodeUserData` and manager."""

from maasserver.models import NodeUserData
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestNodeUserDataManager(MAASServerTestCase):
    """Test NodeUserDataManager."""

    def test_set_user_data_creates_new_nodeuserdata_if_needed(self):
        node = factory.make_Node()
        data = b"foo"
        NodeUserData.objects.set_user_data(node, data)
        self.assertEqual(data, NodeUserData.objects.get(node=node).data)

    def test_set_user_data_overwrites_existing_userdata(self):
        node = factory.make_Node()
        data = b"bar"
        NodeUserData.objects.set_user_data(node, b"old data")
        NodeUserData.objects.set_user_data(node, data)
        self.assertEqual(data, NodeUserData.objects.get(node=node).data)

    def test_set_user_data_leaves_data_for_other_nodes_alone(self):
        node = factory.make_Node()
        NodeUserData.objects.set_user_data(node, b"intact")
        NodeUserData.objects.set_user_data(factory.make_Node(), b"unrelated")
        self.assertEqual(b"intact", NodeUserData.objects.get(node=node).data)

    def test_set_user_data_to_None_removes_user_data(self):
        node = factory.make_Node()
        NodeUserData.objects.set_user_data(node, b"original")
        NodeUserData.objects.set_user_data(node, None)
        self.assertCountEqual([], NodeUserData.objects.filter(node=node))

    def test_set_user_data_to_None_when_none_exists_does_nothing(self):
        node = factory.make_Node()
        NodeUserData.objects.set_user_data(node, None)
        self.assertCountEqual([], NodeUserData.objects.filter(node=node))

    def test_get_user_data_retrieves_data(self):
        node = factory.make_Node()
        data = b"splat"
        NodeUserData.objects.set_user_data(node, data)
        self.assertEqual(data, NodeUserData.objects.get_user_data(node))

    def test_get_user_data_raises_DoesNotExist_if_not_found(self):
        node = factory.make_Node()
        self.assertRaises(
            NodeUserData.DoesNotExist, NodeUserData.objects.get_user_data, node
        )

    def test_get_user_data_ignores_other_nodes(self):
        node = factory.make_Node()
        data = b"bzzz"
        NodeUserData.objects.set_user_data(node, data)
        NodeUserData.objects.set_user_data(factory.make_Node(), b"unrelated")
        self.assertEqual(data, NodeUserData.objects.get_user_data(node))

    def test_has_user_data_returns_False_if_node_has_no_user_data(self):
        self.assertFalse(
            NodeUserData.objects.has_user_data(factory.make_Node())
        )

    def test_has_user_data_returns_True_if_node_has_user_data(self):
        node = factory.make_Node()
        NodeUserData.objects.set_user_data(node, b"This node has user data.")
        self.assertTrue(NodeUserData.objects.has_user_data(node))

    def test_bulk_set_user_data(self):
        nodes = [factory.make_Node() for _ in range(5)]
        data = factory.make_bytes()
        NodeUserData.objects.bulk_set_user_data(nodes, data)
        for node in nodes:
            self.assertEqual(data, NodeUserData.objects.get_user_data(node))

    def test_bulk_set_user_data_only_deletes_when_data_is_None(self):
        nodes = [factory.make_Node() for _ in range(5)]
        NodeUserData.objects.bulk_set_user_data(nodes, None)
        for node in nodes:
            self.assertRaises(
                NodeUserData.DoesNotExist,
                NodeUserData.objects.get_user_data,
                node,
            )

    def test_bulk_set_user_data_with_preexisting_data(self):
        nodes = [factory.make_Node() for _ in range(2)]
        data1 = factory.make_bytes()
        NodeUserData.objects.bulk_set_user_data(nodes, data1)
        nodes.extend(factory.make_Node() for _ in range(3))
        data2 = factory.make_bytes()
        NodeUserData.objects.bulk_set_user_data(nodes, data2)
        for node in nodes:
            self.assertEqual(data2, NodeUserData.objects.get_user_data(node))
