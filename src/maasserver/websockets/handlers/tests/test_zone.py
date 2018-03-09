# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.zone`"""

__all__ = []

from django.core.exceptions import ValidationError
from maasserver.enum import NODE_TYPE
from maasserver.models.zone import Zone
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.websockets.base import dehydrate_datetime
from maasserver.websockets.handlers.zone import ZoneHandler
from testtools import ExpectedException
from testtools.matchers import Equals


class TestZoneHandler(MAASServerTestCase):

    def dehydrate_zone(self, zone):
        data = {
            "id": zone.id,
            "name": zone.name,
            "description": zone.description,
            "updated": dehydrate_datetime(zone.updated),
            "created": dehydrate_datetime(zone.created),
            "devices_count": len([
                node
                for node in zone.node_set.all()
                if node.node_type == NODE_TYPE.DEVICE
            ]),
            "machines_count": len([
                node
                for node in zone.node_set.all()
                if node.node_type == NODE_TYPE.MACHINE
            ]),
            "controllers_count": len([
                node
                for node in zone.node_set.all()
                if (
                    node.node_type == NODE_TYPE.RACK_CONTROLLER or
                    node.node_type == NODE_TYPE.REGION_CONTROLLER or
                    node.node_type == NODE_TYPE.REGION_AND_RACK_CONTROLLER)
            ]),
        }
        return data

    def test_get(self):
        user = factory.make_User()
        handler = ZoneHandler(user, {})
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
        self.assertEqual(
            self.dehydrate_zone(zone), result)
        self.assertEquals(3, result['machines_count'])
        self.assertEquals(3, result['devices_count'])
        self.assertEquals(6, result['controllers_count'])

    def test_list(self):
        user = factory.make_User()
        handler = ZoneHandler(user, {})
        factory.make_Zone()
        expected_zones = [
            self.dehydrate_zone(zone)
            for zone in Zone.objects.all()
            ]
        self.assertItemsEqual(
            expected_zones,
            handler.list({}))


class TestZoneHandlerDelete(MAASServerTestCase):

    def test__delete_as_admin_success(self):
        user = factory.make_admin()
        handler = ZoneHandler(user, {})
        zone = factory.make_Zone()
        handler.delete({
            "id": zone.id,
        })
        zone = reload_object(zone)
        self.assertThat(zone, Equals(None))

    def test__delete_as_non_admin_asserts(self):
        user = factory.make_User()
        handler = ZoneHandler(user, {})
        zone = factory.make_Zone()
        with ExpectedException(AssertionError, "Permission denied."):
            handler.delete({
                "id": zone.id,
            })

    def test__delete_default_zone_fails(self):
        zone = Zone.objects.get_default_zone()
        user = factory.make_admin()
        handler = ZoneHandler(user, {})
        with ExpectedException(ValidationError):
            handler.delete({
                "id": zone.id,
            })
