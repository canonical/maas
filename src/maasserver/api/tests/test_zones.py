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
from maasserver.models import Zone
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory


class TestZonesAPI(APITestCase):

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/zones/', reverse('zones_handler'))

    def test_new_creates_zone(self):
        self.become_admin()
        name = factory.make_name('name')
        description = factory.make_name('description')
        response = self.client.post(
            reverse('zones_handler'),
            {
                'name': name,
                'description': description,
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        zones = Zone.objects.filter(name=name)
        self.assertItemsEqual(
            [(name, description)],
            [(zone.name, zone.description) for zone in zones])

    def test_new_requires_admin(self):
        name = factory.make_name('name')
        description = factory.make_name('description')
        response = self.client.post(
            reverse('zones_handler'),
            {
                'name': name,
                'description': description,
            })
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_list_returns_zone_list(self):
        [factory.make_zone(sortable_name=True) for i in range(3)]
        zones = Zone.objects.all()
        response = self.client.get(
            reverse('zones_handler'),
            {})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [(
                zone.name,
                zone.description,
                reverse('zone_handler', args=[zone.name]))
             for zone in zones],
            [(
                zone.get('name'),
                zone.get('description'),
                zone.get('resource_uri'))
             for zone in parsed_result])

    def test_list_returns_sorted_zone_list(self):
        [factory.make_zone(sortable_name=True) for i in range(10)]
        zones = Zone.objects.all()
        response = self.client.get(
            reverse('zones_handler'),
            {})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        # Sorting is case-insensitive.
        self.assertEqual(
            sorted(
                [
                    zone.name
                    for zone in zones
                ], key=lambda s: s.lower()),
            [zone.get('name') for zone in parsed_result])
