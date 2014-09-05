# Copyright 2013-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test Zone objects."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.models.zone import (
    DEFAULT_ZONE_NAME,
    Zone,
    )
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase


class TestZoneManager(MAASServerTestCase):
    """Tests for `Zone` manager."""

    def test_get_default_zone_returns_default_zone(self):
        self.assertEqual(
            DEFAULT_ZONE_NAME, Zone.objects.get_default_zone().name)

    def test_get_default_zone_ignores_other_zones(self):
        factory.make_Zone()
        self.assertEqual(
            DEFAULT_ZONE_NAME, Zone.objects.get_default_zone().name)


class TestZone(MAASServerTestCase):
    """Tests for :class:`Zone`."""

    def test_init(self):
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        name = factory.make_name('name')
        description = factory.make_name('description')

        zone = Zone(name=name, description=description)
        zone.save()
        zone.node_set.add(node1)
        zone.node_set.add(node2)

        self.assertEqual(
            (
                set(zone.node_set.all()),
                zone.name,
                zone.description,
                node1.zone,
                node2.zone,
            ),
            (set([node1, node2]), name, description, zone, zone))

    def test_delete_deletes_zone(self):
        zone = factory.make_Zone()
        zone.delete()
        self.assertIsNone(reload_object(zone))

    def test_delete_severs_link_to_nodes(self):
        zone = factory.make_Zone()
        node = factory.make_Node(zone=zone)
        zone.delete()
        self.assertIsNone(reload_object(zone))
        node = reload_object(node)
        self.assertIsNotNone(node)
        self.assertEqual(Zone.objects.get_default_zone(), node.zone)

    def test_is_default_returns_True_for_default_zone(self):
        self.assertTrue(Zone.objects.get_default_zone().is_default())

    def test_is_default_returns_False_for_normal_zone(self):
        self.assertFalse(factory.make_Zone().is_default())
