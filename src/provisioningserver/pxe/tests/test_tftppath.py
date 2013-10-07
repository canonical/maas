# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the tftppath module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os.path

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.enum import ARP_HTYPE
from provisioningserver.pxe.tftppath import (
    compose_bootloader_path,
    compose_config_path,
    compose_image_path,
    drill_down,
    extend_path,
    is_visible_subdir,
    list_boot_images,
    list_subdirs,
    locate_tftp_path,
    )
from provisioningserver.testing.boot_images import make_boot_image_params
from provisioningserver.testing.config import ConfigFixture
from testtools.matchers import (
    Not,
    StartsWith,
    )


class TestTFTPPath(MAASTestCase):

    def setUp(self):
        super(TestTFTPPath, self).setUp()
        self.tftproot = self.make_dir()
        self.config = {"tftp": {"root": self.tftproot}}
        self.useFixture(ConfigFixture(self.config))

    def make_image_dir(self, image_params, tftproot):
        """Fake a boot image matching `image_params` under `tftproot`."""
        image_dir = locate_tftp_path(
            compose_image_path(
                arch=image_params['architecture'],
                subarch=image_params['subarchitecture'],
                release=image_params['release'],
                purpose=image_params['purpose']),
            tftproot)
        os.makedirs(image_dir)
        factory.make_file(image_dir, 'linux')
        factory.make_file(image_dir, 'initrd.gz')

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

    def test_list_boot_images_copes_with_empty_directory(self):
        self.assertItemsEqual([], list_boot_images(self.tftproot))

    def test_list_boot_images_copes_with_unexpected_files(self):
        os.makedirs(os.path.join(self.tftproot, factory.make_name('empty')))
        factory.make_file(self.tftproot)
        self.assertItemsEqual([], list_boot_images(self.tftproot))

    def test_list_boot_images_finds_boot_image(self):
        image = make_boot_image_params()
        self.make_image_dir(image, self.tftproot)
        self.assertItemsEqual([image], list_boot_images(self.tftproot))

    def test_list_boot_images_enumerates_boot_images(self):
        images = [make_boot_image_params() for counter in range(3)]
        for image in images:
            self.make_image_dir(image, self.tftproot)
        self.assertItemsEqual(images, list_boot_images(self.tftproot))

    def test_is_visible_subdir_ignores_regular_files(self):
        plain_file = self.make_file()
        self.assertFalse(
            is_visible_subdir(
                os.path.dirname(plain_file), os.path.basename(plain_file)))

    def test_is_visible_subdir_ignores_hidden_directories(self):
        base_dir = self.make_dir()
        hidden_dir = factory.make_name('.')
        os.makedirs(os.path.join(base_dir, hidden_dir))
        self.assertFalse(is_visible_subdir(base_dir, hidden_dir))

    def test_is_visible_subdir_recognizes_subdirectory(self):
        base_dir = self.make_dir()
        subdir = factory.make_name('subdir')
        os.makedirs(os.path.join(base_dir, subdir))
        self.assertTrue(is_visible_subdir(base_dir, subdir))

    def test_list_subdirs_lists_empty_directory(self):
        self.assertItemsEqual([], list_subdirs(self.make_dir()))

    def test_list_subdirs_lists_subdirs(self):
        base_dir = self.make_dir()
        factory.make_file(base_dir, factory.make_name('plain-file'))
        subdir = factory.make_name('subdir')
        os.makedirs(os.path.join(base_dir, subdir))
        self.assertItemsEqual([subdir], list_subdirs(base_dir))

    def test_extend_path_finds_path_extensions(self):
        base_dir = self.make_dir()
        subdirs = [
            factory.make_name('subdir-%d' % counter)
            for counter in range(3)]
        for subdir in subdirs:
            os.makedirs(os.path.join(base_dir, subdir))
        self.assertItemsEqual(
            [[os.path.basename(base_dir), subdir] for subdir in subdirs],
            extend_path(
                os.path.dirname(base_dir), [os.path.basename(base_dir)]))

    def test_extend_path_builds_on_given_paths(self):
        base_dir = self.make_dir()
        lower_dir = factory.make_name('lower')
        subdir = factory.make_name('sub')
        os.makedirs(os.path.join(base_dir, lower_dir, subdir))
        self.assertEqual(
            [[lower_dir, subdir]],
            extend_path(base_dir, [lower_dir]))

    def test_extend_path_stops_if_no_subdirs_found(self):
        self.assertItemsEqual([], extend_path(self.make_dir(), []))

    def test_drill_down_follows_directory_tree(self):
        base_dir = self.make_dir()
        lower_dir = factory.make_name('lower')
        os.makedirs(os.path.join(base_dir, lower_dir))
        subdirs = [
            factory.make_name('subdir-%d' % counter)
            for counter in range(3)]
        for subdir in subdirs:
            os.makedirs(os.path.join(base_dir, lower_dir, subdir))
        self.assertItemsEqual(
            [[lower_dir, subdir] for subdir in subdirs],
            drill_down(base_dir, [[lower_dir]]))

    def test_drill_down_ignores_subdir_not_in_path(self):
        base_dir = self.make_dir()
        irrelevant_dir = factory.make_name('irrelevant')
        irrelevant_subdir = factory.make_name('subdir')
        relevant_dir = factory.make_name('relevant')
        relevant_subdir = factory.make_name('subdir')
        os.makedirs(os.path.join(base_dir, irrelevant_dir, irrelevant_subdir))
        os.makedirs(os.path.join(base_dir, relevant_dir, relevant_subdir))
        self.assertEqual(
            [[relevant_dir, relevant_subdir]],
            drill_down(base_dir, [[relevant_dir]]))

    def test_drill_down_drops_paths_that_do_not_go_deep_enough(self):
        base_dir = self.make_dir()
        shallow_dir = factory.make_name('shallow')
        os.makedirs(os.path.join(base_dir, shallow_dir))
        deep_dir = factory.make_name('deep')
        subdir = factory.make_name('sub')
        os.makedirs(os.path.join(base_dir, deep_dir, subdir))
        self.assertEqual(
            [[deep_dir, subdir]],
            drill_down(base_dir, [[shallow_dir], [deep_dir]]))
