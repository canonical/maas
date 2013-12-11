# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
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

from random import randint

from maasserver.models import NodeGroup
from maasserver.testing import reload_object
from maasserver.testing.factory import factory
from maastesting.testcase import MAASTestCase


class TestFactory(MAASTestCase):

    def test_getRandomEnum_returns_enum_value(self):
        random_value = randint(0, 99999)

        class Enum:
            VALUE = random_value
            OTHER_VALUE = random_value + 3

        self.assertIn(
            factory.getRandomEnum(Enum), [Enum.VALUE, Enum.OTHER_VALUE])

    def test_getRandomEnum_can_exclude_choices(self):
        random_value = randint(0, 99999)

        class Enum:
            FIRST_VALUE = random_value
            SECOND_VALUE = random_value + 1
            THIRD_VALUE = random_value + 2

        self.assertEqual(
            Enum.FIRST_VALUE,
            factory.getRandomEnum(
                Enum, but_not=(Enum.SECOND_VALUE, Enum.THIRD_VALUE)))

    def test_getRandomChoice_chooses_from_django_options(self):
        options = [(2, 'b'), (10, 'j')]
        self.assertIn(
            factory.getRandomChoice(options),
            [option[0] for option in options])

    def test_getRandomChoice_can_exclude_choices(self):
        options = [(2, 'b'), (10, 'j')]
        but_not = [2]
        self.assertEqual(
            10, factory.getRandomChoice(options, but_not=but_not))

    def test_make_node_creates_nodegroup_if_none_given(self):
        existing_nodegroup_ids = set(
            nodegroup.id for nodegroup in NodeGroup.objects.all())
        new_node = factory.make_node()
        self.assertIsNotNone(new_node.nodegroup)
        self.assertNotIn(new_node.nodegroup.id, existing_nodegroup_ids)

    def test_make_node_uses_given_nodegroup(self):
        nodegroup = factory.make_node_group()
        self.assertEqual(
            nodegroup, factory.make_node(nodegroup=nodegroup).nodegroup)

    def test_make_zone_returns_availability_zone(self):
        self.assertIsNotNone(factory.make_zone())

    def test_make_zone_assigns_name(self):
        name = factory.make_zone().name
        self.assertIsNotNone(name)
        self.assertNotEqual(0, len(name))

    def test_make_zone_returns_unique_zone(self):
        self.assertNotEqual(factory.make_zone(), factory.make_zone())

    def test_make_zone_adds_nodes(self):
        node = factory.make_node()
        zone = factory.make_zone(nodes=[node])
        node = reload_object(node)
        self.assertEqual(zone, node.zone)

    def test_make_zone_does_not_add_other_nodes(self):
        previous_zone = factory.make_zone()
        node = factory.make_node(zone=previous_zone)
        factory.make_zone(nodes=[factory.make_node()])
        node = reload_object(node)
        self.assertEqual(previous_zone, node.zone)

    def test_make_zone_adds_no_nodes_by_default(self):
        previous_zone = factory.make_zone()
        node = factory.make_node(zone=previous_zone)
        factory.make_zone()
        node = reload_object(node)
        self.assertEqual(previous_zone, node.zone)
