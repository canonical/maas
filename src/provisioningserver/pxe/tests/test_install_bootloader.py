# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the install_pxe_bootloader command."""

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
from maastesting.utils import (
    age_file,
    get_write_time,
    )
import provisioningserver.pxe.install_bootloader
from provisioningserver.pxe.install_bootloader import (
    install_bootloader,
    make_destination,
    )
from provisioningserver.pxe.tftppath import (
    compose_bootloader_path,
    locate_tftp_path,
    )
from provisioningserver.testing.config import ConfigFixture
from provisioningserver.utils import MainScript
from testtools.matchers import (
    DirExists,
    FileContains,
    FileExists,
    )


class TestInstallPXEBootloader(TestCase):

    def test_integration(self):
        tftproot = self.make_dir()
        config = {"tftp": {"root": tftproot}}
        config_fixture = ConfigFixture(config)
        self.useFixture(config_fixture)

        loader = self.make_file()
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')

        action = factory.make_name("action")
        script = MainScript(action)
        script.register(action, provisioningserver.pxe.install_bootloader)
        script.execute(
            ("--config-file", config_fixture.filename, action, "--arch", arch,
             "--subarch", subarch, "--loader", loader))

        bootloader_filename = os.path.join(
            os.path.dirname(compose_bootloader_path(arch, subarch)),
            os.path.basename(loader))
        self.assertThat(
            locate_tftp_path(
                bootloader_filename, tftproot=tftproot),
            FileExists())

    def test_make_destination_creates_directory_if_not_present(self):
        tftproot = self.make_dir()
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        dest = make_destination(tftproot, arch, subarch)
        self.assertThat(dest, DirExists())

    def test_make_destination_returns_existing_directory(self):
        tftproot = self.make_dir()
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        make_destination(tftproot, arch, subarch)
        dest = make_destination(tftproot, arch, subarch)
        self.assertThat(dest, DirExists())

    def test_install_bootloader_installs_new_bootloader(self):
        contents = factory.getRandomString()
        loader = self.make_file(contents=contents)
        install_dir = self.make_dir()
        dest = os.path.join(install_dir, factory.make_name('loader'))
        install_bootloader(loader, dest)
        self.assertThat(dest, FileContains(contents))

    def test_install_bootloader_replaces_bootloader_if_changed(self):
        contents = factory.getRandomString()
        loader = self.make_file(contents=contents)
        dest = self.make_file(contents="Old contents")
        install_bootloader(loader, dest)
        self.assertThat(dest, FileContains(contents))

    def test_install_bootloader_skips_if_unchanged(self):
        contents = factory.getRandomString()
        dest = self.make_file(contents=contents)
        age_file(dest, 100)
        original_write_time = get_write_time(dest)
        loader = self.make_file(contents=contents)
        install_bootloader(loader, dest)
        self.assertThat(dest, FileContains(contents))
        self.assertEqual(original_write_time, get_write_time(dest))

    def test_install_bootloader_sweeps_aside_dot_new_if_any(self):
        contents = factory.getRandomString()
        loader = self.make_file(contents=contents)
        dest = self.make_file(contents="Old contents")
        temp_file = '%s.new' % dest
        factory.make_file(
            os.path.dirname(temp_file), name=os.path.basename(temp_file))
        install_bootloader(loader, dest)
        self.assertThat(dest, FileContains(contents))
