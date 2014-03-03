# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
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

from maasserver.models import (
    Network,
    NodeGroup,
    )
from maasserver.testing import reload_object
from maasserver.testing.factory import factory
from maastesting.factory import TooManyRandomRetries
from maastesting.testcase import MAASTestCase


class FakeRandInt:
    """Fake `randint` which forced limitations on its range.

    This lets you set a forced minimum, and/or a forced maximum, on the range
    of any call.  For example, if you pass `forced_maximum=3`, then a call
    will never return more than 3.  If you don't set a maximum, or if the
    call's maximum argument is less than the forced maximum, then the call's
    maximum will be respected.
    """
    def __init__(self, real_randint, forced_minimum=None, forced_maximum=None):
        self.real_randint = real_randint
        self.minimum = forced_minimum
        self.maximum = forced_maximum

    def __call__(self, minimum, maximum):
        if self.minimum is not None:
            minimum = max(minimum, self.minimum)
        if self.maximum is not None:
            maximum = min(maximum, self.maximum)
        return self.real_randint(minimum, maximum)


class TestFactory(MAASTestCase):

    def test_getRandomEnum_returns_enum_value(self):
        random_value = random.randint(0, 99999)

        class Enum:
            VALUE = random_value
            OTHER_VALUE = random_value + 3

        self.assertIn(
            factory.getRandomEnum(Enum), [Enum.VALUE, Enum.OTHER_VALUE])

    def test_getRandomEnum_can_exclude_choices(self):
        random_value = random.randint(0, 99999)

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

    def test_make_zone_returns_physical_zone(self):
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

    def test_make_vlan_tag_excludes_None_by_default(self):
        # Artificially limit randint to a very narrow range, to guarantee
        # some repetition in its output, and virtually guarantee that we test
        # both outcomes of the flip-a-coin call in make_vlan_tag.
        self.patch(random, 'randint', FakeRandInt(random.randint, 0, 1))
        outcomes = {factory.make_vlan_tag() for _ in range(1000)}
        self.assertEqual({1}, outcomes)

    def test_make_vlan_tags_includes_None_if_allow_none(self):
        self.patch(random, 'randint', FakeRandInt(random.randint, 0, 1))
        self.assertEqual(
            {None, 1},
            {
                factory.make_vlan_tag(allow_none=True)
                for _ in range(1000)
            })

    def test_make_network_lowers_names_if_sortable_name(self):
        networks = factory.make_networks(10, sortable_name=True)
        self.assertEqual(
            [network.name.lower() for network in networks],
            [network.name for network in networks])

    def test_make_networks_generates_desired_number_of_networks(self):
        number = random.randint(1, 20)
        networks = factory.make_networks(number)
        self.assertEqual(number, len(networks))
        self.assertIsInstance(networks[0], Network)
        self.assertIsInstance(networks[-1], Network)

    def test_make_networks_passes_on_keyword_arguments(self):
        description = factory.getRandomString()
        [network] = factory.make_networks(1, description=description)
        self.assertEqual(description, network.description)

    def test_make_networks_includes_VLANs_by_default(self):
        class FakeNetwork:
            def __init__(self, vlan_tag, *args, **kwargs):
                self.vlan_tag = vlan_tag
        self.patch(factory, 'make_network', FakeNetwork)
        self.patch(random, 'randint', FakeRandInt(random.randint, 0, 1))
        networks = factory.make_networks(100)
        self.assertEqual({None, 1}, {network.vlan_tag for network in networks})

    def test_make_networks_excludes_VLANs_if_not_with_vlans(self):
        class FakeNetwork:
            def __init__(self, vlan_tag, *args, **kwargs):
                self.vlan_tag = vlan_tag
        self.patch(factory, 'make_network', FakeNetwork)
        self.patch(random, 'randint', FakeRandInt(random.randint, 0, 1))
        networks = factory.make_networks(100, with_vlans=False)
        self.assertEqual({None}, {network.vlan_tag for network in networks})

    def test_make_networks_gives_up_if_random_tags_keep_clashing(self):
        self.patch(factory, 'make_network')
        self.patch(random, 'randint', lambda *args: 1)
        self.assertRaises(TooManyRandomRetries, factory.make_networks, 2)
