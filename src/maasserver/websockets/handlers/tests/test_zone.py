# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.zone`"""


from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db.models import Count

from maasserver.enum import NODE_TYPE
from maasserver.models.defaultresource import DefaultResource
from maasserver.models.zone import Zone
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.websockets.base import dehydrate_datetime
from maasserver.websockets.handlers.zone import ZoneHandler
from maastesting.djangotestcase import count_queries


class TestZoneHandler(MAASServerTestCase):
    def dehydrate_zone(self, zone):
        node_count_by_type = defaultdict(
            int,
            zone.node_set.values("node_type")
            .annotate(node_count=Count("node_type"))
            .values_list("node_type", "node_count"),
        )
        return {
            "id": zone.id,
            "name": zone.name,
            "description": zone.description,
            "updated": dehydrate_datetime(zone.updated),
            "created": dehydrate_datetime(zone.created),
            "devices_count": node_count_by_type[NODE_TYPE.DEVICE],
            "machines_count": node_count_by_type[NODE_TYPE.MACHINE],
            "controllers_count": (
                node_count_by_type[NODE_TYPE.RACK_CONTROLLER]
                + node_count_by_type[NODE_TYPE.REGION_CONTROLLER]
                + node_count_by_type[NODE_TYPE.REGION_AND_RACK_CONTROLLER]
            ),
        }

    def test_get(self):
        user = factory.make_User()
        handler = ZoneHandler(user, {}, None)
        zone = factory.make_Zone()
        for _ in range(3):
            factory.make_Node(zone=zone)
        for _ in range(3):
            factory.make_Device(zone=zone)
        for _ in range(3):
            factory.make_RackController(zone=zone)
        for _ in range(3):
            factory.make_RegionController(zone=zone)
        result = handler.get({"id": zone.id})
        self.assertEqual(self.dehydrate_zone(zone), result)
        self.assertEqual(3, result["machines_count"])
        self.assertEqual(3, result["devices_count"])
        self.assertEqual(6, result["controllers_count"])

    def test_get_query_count(self):
        user = factory.make_User()
        handler = ZoneHandler(user, {}, None)
        zone = factory.make_Zone()
        for _ in range(3):
            factory.make_Node(zone=zone)
        for _ in range(3):
            factory.make_Device(zone=zone)
        for _ in range(3):
            factory.make_RackController(zone=zone)
        for _ in range(3):
            factory.make_RegionController(zone=zone)
        count, _ = count_queries(handler.get, {"id": zone.id})
        self.assertEqual(count, 3)

    def test_list(self):
        user = factory.make_User()
        handler = ZoneHandler(user, {}, None)
        factory.make_Zone()
        expected_zones = [
            self.dehydrate_zone(zone) for zone in Zone.objects.all()
        ]
        self.assertCountEqual(expected_zones, handler.list({}))


class TestZoneHandlerDelete(MAASServerTestCase):
    def test_delete_as_admin_success(self):
        user = factory.make_admin()
        handler = ZoneHandler(user, {}, None)
        zone = factory.make_Zone()
        handler.delete({"id": zone.id})
        zone = reload_object(zone)
        self.assertIsNone(zone)

    def test_delete_as_non_admin_asserts(self):
        user = factory.make_User()
        handler = ZoneHandler(user, {}, None)
        zone = factory.make_Zone()
        with self.assertRaisesRegex(AssertionError, "Permission denied."):
            handler.delete({"id": zone.id})

    def test_delete_default_zone_fails(self):
        zone = DefaultResource.objects.get_default_zone()
        user = factory.make_admin()
        handler = ZoneHandler(user, {}, None)
        self.assertRaises(ValidationError, handler.delete, {"id": zone.id})
