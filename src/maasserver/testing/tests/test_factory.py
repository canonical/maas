# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the factory where appropriate.  Don't overdo this."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random

from maasserver.models import NodeGroup
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase


class TestFactory(MAASServerTestCase):

    def test_pick_enum_returns_enum_value(self):
        random_value = random.randint(0, 99999)

        class Enum:
            VALUE = random_value
            OTHER_VALUE = random_value + 3

        self.assertIn(factory.pick_enum(Enum), [Enum.VALUE, Enum.OTHER_VALUE])

    def test_pick_enum_can_exclude_choices(self):
        random_value = random.randint(0, 99999)

        class Enum:
            FIRST_VALUE = random_value
            SECOND_VALUE = random_value + 1
            THIRD_VALUE = random_value + 2

        self.assertEqual(
            Enum.FIRST_VALUE,
            factory.pick_enum(
                Enum, but_not=(Enum.SECOND_VALUE, Enum.THIRD_VALUE)))

    def test_pick_choice_chooses_from_django_options(self):
        options = [(2, 'b'), (10, 'j')]
        self.assertIn(
            factory.pick_choice(options),
            [option[0] for option in options])

    def test_pick_choice_can_exclude_choices(self):
        options = [(2, 'b'), (10, 'j')]
        but_not = [2]
        self.assertEqual(
            10, factory.pick_choice(options, but_not=but_not))

    def test_make_Node_creates_nodegroup_if_none_given(self):
        existing_nodegroup_ids = set(
            nodegroup.id for nodegroup in NodeGroup.objects.all())
        new_node = factory.make_Node()
        self.assertIsNotNone(new_node.nodegroup)
        self.assertNotIn(new_node.nodegroup.id, existing_nodegroup_ids)

    def test_make_Node_uses_given_nodegroup(self):
        nodegroup = factory.make_NodeGroup()
        self.assertEqual(
            nodegroup, factory.make_Node(nodegroup=nodegroup).nodegroup)

    def test_make_Zone_returns_physical_zone(self):
        self.assertIsNotNone(factory.make_Zone())

    def test_make_Zone_assigns_name(self):
        name = factory.make_Zone().name
        self.assertIsNotNone(name)
        self.assertNotEqual(0, len(name))

    def test_make_Zone_returns_unique_zone(self):
        self.assertNotEqual(factory.make_Zone(), factory.make_Zone())

    def test_make_Zone_adds_nodes(self):
        node = factory.make_Node()
        zone = factory.make_Zone(nodes=[node])
        node = reload_object(node)
        self.assertEqual(zone, node.zone)

    def test_make_Zone_does_not_add_other_nodes(self):
        previous_zone = factory.make_Zone()
        node = factory.make_Node(zone=previous_zone)
        factory.make_Zone(nodes=[factory.make_Node()])
        node = reload_object(node)
        self.assertEqual(previous_zone, node.zone)

    def test_make_Zone_adds_no_nodes_by_default(self):
        previous_zone = factory.make_Zone()
        node = factory.make_Node(zone=previous_zone)
        factory.make_Zone()
        node = reload_object(node)
        self.assertEqual(previous_zone, node.zone)
