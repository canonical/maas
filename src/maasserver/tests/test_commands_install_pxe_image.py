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

from django.core.management import call_command
from maasserver.management.commands.install_pxe_image import (
    are_identical_dirs,
    install_dir,
    make_destination,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from testtools.matchers import (
    DirExists,
    FileContains,
    FileExists,
    Not,
    )


def make_random_string(prefix):
    """Return an arbitrary string starting with the given prefix."""
    return '-'.join([prefix, factory.getRandomString(5)])


def make_arch_subarch_release():
    """Create arbitrary architecture/subarchitecture/release names.

    :return: A triplet of three identifiers for these respective items.
    """
    return (
        make_random_string('arch'),
        make_random_string('subarch'),
        make_random_string('release'),
        )


class TestInstallPXEImage(TestCase):

    def test_integration(self):
        download_dir = self.make_dir()
        image_dir = os.path.join(download_dir, 'image')
        os.makedirs(image_dir)
        factory.make_file(image_dir, 'kernel')
        pxe_target_dir = self.make_dir()

        call_command(
            'install_pxe_image', arch='arch', subarch='subarch',
            release='release', purpose='purpose', image=image_dir,
            pxe_target_dir=pxe_target_dir)

        self.assertThat(
            os.path.join(
                pxe_target_dir, 'arch', 'subarch', 'release', 'purpose',
                'kernel'),
            FileExists())

    def test_make_destination_follows_pxe_path_conventions(self):
        # The directory that make_destination returns follows the PXE
        # directory hierarchy specified for MAAS:
        # /var/lib/tftproot/maas/<arch>/<subarch>/<release>
        # (Where the /var/lib/tftproot/maas/ part is configurable, so we
        # can test this without overwriting system files).
        pxe_target_dir = self.make_dir()
        arch, subarch, release = make_arch_subarch_release()
        self.assertEqual(
            os.path.join(pxe_target_dir, arch, subarch, release),
            make_destination(pxe_target_dir, arch, subarch, release))

    def test_make_destination_assumes_maas_dir_included_in_target_dir(self):
        # make_destination does not add a "maas" part to the path, as in
        # the default /var/lib/tftpboot/maas/; that is assumed to be
        # included already in the pxe-target-dir setting.
        pxe_target_dir = self.make_dir()
        arch, subarch, release = make_arch_subarch_release()
        self.assertNotIn(
            '/maas/',
            make_destination(pxe_target_dir, arch, subarch, release))

    def test_make_destination_creates_directory_if_not_present(self):
        pxe_target_dir = self.make_dir()
        arch, subarch, release = make_arch_subarch_release()
        expected_destination = os.path.join(
            pxe_target_dir, arch, subarch, release)
        make_destination(pxe_target_dir, arch, subarch, release)
        self.assertThat(expected_destination, DirExists())

    def test_make_destination_returns_existing_directory(self):
        pxe_target_dir = self.make_dir()
        arch, subarch, release = make_arch_subarch_release()
        expected_dest = os.path.join(pxe_target_dir, arch, subarch, release)
        os.makedirs(expected_dest)
        contents = factory.getRandomString()
        testfile = factory.getRandomString()
        factory.make_file(expected_dest, contents=contents, name=testfile)
        dest = make_destination(pxe_target_dir, arch, subarch, release)
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
