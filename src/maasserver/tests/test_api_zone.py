# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for physical `Zone` API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import json

from django.core.urlresolvers import reverse
from maasserver.testing import reload_object
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory


def get_zone_uri(zone):
    """Return a zone's URI on the API."""
    return reverse('zone_handler', args=[zone.name])


class TestZoneAPI(APITestCase):

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/zones/name/', reverse('zone_handler', args=['name']))

    def test_POST_is_prohibited(self):
        self.become_admin()
        zone = factory.make_zone()
        response = self.client.post(
            get_zone_uri(zone),
            {
                'name': zone.name,
                'description': zone.description,
            })
        self.assertEqual(httplib.METHOD_NOT_ALLOWED, response.status_code)

    def test_GET_returns_zone(self):
        zone = factory.make_zone()
        response = self.client.get(get_zone_uri(zone))
        self.assertEqual(httplib.OK, response.status_code)
        returned_zone = json.loads(response.content)
        self.assertEqual(
            (zone.name, zone.description),
            (returned_zone['name'], returned_zone['description']))

    def test_PUT_updates_zone(self):
        self.become_admin()
        zone = factory.make_zone()
        new_description = factory.getRandomString()

        response = self.client_put(
            get_zone_uri(zone),
            {'description': new_description})
        self.assertEqual(httplib.OK, response.status_code)

        zone = reload_object(zone)
        self.assertEqual(new_description, zone.description)

    def test_PUT_requires_admin(self):
        zone = factory.make_zone()
        response = self.client_put(
            get_zone_uri(zone),
            {'description': factory.getRandomString()})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_PUT_updates_zone_name(self):
        self.become_admin()
        zone = factory.make_zone()
        new_name = factory.make_name('zone-new')

        response = self.client_put(get_zone_uri(zone), {'name': new_name})
        self.assertEqual(httplib.OK, response.status_code)

        zone = reload_object(zone)
        self.assertEqual(new_name, zone.name)

    def test_PUT_changing_name_maintains_foreign_keys(self):
        self.become_admin()
        zone = factory.make_zone()
        node = factory.make_node(zone=zone)

        response = self.client_put(
            get_zone_uri(zone),
            {'name': factory.make_name('new')})
        self.assertEqual(httplib.OK, response.status_code)

        node = reload_object(node)
        zone = reload_object(zone)
        self.assertEqual(zone, node.zone)

    def test_DELETE_removes_zone(self):
        self.become_admin()
        zone = factory.make_zone()
        response = self.client.delete(get_zone_uri(zone))
        self.assertEqual(httplib.NO_CONTENT, response.status_code)
        self.assertIsNone(reload_object(zone))

    def test_DELETE_requires_admin(self):
        zone = factory.make_zone()
        response = self.client.delete(get_zone_uri(zone))
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_DELETE_clears_foreign_keys(self):
        self.become_admin()
        zone = factory.make_zone()
        node = factory.make_node(zone=zone)

        response = self.client.delete(get_zone_uri(zone))
        self.assertEqual(httplib.NO_CONTENT, response.status_code)

        node = reload_object(node)
        self.assertIsNotNone(node)
        self.assertIsNone(node.zone)

    def test_DELETE_is_idempotent(self):
        self.become_admin()
        zone = factory.make_zone()
        response = self.client.delete(get_zone_uri(zone))
        self.assertEqual(httplib.NO_CONTENT, response.status_code)

        response = self.client.delete(get_zone_uri(zone))
        self.assertEqual(httplib.NO_CONTENT, response.status_code)
