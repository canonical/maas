# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the SUSEOS module."""


from itertools import product

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.osystem.suse import (
    BOOT_IMAGE_PURPOSE,
    DISTRO_SERIES_DEFAULT,
    SUSEOS,
)


class TestSUSEOS(MAASTestCase):
    def test_get_boot_image_purposes(self):
        osystem = SUSEOS()
        archs = [factory.make_name("arch") for _ in range(2)]
        subarchs = [factory.make_name("subarch") for _ in range(2)]
        releases = [factory.make_name("release") for _ in range(2)]
        labels = [factory.make_name("label") for _ in range(2)]
        for arch, subarch, release, label in product(
            archs, subarchs, releases, labels
        ):
            expected = osystem.get_boot_image_purposes(
                arch, subarchs, release, label
            )
            self.assertIsInstance(expected, list)
            self.assertEqual(expected, [BOOT_IMAGE_PURPOSE.XINSTALL])

    def test_get_default_release(self):
        osystem = SUSEOS()
        expected = osystem.get_default_release()
        self.assertEqual(expected, DISTRO_SERIES_DEFAULT)

    def test_get_release_title(self):
        osystem = SUSEOS()
        cases = [
            ("sles", "SUSE Linux Enterprise Server"),
            ("sles12", "SUSE Linux Enterprise Server 12"),
            ("sles15.4", "SUSE Linux Enterprise Server 15 SP4"),
            ("opensuse15", "OpenSUSE 15"),
            ("opensuse15.4", "OpenSUSE 15.4"),
            ("tumbleweed", "OpenSUSE Tumbleweed"),
            ("tumbleweed-20230101", "OpenSUSE Tumbleweed 20230101"),
        ]
        for release, title in cases:
            self.assertEqual(
                title, osystem.get_release_title(release), release
            )
