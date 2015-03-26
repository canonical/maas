# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the :class:`NodeResult` model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from random import randint

from django.core.exceptions import ValidationError
from django.http import Http404
from maasserver.testing.factory import factory
from maasserver.utils.converters import XMLToYAML
from maastesting.djangotestcase import DjangoTestCase
from metadataserver.enum import RESULT_TYPE
from metadataserver.fields import Bin
from metadataserver.models import NodeResult
from metadataserver.models.commissioningscript import (
    LLDP_OUTPUT_NAME,
    LSHW_OUTPUT_NAME,
)


class TestNodeResult(DjangoTestCase):
    """Test the NodeResult model."""

    def test_unicode_represents_result(self):
        result = factory.make_NodeResult_for_commissioning()
        self.assertEqual(
            '%s/%s' % (result.node.system_id, result.name),
            unicode(result))

    def test_can_store_data(self):
        node = factory.make_Node()
        name = factory.make_string()
        data = factory.make_bytes()
        factory.make_NodeResult_for_commissioning(
            node=node, name=name, data=data)

        ncr = NodeResult.objects.get(name=name)
        self.assertAttributes(ncr, dict(node=node, data=data))

    def test_node_name_uniqueness(self):
        # You cannot have two result rows with the same name for the
        # same node.
        node = factory.make_Node()
        factory.make_NodeResult_for_commissioning(node=node, name="foo")
        self.assertRaises(
            ValidationError,
            factory.make_NodeResult_for_commissioning, node=node, name="foo")

    def test_different_nodes_can_have_same_data_name(self):
        node = factory.make_Node()
        ncr1 = factory.make_NodeResult_for_commissioning(
            node=node, name="foo")
        node2 = factory.make_Node()
        ncr2 = factory.make_NodeResult_for_commissioning(
            node=node2, name="foo")
        self.assertEqual(ncr1.name, ncr2.name)

    def test_get_data_as_html_returns_output(self):
        output = factory.make_string()
        result = factory.make_NodeResult_for_commissioning(
            data=output.encode('ascii'))
        self.assertEqual(output, result.get_data_as_html())

    def test_get_data_as_yaml_html_returns_output(self):
        data = "<data>bar</data>".encode("utf-8")
        expected = XMLToYAML(data).convert()
        lshw_result = factory.make_NodeResult_for_commissioning(
            name=LSHW_OUTPUT_NAME, script_result=0, data=data)
        lldp_result = factory.make_NodeResult_for_commissioning(
            name=LLDP_OUTPUT_NAME, script_result=0, data=data)
        self.assertEqual(expected, lshw_result.get_data_as_yaml_html())
        self.assertEqual(expected, lldp_result.get_data_as_yaml_html())

    def test_get_data_as_html_escapes_binary(self):
        output = b'\x00\xff'
        result = factory.make_NodeResult_for_commissioning(data=output)
        html = result.get_data_as_html()
        self.assertIsInstance(html, unicode)
        # The nul byte turns into the zero character.  The 0xff is an invalid
        # character and so becomes the Unicode "replacement character" 0xfffd.
        self.assertEqual('\x00\ufffd', html)

    def test_get_data_as_html_escapes_for_html(self):
        output = '<&>'
        result = factory.make_NodeResult_for_commissioning(
            data=output.encode('ascii'))
        self.assertEqual('&lt;&amp;&gt;', result.get_data_as_html())


class TestNodeResultManager(DjangoTestCase):
    """Test the manager utility for NodeResult."""

    def test_clear_results_removes_rows(self):
        # clear_results should remove all a node's results.
        node = factory.make_Node()
        factory.make_NodeResult_for_commissioning(node=node)
        factory.make_NodeResult_for_commissioning(node=node)
        factory.make_NodeResult_for_commissioning(node=node)

        NodeResult.objects.clear_results(node)
        self.assertItemsEqual(
            [],
            NodeResult.objects.filter(node=node))

    def test_clear_results_ignores_other_nodes(self):
        # clear_results should only remove results for the supplied
        # node.
        node1 = factory.make_Node()
        factory.make_NodeResult_for_commissioning(node=node1)
        node2 = factory.make_Node()
        factory.make_NodeResult_for_commissioning(node=node2)

        NodeResult.objects.clear_results(node1)
        self.assertTrue(
            NodeResult.objects.filter(node=node2).exists())

    def test_store_data(self):
        node = factory.make_Node()
        name = factory.make_string(255)
        data = factory.make_bytes(1024 * 1024)
        script_result = randint(0, 10)
        result = NodeResult.objects.store_data(
            node, name=name, script_result=script_result,
            result_type=RESULT_TYPE.COMMISSIONING, data=Bin(data))
        result_in_db = NodeResult.objects.get(node=node)

        self.assertAttributes(result_in_db, dict(name=name, data=data))
        # store_data() returns the model object.
        self.assertEqual(result, result_in_db)

    def test_store_data_updates_existing(self):
        node = factory.make_Node()
        name = factory.make_string(255)
        script_result = randint(0, 10)
        factory.make_NodeResult_for_commissioning(node=node, name=name)
        data = factory.make_bytes(1024 * 1024)
        NodeResult.objects.store_data(
            node, name=name, script_result=script_result,
            result_type=RESULT_TYPE.COMMISSIONING, data=Bin(data))

        self.assertAttributes(
            NodeResult.objects.get(node=node),
            dict(name=name, data=data, script_result=script_result))

    def test_get_data(self):
        ncr = factory.make_NodeResult_for_commissioning()
        result = NodeResult.objects.get_data(ncr.node, ncr.name)
        self.assertEqual(ncr.data, result)

    def test_get_data_404s_when_not_found(self):
        ncr = factory.make_NodeResult_for_commissioning()
        self.assertRaises(
            Http404,
            NodeResult.objects.get_data, ncr.node, "bad name")
