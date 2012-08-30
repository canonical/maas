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
        name = factory.make_name('config')
        self.assertEqual(
            'pxelinux.cfg/%02x-%s' % (ARP_HTYPE.ETHERNET, name),
            compose_config_path(name))

    def test_compose_config_path_does_not_include_tftp_root(self):
        name = factory.make_name('config')
        self.assertThat(
            compose_config_path(name),
            Not(StartsWith(self.tftproot)))

    def test_compose_image_path_follows_maas_pxe_directory_layout(self):
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        release = factory.make_name('release')
        purpose = factory.make_name('purpose')
        self.assertEqual(
            '%s/%s/%s/%s' % (arch, subarch, release, purpose),
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
        self.assertEqual('pxelinux.0', compose_bootloader_path())

    def test_compose_bootloader_path_does_not_include_tftp_root(self):
        self.assertThat(
            compose_bootloader_path(),
            Not(StartsWith(self.tftproot)))

    def test_locate_tftp_path_prefixes_tftp_root(self):
        pxefile = factory.make_name('pxefile')
        self.assertEqual(
            os.path.join(self.tftproot, pxefile),
            locate_tftp_path(pxefile, tftproot=self.tftproot))

    def test_locate_tftp_path_returns_root_when_path_is_None(self):
        self.assertEqual(
            self.tftproot, locate_tftp_path(None, tftproot=self.tftproot))
