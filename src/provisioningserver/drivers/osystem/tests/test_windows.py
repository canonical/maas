# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the WindowsOS module."""

__all__ = []

import os
import random

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.osystem import (
    Node,
    Token,
)
from provisioningserver.drivers.osystem.windows import (
    BOOT_IMAGE_PURPOSE,
    REQUIRE_LICENSE_KEY,
    WINDOWS_CHOICES,
    WINDOWS_DEFAULT,
    WindowsOS,
)
from provisioningserver.testing.config import ClusterConfigurationFixture


class TestWindowsOS(MAASTestCase):

    def make_resource_path(self, files=[]):
        tmpdir = self.make_dir()
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        release = factory.make_name('release')
        label = factory.make_name('label')
        dirpath = os.path.join(
            tmpdir, 'windows', arch, subarch, release, label)
        os.makedirs(dirpath)
        for fname in files:
            factory.make_file(dirpath, fname)
        self.useFixture(ClusterConfigurationFixture(tftp_root=tmpdir))
        return arch, subarch, release, label

    def test_get_boot_image_purposes_neither(self):
        osystem = WindowsOS()
        arch, subarch, release, label = self.make_resource_path()
        self.assertItemsEqual(
            [],
            osystem.get_boot_image_purposes(arch, subarch, release, label))

    def test_get_boot_image_purposes_both(self):
        osystem = WindowsOS()
        arch, subarch, release, label = self.make_resource_path(
            files=['root-dd', 'pxeboot.0'])
        self.assertItemsEqual(
            [BOOT_IMAGE_PURPOSE.XINSTALL, BOOT_IMAGE_PURPOSE.INSTALL],
            osystem.get_boot_image_purposes(arch, subarch, release, label))

    def test_get_boot_image_purposes_xinstall_only(self):
        osystem = WindowsOS()
        arch, subarch, release, label = self.make_resource_path(
            files=['root-dd'])
        self.assertItemsEqual(
            [BOOT_IMAGE_PURPOSE.XINSTALL],
            osystem.get_boot_image_purposes(arch, subarch, release, label))

    def test_get_boot_image_purposes_install_only(self):
        osystem = WindowsOS()
        arch, subarch, release, label = self.make_resource_path(
            files=['pxeboot.0'])
        self.assertItemsEqual(
            [BOOT_IMAGE_PURPOSE.INSTALL],
            osystem.get_boot_image_purposes(arch, subarch, release, label))

    def test_get_default_release(self):
        osystem = WindowsOS()
        expected = osystem.get_default_release()
        self.assertEqual(expected, WINDOWS_DEFAULT)

    def test_get_release_title(self):
        osystem = WindowsOS()
        release = random.choice(list(WINDOWS_CHOICES))
        self.assertEqual(
            WINDOWS_CHOICES[release],
            osystem.get_release_title(release))

    def test_requires_license_key_True(self):
        osystem = WindowsOS()
        for release in REQUIRE_LICENSE_KEY:
            self.assertTrue(osystem.requires_license_key(release))

    def test_requires_license_key_False(self):
        osystem = WindowsOS()
        not_required = set(
            WINDOWS_CHOICES.keys()).difference(REQUIRE_LICENSE_KEY)
        for release in not_required:
            self.assertFalse(osystem.requires_license_key(release))

    def test_validate_license_key(self):
        osystem = WindowsOS()
        parts = [factory.make_string(size=5) for _ in range(5)]
        key = '-'.join(parts)
        self.assertTrue(
            osystem.validate_license_key(REQUIRE_LICENSE_KEY[0], key))

    def test_validate_license_key_invalid(self):
        osystem = WindowsOS()
        keys = [factory.make_string() for _ in range(3)]
        for key in keys:
            self.assertFalse(
                osystem.validate_license_key(REQUIRE_LICENSE_KEY[0], key))

    def make_node(self, hostname=None):
        if hostname is None:
            machine = factory.make_name('hostname')
            dns = factory.make_name('dns')
            hostname = '%s.%s' % (machine, dns)
        return Node(
            system_id=factory.make_name("system_id"),
            hostname=hostname,
        )

    def make_token(self, consumer_key=None, token_key=None, token_secret=None):
        if consumer_key is None:
            consumer_key = factory.make_name('consumer_key')
        if token_key is None:
            token_key = factory.make_name('token_key')
        if token_secret is None:
            token_secret = factory.make_name('secret_key')
        return Token(
            consumer_key=consumer_key,
            token_key=token_key,
            token_secret=token_secret,
        )

    def test_compose_pressed_not_implemented_for_curtin(self):
        osystem = WindowsOS()
        node = self.make_node()
        token = self.make_token()
        url = factory.make_name('url')
        self.assertRaises(
            NotImplementedError,
            osystem.compose_preseed, 'curtin', node, token, url)

    def test_compose_preseed_has_required_keys(self):
        osystem = WindowsOS()
        node = self.make_node()
        token = self.make_token()
        url = factory.make_name('url')
        required_keys = [
            'maas_metadata_url',
            'maas_oauth_consumer_secret',
            'maas_oauth_consumer_key',
            'maas_oauth_token_key',
            'maas_oauth_token_secret',
            'hostname',
            ]
        preseed = osystem.compose_preseed('default', node, token, url)
        self.assertItemsEqual(required_keys, preseed.keys())

    def test_compose_preseed_uses_only_hostname(self):
        osystem = WindowsOS()
        machine = factory.make_name('hostname')
        dns = factory.make_name('dns')
        hostname = '%s.%s' % (machine, dns)
        node = self.make_node(hostname=hostname)
        token = self.make_token()
        url = factory.make_name('url')
        preseed = osystem.compose_preseed('default', node, token, url)
        self.assertEqual(machine, preseed['hostname'])

    def test_compose_preseed_truncates_hostname(self):
        osystem = WindowsOS()
        machine = factory.make_name('hostname', size=20)
        dns = factory.make_name('dns')
        hostname = '%s.%s' % (machine, dns)
        node = self.make_node(hostname=hostname)
        token = self.make_token()
        url = factory.make_name('url')
        preseed = osystem.compose_preseed('default', node, token, url)
        self.assertEqual(15, len(preseed['hostname']))

    def test_compose_preseed_includes_oauth(self):
        osystem = WindowsOS()
        node = self.make_node()
        consumer_key = factory.make_name('consumer_key')
        token_key = factory.make_name('token_key')
        token_secret = factory.make_name('secret_key')
        token = self.make_token(
            consumer_key=consumer_key, token_key=token_key,
            token_secret=token_secret)
        url = factory.make_name('url')
        preseed = osystem.compose_preseed('default', node, token, url)
        self.assertEqual('', preseed['maas_oauth_consumer_secret'])
        self.assertEqual(consumer_key, preseed['maas_oauth_consumer_key'])
        self.assertEqual(token_key, preseed['maas_oauth_token_key'])
        self.assertEqual(token_secret, preseed['maas_oauth_token_secret'])

    def test_compose_preseed_includes_metadata_url(self):
        osystem = WindowsOS()
        node = self.make_node()
        token = self.make_token()
        url = factory.make_name('url')
        preseed = osystem.compose_preseed('default', node, token, url)
        self.assertEqual(url, preseed['maas_metadata_url'])

    def test_get_xinstall_parameters_returns_root_dd_dd_tgz(self):
        osystem = WindowsOS()
        arch, subarch, release, label = self.make_resource_path(['root-dd'])
        self.assertItemsEqual(
            ('root-dd', 'dd-tgz'),
            osystem.get_xinstall_parameters(arch, subarch, release, label))

    def test_get_xinstall_parameters_returns_root_dd_tar_dd_tar(self):
        osystem = WindowsOS()
        arch, subarch, release, label = self.make_resource_path(
            ['root-dd.tar'])
        self.assertItemsEqual(
            ('root-dd.tar', 'dd-tar'),
            osystem.get_xinstall_parameters(arch, subarch, release, label))

    def test_get_xinstall_parameters_returns_root_dd_raw_dd_raw(self):
        osystem = WindowsOS()
        arch, subarch, release, label = self.make_resource_path(
            ['root-dd.raw'])
        self.assertItemsEqual(
            ('root-dd.raw', 'dd-raw'),
            osystem.get_xinstall_parameters(arch, subarch, release, label))

    def test_get_xinstall_parameters_returns_root_dd_tbz_dd_bz2(self):
        osystem = WindowsOS()
        arch, subarch, release, label = self.make_resource_path(
            ['root-dd.bz2'])
        self.assertItemsEqual(
            ('root-dd.bz2', 'dd-bz2'),
            osystem.get_xinstall_parameters(arch, subarch, release, label))

    def test_get_xinstall_parameters_returns_root_dd_gz_dd_gz(self):
        osystem = WindowsOS()
        arch, subarch, release, label = self.make_resource_path(['root-dd.gz'])
        self.assertItemsEqual(
            ('root-dd.gz', 'dd-gz'),
            osystem.get_xinstall_parameters(arch, subarch, release, label))

    def test_get_xinstall_parameters_returns_root_dd_tar_bz_dd_tbz(self):
        osystem = WindowsOS()
        arch, subarch, release, label = self.make_resource_path(
            ['root-dd.tar.bz2'])
        self.assertItemsEqual(
            ('root-dd.tar.bz2', 'dd-tbz'),
            osystem.get_xinstall_parameters(arch, subarch, release, label))

    def test_get_xinstall_parameters_returns_root_dd_xz_dd_xz(self):
        osystem = WindowsOS()
        arch, subarch, release, label = self.make_resource_path(['root-dd.xz'])
        self.assertItemsEqual(
            ('root-dd.xz', 'dd-xz'),
            osystem.get_xinstall_parameters(arch, subarch, release, label))

    def test_get_xinstall_parameters_returns_root_dd_tar_xz_dd_txz(self):
        osystem = WindowsOS()
        arch, subarch, release, label = self.make_resource_path(
            ['root-dd.tar.xz'])
        self.assertItemsEqual(
            ('root-dd.tar.xz', 'dd-txz'),
            osystem.get_xinstall_parameters(arch, subarch, release, label))

    def test_get_xinstall_parameters_returns_default_when_not_found(self):
        osystem = WindowsOS()
        self.assertItemsEqual(
            ('root-dd', 'dd-tgz'),
            osystem.get_xinstall_parameters(
                factory.make_name('arch'),
                factory.make_name('subarch'),
                factory.make_name('release'),
                factory.make_name('label')))
