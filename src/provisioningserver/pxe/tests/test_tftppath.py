# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the tftppath module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import os.path

from maastesting.factory import factory
from maastesting.testcase import TestCase
from provisioningserver.enum import ARP_HTYPE
from provisioningserver.pxe.tftppath import (
    compose_bootloader_path,
    compose_config_path,
    compose_image_path,
    locate_tftp_path,
    )
from provisioningserver.testing.config import ConfigFixture
from testtools.matchers import (
    Not,
    StartsWith,
    )


class TestTFTPPath(TestCase):

    def setUp(self):
        super(TestTFTPPath, self).setUp()
        self.tftproot = self.make_dir()
        self.config = {"tftp": {"root": self.tftproot}}
        self.useFixture(ConfigFixture(self.config))

    def test_compose_config_path_follows_maas_pxe_directory_layout(self):
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        name = factory.make_name('config')
        self.assertEqual(
            '/maas/%s/%s/pxelinux.cfg/%02x-%s' % (
                arch, subarch, ARP_HTYPE.ETHERNET, name),
            compose_config_path(arch, subarch, name))

    def test_compose_config_path_does_not_include_tftp_root(self):
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        name = factory.make_name('config')
        self.assertThat(
            compose_config_path(arch, subarch, name),
            Not(StartsWith(self.tftproot)))

    def test_compose_image_path_follows_maas_pxe_directory_layout(self):
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        release = factory.make_name('release')
        purpose = factory.make_name('purpose')
        self.assertEqual(
            '/maas/%s/%s/%s/%s' % (arch, subarch, release, purpose),
            compose_image_path(arch, subarch, release, purpose))

    def test_compose_image_path_does_not_include_tftp_root(self):
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        release = factory.make_name('release')
        purpose = factory.make_name('purpose')
        self.assertThat(
            compose_image_path(arch, subarch, release, purpose),
            Not(StartsWith(self.tftproot)))

    def test_compose_bootloader_path_follows_maas_pxe_directory_layout(self):
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        self.assertEqual(
            '/maas/%s/%s/pxelinux.0' % (arch, subarch),
            compose_bootloader_path(arch, subarch))

    def test_compose_bootloader_path_does_not_include_tftp_root(self):
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        self.assertThat(
            compose_bootloader_path(arch, subarch),
            Not(StartsWith(self.tftproot)))

    def test_locate_tftp_path_prefixes_tftp_root_by_default(self):
        pxefile = factory.make_name('pxefile')
        self.assertEqual(
            os.path.join(self.tftproot, pxefile),
            locate_tftp_path(pxefile, tftproot=self.tftproot))

    def test_locate_tftp_path_overrides_default_tftproot(self):
        tftproot = '/%s' % factory.make_name('tftproot')
        pxefile = factory.make_name('pxefile')
        self.assertEqual(
            os.path.join(tftproot, pxefile),
            locate_tftp_path(pxefile, tftproot=tftproot))

    def test_locate_tftp_path_returns_root_by_default(self):
        self.assertEqual(
            self.tftproot, locate_tftp_path(tftproot=self.tftproot))
