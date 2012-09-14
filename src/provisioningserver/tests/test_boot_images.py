# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for reporting of boot images."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import json

from apiclient.maas_client import MAASClient
from apiclient.testing.credentials import make_api_credentials
from maastesting.factory import factory
from mock import Mock
from provisioningserver import boot_images
from provisioningserver.auth import (
    record_api_credentials,
    record_maas_url,
    )
from provisioningserver.pxe import tftppath
from provisioningserver.testing.boot_images import make_boot_image_params
from provisioningserver.testing.config import ConfigFixture
from provisioningserver.testing.testcase import PservTestCase


class TestBootImagesTasks(PservTestCase):

    def setUp(self):
        super(TestBootImagesTasks, self).setUp()
        self.useFixture(ConfigFixture({'tftp': {'root': self.make_dir()}}))

    def set_maas_url(self):
        record_maas_url(
            'http://127.0.0.1/%s' % factory.make_name('path'))

    def set_api_credentials(self):
        record_api_credentials(':'.join(make_api_credentials()))

    def test_sends_boot_images_to_server(self):
        self.set_maas_url()
        self.set_api_credentials()
        image = make_boot_image_params()
        self.patch(tftppath, 'list_boot_images', Mock(return_value=[image]))
        self.patch(MAASClient, 'post')

        boot_images.report_to_server()

        self.assertItemsEqual(
            [image],
            json.loads(MAASClient.post.call_args[1]['images']))

    def test_does_nothing_without_maas_url(self):
        self.set_api_credentials()
        self.patch(
            tftppath, 'list_boot_images',
            Mock(return_value=make_boot_image_params()))
        boot_images.report_to_server()
        self.assertItemsEqual([], tftppath.list_boot_images.call_args_list)

    def test_does_nothing_without_credentials(self):
        self.set_maas_url()
        self.patch(
            tftppath, 'list_boot_images',
            Mock(return_value=make_boot_image_params()))
        boot_images.report_to_server()
        self.assertItemsEqual([], tftppath.list_boot_images.call_args_list)
