# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for physical `Zone` API."""

import http.client
import json

from django.conf import settings
from django.urls import reverse

from maasserver.models.defaultresource import DefaultResource
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.orm import reload_object


def get_zone_uri(zone):
    """Return a zone's URI on the API."""
    return reverse("zone_handler", args=[zone.name])


class TestZoneAPI(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/zones/name/", reverse("zone_handler", args=["name"])
        )

    def test_POST_is_prohibited(self):
        self.become_admin()
        zone = factory.make_Zone()
        response = self.client.post(
            get_zone_uri(zone),
            {"name": zone.name, "description": zone.description},
        )
        self.assertEqual(http.client.METHOD_NOT_ALLOWED, response.status_code)

    def test_GET_returns_zone(self):
        zone = factory.make_Zone()
        response = self.client.get(get_zone_uri(zone))
        self.assertEqual(http.client.OK, response.status_code)
        returned_zone = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            (zone.name, zone.description),
            (returned_zone["name"], returned_zone["description"]),
        )

    def test_PUT_updates_zone(self):
        self.become_admin()
        zone = factory.make_Zone()
        new_description = factory.make_string()

        response = self.client.put(
            get_zone_uri(zone), {"description": new_description}
        )
        self.assertEqual(http.client.OK, response.status_code)

        zone = reload_object(zone)
        self.assertEqual(new_description, zone.description)

    def test_PUT_requires_admin(self):
        zone = factory.make_Zone()
        response = self.client.put(
            get_zone_uri(zone), {"description": factory.make_string()}
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_PUT_updates_zone_name(self):
        self.become_admin()
        zone = factory.make_Zone()
        new_name = factory.make_name("zone-new")

        response = self.client.put(get_zone_uri(zone), {"name": new_name})
        self.assertEqual(http.client.OK, response.status_code)

        zone = reload_object(zone)
        self.assertEqual(new_name, zone.name)

    def test_PUT_rejects_change_of_default_zone_name(self):
        self.become_admin()
        zone = DefaultResource.objects.get_default_zone()
        new_name = factory.make_name("zone")
        response = self.client.put(get_zone_uri(zone), {"name": new_name})
        self.assertEqual(http.client.OK, response.status_code)
        zone = reload_object(zone)
        self.assertEqual(new_name, zone.name)

    def test_PUT_changing_name_maintains_foreign_keys(self):
        self.become_admin()
        zone = factory.make_Zone()
        node = factory.make_Node(zone=zone)

        response = self.client.put(
            get_zone_uri(zone), {"name": factory.make_name("new")}
        )
        self.assertEqual(http.client.OK, response.status_code)

        node = reload_object(node)
        zone = reload_object(zone)
        self.assertEqual(zone, node.zone)

    def test_DELETE_removes_zone(self):
        self.become_admin()
        zone = factory.make_Zone()
        response = self.client.delete(get_zone_uri(zone))
        self.assertEqual(http.client.NO_CONTENT, response.status_code)
        self.assertIsNone(reload_object(zone))

    def test_DELETE_rejects_deletion_of_default_zone(self):
        self.become_admin()
        response = self.client.delete(
            get_zone_uri(DefaultResource.objects.get_default_zone())
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertIsNotNone(DefaultResource.objects.get_default_zone())

    def test_DELETE_requires_admin(self):
        zone = factory.make_Zone()
        response = self.client.delete(get_zone_uri(zone))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_DELETE_cannot_delete_default_zone(self):
        self.become_admin()
        zone = DefaultResource.objects.get_default_zone()

        response = self.client.delete(get_zone_uri(zone))

        self.assertEqual(
            (
                http.client.BAD_REQUEST.value,
                "This zone is the default zone, it cannot be deleted.",
            ),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_DELETE_sets_foreign_keys_to_default(self):
        default_zone = DefaultResource.objects.get_default_zone()
        self.become_admin()
        zone = factory.make_Zone()
        node = factory.make_Node(zone=zone)

        response = self.client.delete(get_zone_uri(zone))
        self.assertEqual(http.client.NO_CONTENT, response.status_code)

        node = reload_object(node)
        self.assertIsNotNone(node)
        self.assertEqual(default_zone, node.zone)

    def test_DELETE_is_idempotent(self):
        self.become_admin()
        zone = factory.make_Zone()
        response = self.client.delete(get_zone_uri(zone))
        self.assertEqual(http.client.NO_CONTENT, response.status_code)

        response = self.client.delete(get_zone_uri(zone))
        self.assertEqual(http.client.NO_CONTENT, response.status_code)
