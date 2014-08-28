# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `boot_images` module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os

from maasserver.clusterrpc.boot_images import get_boot_images
from maasserver.enum import NODEGROUP_STATUS
from maasserver.rpc.testing.fixtures import RunningClusterRPCFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.boot.tests import test_tftppath
from provisioningserver.boot.tftppath import (
    compose_image_path,
    locate_tftp_path,
    )
from provisioningserver.testing.boot_images import (
    make_boot_image_storage_params,
    )
from provisioningserver.testing.config import set_tftp_root


class TestGetBootImages(MAASServerTestCase):
    """Tests for `get_boot_images`."""

    def setUp(self):
        super(TestGetBootImages, self).setUp()
        self.tftproot = self.make_dir()
        self.useFixture(set_tftp_root(self.tftproot))

    def make_image_dir(self, image_params):
        """Fake a boot image matching `image_params` under `tftproot`."""
        image_dir = locate_tftp_path(
            compose_image_path(
                osystem=image_params['osystem'],
                arch=image_params['architecture'],
                subarch=image_params['subarchitecture'],
                release=image_params['release'],
                label=image_params['label']),
            self.tftproot)
        os.makedirs(image_dir)
        factory.make_file(image_dir, 'linux')
        factory.make_file(image_dir, 'initrd.gz')

    def test_returns_boot_images(self):
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        self.useFixture(RunningClusterRPCFixture())

        purposes = ['install', 'commissioning', 'xinstall']
        params = [make_boot_image_storage_params() for _ in range(3)]
        for param in params:
            self.make_image_dir(param)
            test_tftppath.make_osystem(self, param['osystem'], purposes)
        self.assertItemsEqual(
            [
                test_tftppath.make_image(param, purpose)
                for param in params
                for purpose in purposes
            ],
            get_boot_images(nodegroup))
