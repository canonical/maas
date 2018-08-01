# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Custom module."""

__all__ = []

from itertools import product
import os

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.config import ClusterConfiguration
from provisioningserver.drivers.osystem.custom import (
    BOOT_IMAGE_PURPOSE,
    CustomOS,
)
from provisioningserver.testing.config import ClusterConfigurationFixture


class TestCustomOS(MAASTestCase):

    def make_resource_path(self, filename):
        self.useFixture(ClusterConfigurationFixture())
        tmpdir = self.make_dir()
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        release = factory.make_name('release')
        label = factory.make_name('label')
        current_dir = os.path.join(tmpdir, 'current') + '/'
        dirpath = os.path.join(
            current_dir, 'custom', arch, subarch, release, label)
        os.makedirs(dirpath)
        factory.make_file(dirpath, filename)
        with ClusterConfiguration.open_for_update() as config:
            config.tftp_root = current_dir
        return arch, subarch, release, label

    def test_get_boot_image_purposes(self):
        osystem = CustomOS()
        archs = [factory.make_name('arch') for _ in range(2)]
        subarchs = [factory.make_name('subarch') for _ in range(2)]
        releases = [factory.make_name('release') for _ in range(2)]
        labels = [factory.make_name('label') for _ in range(2)]
        for arch, subarch, release, label in product(
                archs, subarchs, releases, labels):
            expected = osystem.get_boot_image_purposes(
                arch, subarchs, release, label)
            self.assertIsInstance(expected, list)
            self.assertEqual(expected, [
                BOOT_IMAGE_PURPOSE.XINSTALL,
                ])

    def test_get_default_release(self):
        osystem = CustomOS()
        self.assertEqual("", osystem.get_default_release())

    def test_get_release_title(self):
        osystem = CustomOS()
        release = factory.make_name('release')
        self.assertEqual(release, osystem.get_release_title(release))

    def test_get_xinstall_parameters_returns_root_tgz_tgz(self):
        osystem = CustomOS()
        arch, subarch, release, label = self.make_resource_path('root-tgz')
        self.assertItemsEqual(
            ('root-tgz', 'tgz'),
            osystem.get_xinstall_parameters(arch, subarch, release, label))

    def test_get_xinstall_parameters_returns_root_dd_dd_tgz(self):
        osystem = CustomOS()
        arch, subarch, release, label = self.make_resource_path('root-dd')
        self.assertItemsEqual(
            ('root-dd', 'dd-tgz'),
            osystem.get_xinstall_parameters(arch, subarch, release, label))

    def test_get_xinstall_parameters_returns_root_dd_tar_dd_tar(self):
        osystem = CustomOS()
        arch, subarch, release, label = self.make_resource_path('root-dd.tar')
        self.assertItemsEqual(
            ('root-dd.tar', 'dd-tar'),
            osystem.get_xinstall_parameters(arch, subarch, release, label))

    def test_get_xinstall_parameters_returns_root_dd_raw_dd_raw(self):
        osystem = CustomOS()
        arch, subarch, release, label = self.make_resource_path('root-dd.raw')
        self.assertItemsEqual(
            ('root-dd.raw', 'dd-raw'),
            osystem.get_xinstall_parameters(arch, subarch, release, label))

    def test_get_xinstall_parameters_returns_root_dd_tbz_dd_bz2(self):
        osystem = CustomOS()
        arch, subarch, release, label = self.make_resource_path('root-dd.bz2')
        self.assertItemsEqual(
            ('root-dd.bz2', 'dd-bz2'),
            osystem.get_xinstall_parameters(arch, subarch, release, label))

    def test_get_xinstall_parameters_returns_root_dd_gz_dd_gz(self):
        osystem = CustomOS()
        arch, subarch, release, label = self.make_resource_path('root-dd.gz')
        self.assertItemsEqual(
            ('root-dd.gz', 'dd-gz'),
            osystem.get_xinstall_parameters(arch, subarch, release, label))

    def test_get_xinstall_parameters_returns_root_dd_tar_bz_dd_tbz(self):
        osystem = CustomOS()
        arch, subarch, release, label = self.make_resource_path(
            'root-dd.tar.bz2')
        self.assertItemsEqual(
            ('root-dd.tar.bz2', 'dd-tbz'),
            osystem.get_xinstall_parameters(arch, subarch, release, label))

    def test_get_xinstall_parameters_returns_root_dd_xz_dd_xz(self):
        osystem = CustomOS()
        arch, subarch, release, label = self.make_resource_path('root-dd.xz')
        self.assertItemsEqual(
            ('root-dd.xz', 'dd-xz'),
            osystem.get_xinstall_parameters(arch, subarch, release, label))

    def test_get_xinstall_parameters_returns_root_dd_tar_xz_dd_txz(self):
        osystem = CustomOS()
        arch, subarch, release, label = self.make_resource_path(
            'root-dd.tar.xz')
        self.assertItemsEqual(
            ('root-dd.tar.xz', 'dd-txz'),
            osystem.get_xinstall_parameters(arch, subarch, release, label))

    def test_get_xinstall_parameters_returns_default_when_not_found(self):
        osystem = CustomOS()
        self.assertItemsEqual(
            ('root-tgz', 'tgz'),
            osystem.get_xinstall_parameters(
                factory.make_name('arch'),
                factory.make_name('subarch'),
                factory.make_name('release'),
                factory.make_name('label')))
