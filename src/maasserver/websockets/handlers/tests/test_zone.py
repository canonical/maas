# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.zone`"""

__all__ = []

from maasserver.models.zone import Zone
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.handlers.timestampedmodel import dehydrate_datetime
from maasserver.websockets.handlers.zone import ZoneHandler


class TestZoneHandler(MAASServerTestCase):

    def dehydrate_zone(self, zone):
        data = {
            "id": zone.id,
            "name": zone.name,
            "description": zone.description,
            "updated": dehydrate_datetime(zone.updated),
            "created": dehydrate_datetime(zone.created),
            }
        return data

    def test_get(self):
        user = factory.make_User()
        handler = ZoneHandler(user, {})
        zone = factory.make_Zone()
        self.assertEqual(
            self.dehydrate_zone(zone),
            handler.get({"id": zone.id}))

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
