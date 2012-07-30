# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the factory where appropriate.  Don't overdo this."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from random import randint

from maasserver.models import NodeGroup
from maasserver.testing.factory import factory
from maastesting.testcase import TestCase


class TestFactory(TestCase):

    def test_getRandomEnum_returns_enum_value(self):
        random_value = randint(0, 99999)

        class Enum:
            VALUE = random_value
            OTHER_VALUE = random_value + 3

        self.assertIn(
            factory.getRandomEnum(Enum), [Enum.VALUE, Enum.OTHER_VALUE])

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
