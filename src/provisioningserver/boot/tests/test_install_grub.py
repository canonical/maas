# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the install_grub command."""

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
import provisioningserver.boot.install_grub
from provisioningserver.boot.tftppath import locate_tftp_path
from provisioningserver.testing.config import ConfigFixture
from provisioningserver.utils import MainScript
from testtools.matchers import FileExists


class TestInstallGrub(MAASTestCase):

    def test_integration(self):
        tftproot = self.make_dir()
        config = {"tftp": {"root": tftproot}}
        config_fixture = ConfigFixture(config)
        self.useFixture(config_fixture)

        action = factory.make_name("action")
        script = MainScript(action)
        script.register(action, provisioningserver.boot.install_grub)
        script.execute(
            ("--config-file", config_fixture.filename, action))

        config_filename = os.path.join('grub', 'grub.cfg')
        self.assertThat(
            locate_tftp_path(
                config_filename, tftproot=tftproot),
            FileExists())
