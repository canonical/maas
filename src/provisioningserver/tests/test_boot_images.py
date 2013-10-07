# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for reporting of boot images."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import json

from apiclient.maas_client import MAASClient
from mock import (
    Mock,
    sentinel,
    )
from provisioningserver import boot_images
from provisioningserver.pxe import tftppath
from provisioningserver.testing.boot_images import make_boot_image_params
from provisioningserver.testing.config import ConfigFixture
from provisioningserver.testing.testcase import PservTestCase


class TestBootImagesTasks(PservTestCase):

    def setUp(self):
        super(TestBootImagesTasks, self).setUp()
        self.useFixture(ConfigFixture({'tftp': {'root': self.make_dir()}}))

    def test_sends_boot_images_to_server(self):
        self.set_maas_url()
        self.set_api_credentials()
        image = make_boot_image_params()
        self.patch(tftppath, 'list_boot_images', Mock(return_value=[image]))
        get_cluster_uuid = self.patch(boot_images, "get_cluster_uuid")
        get_cluster_uuid.return_value = sentinel.uuid
        self.patch(MAASClient, 'post')
        boot_images.report_to_server()
        args, kwargs = MAASClient.post.call_args
        self.assertIs(sentinel.uuid, kwargs["nodegroup"])
        self.assertItemsEqual([image], json.loads(kwargs['images']))

    def test_does_nothing_without_credentials(self):
        self.set_maas_url()
        self.patch(
            tftppath, 'list_boot_images',
            Mock(return_value=make_boot_image_params()))
        boot_images.report_to_server()
        self.assertItemsEqual([], tftppath.list_boot_images.call_args_list)
