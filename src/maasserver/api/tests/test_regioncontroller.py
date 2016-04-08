# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Region Controller API."""

from django.core.urlresolvers import reverse
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes


class TestRegionControllerAPI(APITestCase):
    """Tests for /api/2.0/regioncontrollers/<region>/."""

    def test_handler_path(self):
        self.assertEqual(
            '/api/2.0/regioncontrollers/region-name/',
            reverse('regioncontroller_handler', args=['region-name']))


class TestRegionControllersAPI(APITestCase):
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
                'resource_uri',
                'distro_series',
                'interface_set',
                'ip_addresses',
                'zone',
                'status_action',
                'node_type',
                'node_type_name',
            ],
            list(parsed_result[0]))
