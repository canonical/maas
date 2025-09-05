# Copyright 2014-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from os import environ
from unittest.mock import MagicMock

from maasserver import bootsources
from maasserver.bootsources import get_os_info_from_boot_sources
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


def patch_and_capture_env_for_download_all_image_descriptions(testcase):
    class CaptureEnv:
        """Fake function; records a copy of the environment."""

        def __call__(self, *args, **kwargs):
            self.args = args
            self.env = environ.copy()
            return MagicMock()

    capture = testcase.patch(
        bootsources, "download_all_image_descriptions", CaptureEnv()
    )
    return capture


class TestGetOSInfoFromBootSources(MAASServerTestCase):
    def test_returns_empty_sources_and_sets_when_cache_empty(self):
        self.assertEqual(
            ([], set(), set()),
            get_os_info_from_boot_sources(factory.make_name("os")),
        )

    def test_returns_empty_sources_and_sets_when_no_os(self):
        factory.make_BootSourceCache()
        self.assertEqual(
            ([], set(), set()),
            get_os_info_from_boot_sources(factory.make_name("os")),
        )

    def test_returns_sources_and_sets_of_releases_and_architectures(self):
        os = factory.make_name("os")
        sources = [
            factory.make_BootSource(keyring_data="1234") for _ in range(2)
        ]
        releases = set()
        arches = set()
        for source in sources:
            for _ in range(3):
                release = factory.make_name("release")
                arch = factory.make_name("arch")
                factory.make_BootSourceCache(
                    source, os=os, release=release, arch=arch
                )
                releases.add(release)
                arches.add(arch)
        self.assertEqual(
            (sources, releases, arches), get_os_info_from_boot_sources(os)
        )
