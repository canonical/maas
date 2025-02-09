# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for physical `Zone` API."""

import http.client
import json

from django.conf import settings
from django.urls import reverse

from maasserver.models import Zone
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory


class TestZonesAPI(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual("/MAAS/api/2.0/zones/", reverse("zones_handler"))

    def test_new_creates_zone(self):
        self.become_admin()
        name = factory.make_name("name")
        description = factory.make_name("description")
        response = self.client.post(
            reverse("zones_handler"),
            {"name": name, "description": description},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        zone = Zone.objects.get(name=name)
        self.assertEqual(name, zone.name)
        self.assertEqual(description, zone.description)

    def test_new_requires_admin(self):
        name = factory.make_name("name")
        description = factory.make_name("description")
        response = self.client.post(
            reverse("zones_handler"),
            {"name": name, "description": description},
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_list_returns_zone_list(self):
        [factory.make_Zone(sortable_name=True) for _ in range(3)]
        zones = Zone.objects.all()
        response = self.client.get(reverse("zones_handler"), {})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertCountEqual(
            [
                (
                    zone.name,
                    zone.description,
                    reverse("zone_handler", args=[zone.name]),
                )
                for zone in zones
            ],
            [
                (
                    zone.get("name"),
                    zone.get("description"),
                    zone.get("resource_uri"),
                )
                for zone in parsed_result
            ],
        )

    def test_list_returns_sorted_zone_list(self):
        [factory.make_Zone(sortable_name=True) for _ in range(10)]
        zones = Zone.objects.all()
        response = self.client.get(reverse("zones_handler"), {})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        # Sorting is case-insensitive.
        self.assertEqual(
            sorted((zone.name for zone in zones), key=lambda s: s.lower()),
            [zone.get("name") for zone in parsed_result],
        )
