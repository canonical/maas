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

from maasserver.clusterrpc.boot_images import (
    get_boot_images,
    get_boot_images_for,
    )
from maasserver.enum import (
    BOOT_RESOURCE_TYPE,
    NODEGROUP_STATUS,
    )
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
    make_image,
    )
from provisioningserver.testing.config import set_tftp_root


def make_image_dir(image_params, tftproot):
    """Fake a boot image matching `image_params` under `tftproot`."""
    image_dir = locate_tftp_path(
        compose_image_path(
            osystem=image_params['osystem'],
            arch=image_params['architecture'],
            subarch=image_params['subarchitecture'],
            release=image_params['release'],
            label=image_params['label']),
        tftproot)
    os.makedirs(image_dir)
    factory.make_file(image_dir, 'linux')
    factory.make_file(image_dir, 'initrd.gz')


class TestGetBootImages(MAASServerTestCase):
    """Tests for `get_boot_images`."""

    def setUp(self):
        super(TestGetBootImages, self).setUp()
        self.tftproot = self.make_dir()
        self.useFixture(set_tftp_root(self.tftproot))

    def test_returns_boot_images(self):
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        self.useFixture(RunningClusterRPCFixture())

        purposes = ['install', 'commissioning', 'xinstall']
        params = [make_boot_image_storage_params() for _ in range(3)]
        for param in params:
            make_image_dir(param, self.tftproot)
            test_tftppath.make_osystem(self, param['osystem'], purposes)
        self.assertItemsEqual(
            [
                make_image(param, purpose)
                for param in params
                for purpose in purposes
            ],
            get_boot_images(nodegroup))


class TestGetBootImagesFor(MAASServerTestCase):
    """Tests for `get_boot_images_for`."""

    def setUp(self):
        super(TestGetBootImagesFor, self).setUp()
        self.tftproot = self.make_dir()
        self.useFixture(set_tftp_root(self.tftproot))

    def make_boot_images(self):
        purposes = ['install', 'commissioning', 'xinstall']
        params = [make_boot_image_storage_params() for _ in range(3)]
        for param in params:
            make_image_dir(param, self.tftproot)
            test_tftppath.make_osystem(self, param['osystem'], purposes)
        return params

    def make_rpc_boot_images(self, param):
        purposes = ['install', 'commissioning', 'xinstall']
        return [
            make_image(param, purpose)
            for purpose in purposes
            ]

    def test_returns_boot_images_matching_subarchitecture(self):
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        self.useFixture(RunningClusterRPCFixture())
        params = self.make_boot_images()
        param = params.pop()

        self.assertItemsEqual(
            self.make_rpc_boot_images(param),
            get_boot_images_for(
                nodegroup,
                param['osystem'],
                param['architecture'],
                param['subarchitecture'],
                param['release']))

    def test_returns_boot_images_matching_subarches_in_boot_resources(self):
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        self.useFixture(RunningClusterRPCFixture())
        params = self.make_boot_images()
        param = params.pop()

        subarches = [factory.make_name('subarch') for _ in range(3)]
        resource_name = '%s/%s' % (param['osystem'], param['release'])
        resource_arch = '%s/%s' % (
            param['architecture'], param['subarchitecture'])

        resource = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=resource_name, architecture=resource_arch)
        resource.extra['subarches'] = ','.join(subarches)
        resource.save()

        subarch = subarches.pop()
        self.assertItemsEqual(
            self.make_rpc_boot_images(param),
            get_boot_images_for(
                nodegroup,
                param['osystem'],
                param['architecture'],
                subarch,
                param['release']))
