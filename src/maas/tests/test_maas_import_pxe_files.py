# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the maas-import-pxe-files script."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import os
from stat import ST_MTIME
from subprocess import check_call

from maastesting.factory import factory
from maastesting.testcase import TestCase
from testtools.matchers import (
    FileContains,
    FileExists,
    Not,
    )


def make_name(prefix, separator='-'):
    """Return an arbitrary name, with the given prefix."""
    return separator.join([prefix, factory.getRandomString(4)])


def read_file(path, name):
    """Return the contents of the file at `path/name`."""
    with open(os.path.join(path, name)) as infile:
        return infile.read()


def get_write_time(path):
    """Return last modification time of file at `path`."""
    return os.stat(path)[ST_MTIME]


def backdate(path):
    """Set the last modification time for the file at `path` to the past."""
    os.utime(path, (99999, 99999))


def compose_download_dir(archive, arch, release):
    """Locate a bootloader, initrd, and kernel in an archive.

    :param archive: Archive directory (corresponding to the script's ARCHIVE
        setting, except here it's a filesystem path not a URL).
    :param arch: Architecture.
    :param release: Ubuntu release name.
    :return: Full absolute path to the directory holding the requisite files
        for this archive, arch, and release.
    """
    return os.path.join(
        archive, 'dists', release, 'main', 'installer-%s' % arch, 'current',
        'images', 'netboot', 'ubuntu-installer', arch)


def compose_tftp_path(tftproot, arch, *path):
    """Compose path for MAAS TFTP files for given architecture.

    After the TFTP root directory and the architecture, just append any path
    components you want to drill deeper, e.g. the release name to get to the
    files for a specific release.
    """
    return os.path.join(tftproot, 'maas', arch, 'generic', *path)


class TestImportPXEFiles(TestCase):

    def make_downloads(self, release=None, arch=None):
        """Set up a directory with an image for "download" by the script.

        Returns an "ARCHIVE" URL for the download.
        """
        if release is None:
            release = make_name('release')
        if arch is None:
            arch = make_name('arch')
        archive = self.make_dir()
        download = compose_download_dir(archive, arch, release)
        os.makedirs(download)
        for filename in ['initrd.gz', 'linux', 'pxelinux.0']:
            factory.make_file(download, filename)
        return archive

    def call_script(self, archive_dir, tftproot, arch=None, release=None):
        """Call the maas-download-pxe-files script with given settings.

        The ARCHIVE URL and TFTPROOT path must be set, or the script will try
        to download from the Ubuntu server and store into the system's real
        TFTP root directory, respectively.  Both bad ideas.
        """
        script = './scripts/maas-import-pxe-files'
        env = {
            'ARCHIVE': 'file://%s' % archive_dir,
            # Substitute curl for wget; it accepts file:// URLs.
            'DOWNLOAD': 'curl -O --silent',
            'TFTPROOT': tftproot,
        }
        if arch is not None:
            env['ARCHES'] = arch
        if release is not None:
            env['RELEASES'] = release
            env['CURRENT_RELEASE'] = release
        with open('/dev/null', 'w') as dev_null:
            check_call(script, env=env, stdout=dev_null)

    def test_downloads_pre_boot_loader(self):
        arch = make_name('arch')
        release = 'precise'
        archive = self.make_downloads(arch=arch, release=release)
        tftproot = self.make_dir()
        self.call_script(archive, tftproot, arch=arch, release=release)
        tftp_path = compose_tftp_path(tftproot, arch, 'pxelinux.0')
        download_path = compose_download_dir(archive, arch, release)
        expected_contents = read_file(download_path, 'pxelinux.0')
        self.assertThat(tftp_path, FileContains(expected_contents))

    def test_ignores_missing_pre_boot_loader(self):
        arch = make_name('arch')
        release = 'precise'
        archive = self.make_downloads(arch=arch, release=release)
        download_path = compose_download_dir(archive, arch, release)
        os.remove(os.path.join(download_path, 'pxelinux.0'))
        tftproot = self.make_dir()
        self.call_script(archive, tftproot, arch=arch, release=release)
        tftp_path = compose_tftp_path(tftproot, arch, 'pxelinux.0')
        self.assertThat(tftp_path, Not(FileExists()))

    def test_updates_pre_boot_loader(self):
        arch = make_name('arch')
        release = 'precise'
        tftproot = self.make_dir()
        tftp_path = compose_tftp_path(tftproot, arch, 'pxelinux.0')
        os.makedirs(os.path.dirname(tftp_path))
        with open(tftp_path, 'w') as existing_file:
            existing_file.write(factory.getRandomString())
        archive = self.make_downloads(arch=arch, release=release)
        self.call_script(archive, tftproot, arch=arch, release=release)
        download_path = compose_download_dir(archive, arch, release)
        expected_contents = read_file(download_path, 'pxelinux.0')
        self.assertThat(tftp_path, FileContains(expected_contents))

    def test_leaves_pre_boot_loader_untouched_if_unchanged(self):
        # If pxelinux.0 has not changed between script runs, the old
        # copy stays in place.
        arch = make_name('arch')
        release = 'precise'
        archive = self.make_downloads(arch=arch, release=release)
        tftproot = self.make_dir()
        self.call_script(archive, tftproot, arch=arch, release=release)
        tftp_path = compose_tftp_path(tftproot, arch, 'pxelinux.0')
        backdate(tftp_path)
        original_timestamp = get_write_time(tftp_path)
        self.call_script(archive, tftproot, arch=arch, release=release)
        self.assertEqual(original_timestamp, get_write_time(tftp_path))

    def test_downloads_install_image(self):
        arch = make_name('arch')
        release = 'precise'
        archive = self.make_downloads(arch=arch, release=release)
        tftproot = self.make_dir()
        self.call_script(archive, tftproot, arch=arch, release=release)
        tftp_path = compose_tftp_path(
            tftproot, arch, release, 'install', 'linux')
        download_path = compose_download_dir(archive, arch, release)
        expected_contents = read_file(download_path, 'linux')
        self.assertThat(tftp_path, FileContains(expected_contents))

    def test_updates_install_image(self):
        arch = make_name('arch')
        release = 'precise'
        tftproot = self.make_dir()
        tftp_path = compose_tftp_path(
            tftproot, arch, release, 'install', 'linux')
        os.makedirs(os.path.dirname(tftp_path))
        with open(tftp_path, 'w') as existing_file:
            existing_file.write(factory.getRandomString())
        archive = self.make_downloads(arch=arch, release=release)
        self.call_script(archive, tftproot, arch=arch, release=release)
        download_path = compose_download_dir(archive, arch, release)
        expected_contents = read_file(download_path, 'linux')
        self.assertThat(tftp_path, FileContains(expected_contents))

    def test_leaves_install_image_untouched_if_unchanged(self):
        arch = make_name('arch')
        release = 'precise'
        archive = self.make_downloads(arch=arch, release=release)
        tftproot = self.make_dir()
        self.call_script(archive, tftproot, arch=arch, release=release)
        tftp_path = compose_tftp_path(
            tftproot, arch, release, 'install', 'linux')
        backdate(tftp_path)
        original_timestamp = get_write_time(tftp_path)
        self.call_script(archive, tftproot, arch=arch, release=release)
        self.assertEqual(original_timestamp, get_write_time(tftp_path))
