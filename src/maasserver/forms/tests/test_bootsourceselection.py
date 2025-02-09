# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootSourceSelectionForm`."""

from django.core.exceptions import ValidationError

from maasserver.forms import BootSourceSelectionForm
from maasserver.models.signals import bootsources
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestBootSourceSelectionForm(MAASServerTestCase):
    """Tests for `BootSourceSelectionForm`."""

    def setUp(self):
        super().setUp()
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

    def make_valid_source_selection_params(self, boot_source=None):
        # Helper that creates a valid BootSourceCache and parameters for
        # a BootSourceSelectionForm that will validate against the
        # cache.
        if boot_source is None:
            boot_source = factory.make_BootSource()
        arch = factory.make_name("arch")
        arch2 = factory.make_name("arch")
        subarch = factory.make_name("subarch")
        subarch2 = factory.make_name("subarch")
        label = factory.make_name("label")
        label2 = factory.make_name("label")
        params = {
            "os": factory.make_name("os"),
            "release": factory.make_name("release"),
            "arches": [arch, arch2],
            "subarches": [subarch, subarch2],
            "labels": [label, label2],
        }
        factory.make_BootSourceCache(
            boot_source=boot_source,
            os=params["os"],
            release=params["release"],
            arch=arch,
            subarch=subarch,
            label=label,
        )
        factory.make_BootSourceCache(
            boot_source=boot_source,
            os=params["os"],
            release=params["release"],
            arch=arch2,
            subarch=subarch2,
            label=label2,
        )
        return params

    def test_edits_boot_source_selection_object(self):
        boot_source_selection = factory.make_BootSourceSelection()
        boot_source = boot_source_selection.boot_source
        params = self.make_valid_source_selection_params(boot_source)
        form = BootSourceSelectionForm(
            instance=boot_source_selection, data=params
        )
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        boot_source_selection = reload_object(boot_source_selection)
        for key, value in params.items():
            self.assertEqual(getattr(boot_source_selection, key), value)

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
        dup_params = {"os": params["os"], "release": params["release"]}
        form = BootSourceSelectionForm(
            boot_source=boot_source, data=dup_params
        )
        self.assertRaises(ValidationError, form.save)

    def test_validates_if_boot_source_cache_has_same_os_and_release(self):
        boot_source = factory.make_BootSource()
        boot_cache = factory.make_BootSourceCache(boot_source)

        params = {"os": boot_cache.os, "release": boot_cache.release}
        form = BootSourceSelectionForm(boot_source=boot_source, data=params)
        self.assertTrue(form.is_valid(), form._errors)

    def test_rejects_if_boot_source_cache_has_different_os(self):
        boot_source = factory.make_BootSource()
        boot_cache = factory.make_BootSourceCache(boot_source)

        params = {"os": factory.make_name("os"), "release": boot_cache.release}
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

        params = {"os": boot_cache.os, "release": factory.make_name("release")}
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

    def make_some_caches(self, boot_source, os, release):
        # Make a few BootSourceCache records that the following tests can use
        # to validate against when using BootSourceSelectionForm.
        return factory.make_many_BootSourceCaches(
            3, boot_source=boot_source, os=os, release=release
        )

    def test_validates_if_boot_source_cache_has_arch(self):
        boot_source = factory.make_BootSource()
        os = factory.make_name("os")
        release = factory.make_name("release")
        boot_caches = self.make_some_caches(boot_source, os, release)

        # Request arches that are in two of the cache records.
        params = {
            "os": os,
            "release": release,
            "arches": [boot_caches[0].arch, boot_caches[2].arch],
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
            "arches": [factory.make_name("arch")],
        }

        form = BootSourceSelectionForm(boot_source=boot_source, data=params)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "arches": [
                    "No available images to download for %s" % params["arches"]
                ]
            },
            form._errors,
        )

    def test_validates_if_boot_source_cache_has_subarch(self):
        boot_source = factory.make_BootSource()
        os = factory.make_name("os")
        release = factory.make_name("release")
        boot_caches = self.make_some_caches(boot_source, os, release)

        # Request subarches that are in two of the cache records.
        params = {
            "os": os,
            "release": release,
            "subarches": [boot_caches[0].subarch, boot_caches[2].subarch],
        }

        form = BootSourceSelectionForm(boot_source=boot_source, data=params)
        self.assertTrue(form.is_valid(), form._errors)

    def test_rejects_if_boot_source_cache_does_not_have_subarch(self):
        boot_source = factory.make_BootSource()
        os = factory.make_name("os")
        release = factory.make_name("release")
        factory.make_BootSourceCache(boot_source, os=os, release=release)

        params = {
            "os": os,
            "release": release,
            "subarches": [factory.make_name("subarch")],
        }

        form = BootSourceSelectionForm(boot_source=boot_source, data=params)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "subarches": [
                    "No available images to download for %s"
                    % params["subarches"]
                ]
            },
            form._errors,
        )

    def test_validates_if_boot_source_cache_has_label(self):
        boot_source = factory.make_BootSource()
        os = factory.make_name("os")
        release = factory.make_name("release")
        boot_caches = self.make_some_caches(boot_source, os, release)

        # Request labels that are in two of the cache records.
        params = {
            "os": os,
            "release": release,
            "labels": [boot_caches[0].label, boot_caches[2].label],
        }

        form = BootSourceSelectionForm(boot_source=boot_source, data=params)
        self.assertTrue(form.is_valid(), form._errors)

    def test_rejects_if_boot_source_cache_does_not_have_label(self):
        boot_source = factory.make_BootSource()
        os = factory.make_name("os")
        release = factory.make_name("release")
        factory.make_BootSourceCache(boot_source, os=os, release=release)

        params = {
            "os": os,
            "release": release,
            "labels": [factory.make_name("label")],
        }

        form = BootSourceSelectionForm(boot_source=boot_source, data=params)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "labels": [
                    "No available images to download for %s" % params["labels"]
                ]
            },
            form._errors,
        )

    def test_star_values_in_request_validate_against_any_cache(self):
        boot_source = factory.make_BootSource()
        os = factory.make_name("os")
        release = factory.make_name("release")
        factory.make_BootSourceCache(boot_source, os=os, release=release)
        params = {
            "os": os,
            "release": release,
            "arches": ["*"],
            "subarches": ["*"],
            "labels": ["*"],
        }

        form = BootSourceSelectionForm(boot_source=boot_source, data=params)
        self.assertTrue(form.is_valid(), form._errors)
