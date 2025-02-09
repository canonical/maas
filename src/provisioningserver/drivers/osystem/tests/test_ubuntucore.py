# Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the UbuntuCore module."""

import os

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.config import ClusterConfiguration
from provisioningserver.drivers.osystem.ubuntucore import (
    BOOT_IMAGE_PURPOSE,
    UbuntuCoreOS,
)
from provisioningserver.testing.config import ClusterConfigurationFixture


class TestUbuntuCoreOS(MAASTestCase):
    def make_resource_path(self, filename):
        self.useFixture(ClusterConfigurationFixture())
        tmpdir = self.make_dir()
        arch = factory.make_name("arch")
        subarch = factory.make_name("subarch")
        release = factory.make_name("release")
        label = factory.make_name("label")
        current_dir = os.path.join(tmpdir, "current")
        dirpath = os.path.join(
            current_dir, "ubuntu-core", arch, subarch, release, label
        )
        os.makedirs(dirpath)
        factory.make_file(dirpath, filename)
        with ClusterConfiguration.open_for_update() as config:
            config.tftp_root = current_dir
        return arch, subarch, release, label

    def test_get_boot_image_purposes(self):
        osystem = UbuntuCoreOS()
        expected = osystem.get_boot_image_purposes()
        self.assertIsInstance(expected, list)
        self.assertEqual(expected, [BOOT_IMAGE_PURPOSE.XINSTALL])

    def test_get_default_release(self):
        osystem = UbuntuCoreOS()
        self.assertEqual("16", osystem.get_default_release())

    def test_get_release_title(self):
        osystem = UbuntuCoreOS()
        release = factory.make_name("release")
        self.assertEqual(release, osystem.get_release_title(release))
