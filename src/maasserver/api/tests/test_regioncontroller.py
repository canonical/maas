# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Region Controller API."""

import http.client

from django.core.urlresolvers import reverse
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object


class TestRegionControllerAPI(APITestCase.ForUser):
    """Tests for /api/2.0/regioncontrollers/<region>/."""

    def test_handler_path(self):
        self.assertEqual(
            '/api/2.0/regioncontrollers/region-name/',
            reverse('regioncontroller_handler', args=['region-name']))

    @staticmethod
    def get_region_uri(region):
        """Get the API URI for `region`."""
        return reverse('regioncontroller_handler', args=[region.system_id])

    def test_PUT_updates_region_controller(self):
        self.become_admin()
        region = factory.make_RegionController()
        zone = factory.make_zone()
        response = self.client.put(
            self.get_region_uri(region), {'zone': zone.name})
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(zone.name, reload_object(region).zone.name)

    def test_PUT_requires_admin(self):
        region = factory.make_RegionController()
        response = self.client.put(self.get_region_uri(region), {})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)


class TestRegionControllersAPI(APITestCase.ForUser):
    """Tests for /api/2.0/regioncontrollers/."""

    @staticmethod
    def get_region_uri():
        """Get the API URI for `region`."""
        return reverse('regioncontrollers_handler')

    def test_handler_path(self):
        self.assertEqual(
            '/api/2.0/regioncontrollers/',
            reverse('regioncontrollers_handler'))

    def test_read_returns_limited_fields(self):
        self.become_admin()
        factory.make_RegionController()
        response = self.client.get(reverse('regioncontrollers_handler'))
        parsed_result = json_load_bytes(response.content)
        self.assertItemsEqual(
            [
                'system_id',
                'hostname',
                'domain',
                'fqdn',
                'architecture',
                'cpu_count',
                'memory',
                'swap_size',
                'osystem',
                'power_state',
                'power_type',
                'resource_uri',
                'distro_series',
                'interface_set',
                'ip_addresses',
                'zone',
                'status_action',
                'node_type',
                'node_type_name',
                'current_commissioning_result_id',
                'current_testing_result_id',
                'current_installation_result_id',
            ],
            list(parsed_result[0]))
