# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootSourceSelectionForm`."""

from django.core.exceptions import ValidationError

from maasserver.forms import BootSourceSelectionForm
from maasserver.models.signals import bootsources
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestBootSourceSelectionForm(MAASServerTestCase):
    """Tests for `BootSourceSelectionForm`."""

    def setUp(self):
        super().setUp()
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

    def make_valid_source_selection_params(self, boot_source):
        # Helper that creates a valid BootSourceCache and parameters for
        # a BootSourceSelectionForm that will validate against the
        # cache.
        arch = factory.make_name("arch")
        params = {
            "os": factory.make_name("os"),
            "release": factory.make_name("release"),
            "arch": arch,
        }
        factory.make_BootSourceCache(
            boot_source=boot_source,
            os=params["os"],
            release=params["release"],
            arch=arch,
        )
        return params

    def test_creates_boot_source_selection_object(self):
        boot_source = factory.make_BootSource()
        params = self.make_valid_source_selection_params(boot_source)
        form = BootSourceSelectionForm(boot_source=boot_source, data=params)
        self.assertTrue(form.is_valid(), form._errors)
        boot_source_selection = form.save()
        for key, value in params.items():
            self.assertEqual(getattr(boot_source_selection, key), value)

    def test_cannot_create_duplicate_entry(self):
        boot_source = factory.make_BootSource()
        params = self.make_valid_source_selection_params(boot_source)
        form = BootSourceSelectionForm(boot_source=boot_source, data=params)
        self.assertTrue(form.is_valid(), form._errors)
        form.save()

        # Duplicates should be detected for the same boot_source, os and
        # release, the other fields are irrelevant.
        dup_params = {
            "os": params["os"],
            "release": params["release"],
            "arch": params["arch"],
        }
        form = BootSourceSelectionForm(
            boot_source=boot_source, data=dup_params
        )
        self.assertRaises(ValidationError, form.save)

    def test_validates_if_boot_source_cache_has_same_os_and_release(self):
        boot_source = factory.make_BootSource()
        boot_cache = factory.make_BootSourceCache(boot_source)

        params = {
            "os": boot_cache.os,
            "release": boot_cache.release,
            "arch": boot_cache.arch,
        }
        form = BootSourceSelectionForm(boot_source=boot_source, data=params)
        self.assertTrue(form.is_valid(), form._errors)

    def test_rejects_if_boot_source_cache_has_different_os(self):
        boot_source = factory.make_BootSource()
        boot_cache = factory.make_BootSourceCache(boot_source)

        params = {
            "os": factory.make_name("os"),
            "release": boot_cache.release,
            "arch": boot_cache.arch,
        }
        form = BootSourceSelectionForm(boot_source=boot_source, data=params)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "os": [
                    "OS %s with release %s has no available images "
                    "for download" % (params["os"], boot_cache.release)
                ]
            },
            form._errors,
        )

    def test_rejects_if_boot_source_cache_has_different_release(self):
        boot_source = factory.make_BootSource()
        boot_cache = factory.make_BootSourceCache(boot_source)

        params = {
            "os": boot_cache.os,
            "release": factory.make_name("release"),
            "arch": factory.make_name("arch"),
        }
        form = BootSourceSelectionForm(boot_source=boot_source, data=params)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "os": [
                    "OS %s with release %s has no available images "
                    "for download" % (boot_cache.os, params["release"])
                ]
            },
            form._errors,
        )

    def test_validates_if_boot_source_cache_has_arch(self):
        boot_source = factory.make_BootSource()
        os = factory.make_name("os")
        release = factory.make_name("release")
        boot_cache = factory.make_BootSourceCache(
            boot_source=boot_source, os=os, release=release
        )

        # Request arches that are in two of the cache records.
        params = {
            "os": os,
            "release": release,
            "arch": boot_cache.arch,
        }

        form = BootSourceSelectionForm(boot_source=boot_source, data=params)
        self.assertTrue(form.is_valid(), form._errors)

    def test_rejects_if_boot_source_cache_does_not_have_arch(self):
        boot_source = factory.make_BootSource()
        os = factory.make_name("os")
        release = factory.make_name("release")
        factory.make_BootSourceCache(boot_source, os=os, release=release)

        params = {
            "os": os,
            "release": release,
            "arch": factory.make_name("arch"),
        }

        form = BootSourceSelectionForm(boot_source=boot_source, data=params)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "arch": [
                    "No available images to download for %s" % params["arch"]
                ]
            },
            form._errors,
        )
