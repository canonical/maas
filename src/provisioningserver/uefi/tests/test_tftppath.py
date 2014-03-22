# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the uefi tftppath module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.testcase import MAASTestCase
from provisioningserver.testing.config import ConfigFixture
from provisioningserver.uefi.tftppath import compose_uefi_bootloader_path
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

    def test_compose_bootloader_path_follows_maas_uefi_directory_layout(self):
        self.assertEqual('bootx64.efi', compose_uefi_bootloader_path())

    def test_compose_bootloader_path_does_not_include_tftp_root(self):
        self.assertThat(
            compose_uefi_bootloader_path(),
            Not(StartsWith(self.tftproot)))
