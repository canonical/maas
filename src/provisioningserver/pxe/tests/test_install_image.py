# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the install_pxe_image command."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import os

from maastesting.factory import factory
from maastesting.testcase import TestCase
import provisioningserver.pxe.install_image
from provisioningserver.pxe.install_image import (
    are_identical_dirs,
    install_dir,
    make_destination,
    )
from provisioningserver.pxe.tftppath import (
    compose_image_path,
    locate_tftp_path,
    )
from provisioningserver.testing.config import ConfigFixture
from provisioningserver.utils import MainScript
from testtools.matchers import (
    DirExists,
    FileContains,
    FileExists,
    Not,
    )


def make_arch_subarch_release_purpose():
    """Create arbitrary architecture/subarchitecture/release names.

    :return: A triplet of three identifiers for these respective items.
    """
    return tuple(
        factory.make_name(item)
        for item in ('arch', 'subarch', 'release', 'purpose'))


class TestInstallPXEImage(TestCase):

    def test_integration(self):
        tftproot = self.make_dir()
        config = {"tftp": {"root": tftproot}}
        config_fixture = ConfigFixture(config)
        self.useFixture(config_fixture)

        download_dir = self.make_dir()
        image_dir = os.path.join(download_dir, 'image')
        os.makedirs(image_dir)
        factory.make_file(image_dir, 'kernel')
        arch, subarch, release, purpose = make_arch_subarch_release_purpose()

        action = factory.make_name("action")
        script = MainScript(action)
        script.register(action, provisioningserver.pxe.install_image)
        script.execute(
            ("--config-file", config_fixture.filename, action, "--arch", arch,
             "--subarch", subarch, "--release", release, "--purpose", purpose,
             "--image", image_dir))

        self.assertThat(
            os.path.join(
                locate_tftp_path(
                    compose_image_path(arch, subarch, release, purpose),
                    tftproot=tftproot),
                'kernel'),
            FileExists())

    def test_make_destination_follows_pxe_path_conventions(self):
        # The directory that make_destination returns follows the PXE
        # directory hierarchy specified for MAAS:
        # /var/lib/maas/tftp/<arch>/<subarch>/<release>/<purpose>
        # (Where the /var/lib/maas/tftp/ part is configurable, so we
        # can test this without overwriting system files).
        tftproot = self.make_dir()
        arch, subarch, release, purpose = make_arch_subarch_release_purpose()
        self.assertEqual(
            os.path.join(tftproot, arch, subarch, release, purpose),
            make_destination(tftproot, arch, subarch, release, purpose))

    def test_make_destination_creates_directory_if_not_present(self):
        tftproot = self.make_dir()
        arch, subarch, release, purpose = make_arch_subarch_release_purpose()
        expected_destination = os.path.dirname(locate_tftp_path(
            compose_image_path(arch, subarch, release, purpose),
            tftproot=tftproot))
        make_destination(tftproot, arch, subarch, release, purpose)
        self.assertThat(expected_destination, DirExists())

    def test_make_destination_returns_existing_directory(self):
        tftproot = self.make_dir()
        arch, subarch, release, purpose = make_arch_subarch_release_purpose()
        expected_dest = locate_tftp_path(
            compose_image_path(arch, subarch, release, purpose),
            tftproot=tftproot)
        os.makedirs(expected_dest)
        contents = factory.getRandomString()
        testfile = factory.make_name('testfile')
        factory.make_file(expected_dest, contents=contents, name=testfile)
        dest = make_destination(tftproot, arch, subarch, release, purpose)
        self.assertThat(os.path.join(dest, testfile), FileContains(contents))

    def test_are_identical_dirs_sees_missing_old_dir_as_different(self):
        self.assertFalse(
            are_identical_dirs(
                os.path.join(self.make_dir(), factory.getRandomString()),
                os.path.dirname(self.make_file())))

    def test_are_identical_dirs_returns_true_if_identical(self):
        name = factory.getRandomString()
        contents = factory.getRandomString()
        self.assertTrue(are_identical_dirs(
            os.path.dirname(self.make_file(name=name, contents=contents)),
            os.path.dirname(self.make_file(name=name, contents=contents))))

    def test_are_identical_dirs_returns_false_if_file_has_changed(self):
        name = factory.getRandomString()
        old = os.path.dirname(self.make_file(name=name))
        new = os.path.dirname(self.make_file(name=name))
        self.assertFalse(are_identical_dirs(old, new))

    def test_are_identical_dirs_returns_false_if_file_was_added(self):
        shared_file = factory.getRandomString()
        contents = factory.getRandomString()
        old = os.path.dirname(
            self.make_file(name=shared_file, contents=contents))
        new = os.path.dirname(
            self.make_file(name=shared_file, contents=contents))
        factory.make_file(new)
        self.assertFalse(are_identical_dirs(old, new))

    def test_are_identical_dirs_returns_false_if_file_was_removed(self):
        shared_file = factory.getRandomString()
        contents = factory.getRandomString()
        old = os.path.dirname(
            self.make_file(name=shared_file, contents=contents))
        new = os.path.dirname(
            self.make_file(name=shared_file, contents=contents))
        factory.make_file(old)
        self.assertFalse(are_identical_dirs(old, new))

    def test_install_dir_moves_dir_into_place(self):
        download_image = os.path.join(self.make_dir(), 'download-image')
        published_image = os.path.join(self.make_dir(), 'published-image')
        contents = factory.getRandomString()
        os.makedirs(download_image)
        sample_file = factory.make_file(download_image, contents=contents)
        install_dir(download_image, published_image)
        self.assertThat(
            os.path.join(published_image, os.path.basename(sample_file)),
            FileContains(contents))

    def test_install_dir_replaces_existing_dir(self):
        download_image = os.path.join(self.make_dir(), 'download-image')
        published_image = os.path.join(self.make_dir(), 'published-image')
        os.makedirs(download_image)
        sample_file = factory.make_file(download_image)
        os.makedirs(published_image)
        obsolete_file = factory.make_file(published_image)
        install_dir(download_image, published_image)
        self.assertThat(
            os.path.join(published_image, os.path.basename(sample_file)),
            FileExists())
        self.assertThat(obsolete_file, Not(FileExists()))

    def test_install_dir_sweeps_aside_dot_new_and_dot_old_if_any(self):
        # If directories <old>.old or <old>.new already exist, they're
        # probably from an aborted previous run.  They won't stop
        # install_dir from doing its work.
        download_image = os.path.join(self.make_dir(), 'download-image')
        published_image = os.path.join(
            self.make_dir(), factory.getRandomString())
        contents = factory.getRandomString()
        os.makedirs(download_image)
        sample_file = factory.make_file(download_image, contents=contents)
        os.makedirs('%s.old' % published_image)
        os.makedirs('%s.new' % published_image)
        install_dir(download_image, published_image)
        self.assertThat(
            os.path.join(published_image, os.path.basename(sample_file)),
            FileContains(contents))
        self.assertThat('%s.old' % published_image, Not(DirExists()))
        self.assertThat('%s.new' % published_image, Not(DirExists()))
