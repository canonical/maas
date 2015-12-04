# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `Boot Images` API."""

__all__ = []

import http.client

from crochet import TimeoutError
from django.core.urlresolvers import reverse
from maasserver.api import boot_images as boot_images_module
from maasserver.clusterrpc.testing.boot_images import make_rpc_boot_image
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from provisioningserver.rpc.exceptions import NoConnectionsAvailable


class TestBootImagesAPI(APITestCase):
    """Test the the boot images API."""

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/nodegroups/uuid/boot-images/',
            reverse('boot_images_handler', args=['uuid']))

    def make_boot_image(self):
        rpc_image = make_rpc_boot_image()
        api_image = rpc_image.copy()
        del api_image['xinstall_type']
        del api_image['xinstall_path']
        return rpc_image, api_image

    def test_GET_returns_boot_image_list(self):
        nodegroup = factory.make_NodeGroup()
        rpc_images = []
        api_images = []
        for _ in range(3):
            rpc_image, api_image = self.make_boot_image()
            rpc_images.append(rpc_image)
            api_images.append(api_image)
        self.patch(
            boot_images_module, 'get_boot_images').return_value = rpc_images

        response = self.client.get(
            reverse('boot_images_handler', args=[nodegroup.uuid]))
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_result = json_load_bytes(response.content)
        self.assertItemsEqual(api_images, parsed_result)

    def test_GET_returns_404_when_invalid_nodegroup(self):
        uuid = factory.make_UUID()
        response = self.client.get(
            reverse('boot_images_handler', args=[uuid]))
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content)

    def test_GET_returns_503_when_no_connection_avaliable(self):
        nodegroup = factory.make_NodeGroup()
        mock_get_boot_images = self.patch(
            boot_images_module, 'get_boot_images')
        mock_get_boot_images.side_effect = NoConnectionsAvailable

        response = self.client.get(
            reverse('boot_images_handler', args=[nodegroup.uuid]))
        self.assertEqual(
            http.client.SERVICE_UNAVAILABLE,
            response.status_code, response.content)

    def test_GET_returns_503_when_timeout_error(self):
        nodegroup = factory.make_NodeGroup()
        mock_get_boot_images = self.patch(
            boot_images_module, 'get_boot_images')
        mock_get_boot_images.side_effect = TimeoutError

        response = self.client.get(
            reverse('boot_images_handler', args=[nodegroup.uuid]))
        self.assertEqual(
            http.client.SERVICE_UNAVAILABLE,
            response.status_code, response.content)
