# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test Zone objects."""


from maasserver.enum import NODE_TYPE
from maasserver.models.defaultresource import DefaultResource
from maasserver.models.zone import Zone
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestZoneManager(MAASServerTestCase):
    """Tests for `Zone` manager."""

    DEFAULT_ZONE_NAME = "default"

    def test_get_default_zone_returns_default_zone(self):
        self.assertEqual(
            self.DEFAULT_ZONE_NAME,
            DefaultResource.objects.get_default_zone().name,
        )

    def test_get_default_zone_ignores_other_zones(self):
        factory.make_Zone()
        self.assertEqual(
            self.DEFAULT_ZONE_NAME,
            DefaultResource.objects.get_default_zone().name,
        )

    def test_get_renamed_default_zone(self):
        default_zone = Zone.objects.get(name=self.DEFAULT_ZONE_NAME)
        default_zone.name = "myzone"
        default_zone.save()

        self.assertEqual(
            "myzone", DefaultResource.objects.get_default_zone().name
        )


class TestZone(MAASServerTestCase):
    """Tests for :class:`Zone`."""

    def test_init(self):
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        name = factory.make_name("name")
        description = factory.make_name("description")

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
            ({node1, node2}, name, description, zone, zone),
        )

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
        self.assertEqual(DefaultResource.objects.get_default_zone(), node.zone)

    def test_nodes_only_set(self):
        """zone.node_only_set has only type node."""
        zone = factory.make_Zone()
        node1 = factory.make_Node(zone=zone, node_type=NODE_TYPE.MACHINE)
        node2 = factory.make_Node(zone=zone, node_type=NODE_TYPE.MACHINE)
        node3 = factory.make_Node(zone=zone, node_type=NODE_TYPE.MACHINE)
        device1 = factory.make_Node(zone=zone, node_type=NODE_TYPE.DEVICE)
        device2 = factory.make_Node(zone=zone, node_type=NODE_TYPE.DEVICE)
        rack_controller = factory.make_Node(
            zone=zone, node_type=NODE_TYPE.RACK_CONTROLLER
        )
        self.assertEqual(zone.node_only_set.count(), 3)
        self.assertIn(node1, zone.node_only_set)
        self.assertIn(node2, zone.node_only_set)
        self.assertIn(node3, zone.node_only_set)
        self.assertNotIn(device1, zone.node_only_set)
        self.assertNotIn(device2, zone.node_only_set)
        self.assertNotIn(rack_controller, zone.node_only_set)

    def test_devices_only_set(self):
        """zone.devices_only_set has only type device."""
        zone = factory.make_Zone()
        node1 = factory.make_Node(zone=zone, node_type=NODE_TYPE.MACHINE)
        node2 = factory.make_Node(zone=zone, node_type=NODE_TYPE.MACHINE)
        node3 = factory.make_Node(zone=zone, node_type=NODE_TYPE.MACHINE)
        device1 = factory.make_Node(zone=zone, node_type=NODE_TYPE.DEVICE)
        device2 = factory.make_Node(zone=zone, node_type=NODE_TYPE.DEVICE)
        rack_controller = factory.make_Node(
            zone=zone, node_type=NODE_TYPE.RACK_CONTROLLER
        )
        self.assertEqual(zone.device_only_set.count(), 2)
        self.assertNotIn(node1, zone.device_only_set)
        self.assertNotIn(node2, zone.device_only_set)
        self.assertNotIn(node3, zone.device_only_set)
        self.assertIn(device1, zone.device_only_set)
        self.assertIn(device2, zone.device_only_set)
        self.assertNotIn(rack_controller, zone.node_only_set)

    def test_rack_controllers_only_set(self):
        """zone.rack_controllers_only_set has only type rack_controller."""
        zone = factory.make_Zone()
        node1 = factory.make_Node(zone=zone, node_type=NODE_TYPE.MACHINE)
        node2 = factory.make_Node(zone=zone, node_type=NODE_TYPE.MACHINE)
        node3 = factory.make_Node(zone=zone, node_type=NODE_TYPE.MACHINE)
        device1 = factory.make_Node(zone=zone, node_type=NODE_TYPE.DEVICE)
        device2 = factory.make_Node(zone=zone, node_type=NODE_TYPE.DEVICE)
        rack_controller = factory.make_Node(
            zone=zone, node_type=NODE_TYPE.RACK_CONTROLLER
        )
        self.assertEqual(zone.device_only_set.count(), 2)
        self.assertNotIn(node1, zone.rack_controller_only_set)
        self.assertNotIn(node2, zone.rack_controller_only_set)
        self.assertNotIn(node3, zone.rack_controller_only_set)
        self.assertNotIn(device1, zone.rack_controller_only_set)
        self.assertNotIn(device2, zone.rack_controller_only_set)
        self.assertIn(rack_controller, zone.rack_controller_only_set)
