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
from metadataserver.models import NodeCommissionResult


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
