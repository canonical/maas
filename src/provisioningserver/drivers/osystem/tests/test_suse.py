# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the SUSEOS module."""


from itertools import product
import random

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.osystem.suse import (
    BOOT_IMAGE_PURPOSE,
    DISTRO_SERIES_CHOICES,
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
        release = random.choice(list(DISTRO_SERIES_CHOICES))
        self.assertEqual(
            DISTRO_SERIES_CHOICES[release], osystem.get_release_title(release)
        )
