# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the install_grub command."""


import os.path

from testtools.matchers import FileExists

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
import provisioningserver.boot.install_grub
from provisioningserver.testing.config import ClusterConfigurationFixture
from provisioningserver.utils.script import MainScript


class TestInstallGrub(MAASTestCase):
    def test_integration(self):
        tftproot = self.make_dir()
        self.useFixture(ClusterConfigurationFixture(tftp_root=tftproot))

        action = factory.make_name("action")
        script = MainScript(action)
        script.register(action, provisioningserver.boot.install_grub)
        script.execute((action,))

        config_filename = os.path.join("grub", "grub.cfg")
        self.assertThat(os.path.join(tftproot, config_filename), FileExists())
