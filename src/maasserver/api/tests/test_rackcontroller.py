# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Rack Controller API."""

import http.client

from django.core.urlresolvers import reverse
from maasserver.models import node as node_module
from maasserver.testing.api import (
    APITestCase,
    explain_unexpected_response,
)
from maasserver.testing.factory import factory
from maastesting.matchers import MockCalledOnceWith


class TestRackControllerAPI(APITestCase):
    """Tests for /api/2.0/rackcontrollers/<rack>/."""

    def test_handler_path(self):
        self.assertEqual(
            '/api/2.0/rackcontrollers/rack-name/',
            reverse('rackcontroller_handler', args=['rack-name']))

    @staticmethod
    def get_rack_uri(rack):
        """Get the API URI for `rack`."""
        return reverse('rackcontroller_handler', args=[rack.system_id])

    def test_POST_refresh_checks_permission(self):
        self.patch(node_module.RackController, 'refresh')
        rack = factory.make_RackController(owner=factory.make_User())
        response = self.client.post(self.get_rack_uri(rack), {'op': 'refresh'})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_POST_refresh_returns_null(self):
        self.patch(node_module.RackController, 'refresh')
        self.become_admin()
        rack = factory.make_RackController(owner=factory.make_User())
        response = self.client.post(self.get_rack_uri(rack), {'op': 'refresh'})
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            ('Refresh of %s has begun' % rack.hostname).encode('utf-8'),
            response.content)

    def test_POST_import_boot_images_import_to_rack_controllers(self):
        from maasserver.clusterrpc import boot_images
        self.patch(boot_images, "ClustersImporter")
        self.become_admin()
        rack = factory.make_RackController(owner=factory.make_User())
        response = self.client.post(
            self.get_rack_uri(rack), {'op': 'import_boot_images'})
        self.assertEqual(
            http.client.OK, response.status_code,
            explain_unexpected_response(http.client.OK, response))
        self.assertThat(
            boot_images.ClustersImporter.schedule,
            MockCalledOnceWith(rack.system_id))

    def test_POST_import_boot_images_denied_if_not_admin(self):
        rack = factory.make_RackController(owner=factory.make_User())
        response = self.client.post(
            self.get_rack_uri(rack), {'op': 'import_boot_images'})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code,
            explain_unexpected_response(http.client.FORBIDDEN, response))


class TestRackControllersAPI(APITestCase):
    """Tests for /api/2.0/rackcontrollers/."""

    def test_handler_path(self):
        self.assertEqual(
            '/api/2.0/rackcontrollers/', reverse('rackcontrollers_handler'))

    @staticmethod
    def get_rack_uri(rack):
        """Get the API URI for `rack`."""
        return reverse('rackcontrollers_handler')
