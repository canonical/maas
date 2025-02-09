# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootSourceCache`."""

from maasserver.models.bootsourcecache import BootSourceCache
from maasserver.models.signals import bootsources
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestBootSourceCache(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

    def test_get_release_title_returns_None_for_unknown(self):
        self.assertIsNone(
            BootSourceCache.objects.get_release_title(
                factory.make_name("os"), factory.make_name("release")
            )
        )

    def test_get_release_title_returns_None_for_missing_title(self):
        cache = factory.make_BootSourceCache()
        self.assertIsNone(
            BootSourceCache.objects.get_release_title(cache.os, cache.release)
        )

    def test_get_release_title_returns_release_title(self):
        release_title = factory.make_name("release_title")
        cache = factory.make_BootSourceCache(release_title=release_title)
        self.assertEqual(
            release_title,
            BootSourceCache.objects.get_release_title(cache.os, cache.release),
        )

    def test_get_release_codename_returns_None_for_unknown(self):
        self.assertIsNone(
            BootSourceCache.objects.get_release_title(
                factory.make_name("os"), factory.make_name("release")
            )
        )

    def test_get_release_codename_returns_None_for_missing_codename(self):
        cache = factory.make_BootSourceCache()
        self.assertIsNone(
            BootSourceCache.objects.get_release_title(cache.os, cache.release)
        )

    def test_get_release_codename_returns_release_codename(self):
        release_codename = factory.make_name("release_codename")
        cache = factory.make_BootSourceCache(release_codename=release_codename)
        self.assertEqual(
            release_codename,
            BootSourceCache.objects.get_release_codename(
                cache.os, cache.release
            ),
        )
