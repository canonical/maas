# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootSourceSelection`."""

from django.core.exceptions import ValidationError

from maasserver.models import BootSource, Config
from maasserver.models.bootsourceselection import (
    BootSourceSelection,
    BootSourceSelectionNew,
)
from maasserver.models.signals import bootsources
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestBootSourceSelectionLegacy(MAASServerTestCase):
    """Tests for the `BootSourceSelection` model."""

    def setUp(self):
        super().setUp()
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

    def test_can_create_selection(self):
        boot_source = BootSource(
            url="http://example.com", keyring_filename="/path/to/something"
        )
        boot_source.save()
        selection = BootSourceSelection(
            boot_source=boot_source,
            os="ubuntu",
            release="trusty",
            arches=["i386"],
            subarches=["generic"],
            labels=["release"],
        )
        selection.save()
        self.assertEqual(
            ("ubuntu", "trusty", ["i386"], ["generic"], ["release"]),
            (
                selection.os,
                selection.release,
                selection.arches,
                selection.subarches,
                selection.labels,
            ),
        )

    def test_deleting_boot_source_deletes_its_selections(self):
        # BootSource deletion cascade-deletes related
        # BootSourceSelections. This is implicit in Django but it's
        # worth adding a test for it all the same.
        boot_source = factory.make_BootSource()
        boot_source_selection = factory.make_BootSourceSelection(
            boot_source=boot_source
        )
        boot_source.delete()
        self.assertNotIn(
            boot_source_selection.id,
            [selection.id for selection in BootSourceSelection.objects.all()],
        )

    def test_to_dict_returns_dict(self):
        boot_source_selection = factory.make_BootSourceSelection()
        expected = {
            "os": boot_source_selection.os,
            "release": boot_source_selection.release,
            "arches": boot_source_selection.arches,
            "subarches": boot_source_selection.subarches,
            "labels": boot_source_selection.labels,
        }
        self.assertEqual(expected, boot_source_selection.to_dict())

    def test_cannt_delete_commissioning_os(self):
        boot_source_selection = factory.make_BootSourceSelection()
        commissioning_osystem, _ = Config.objects.get_or_create(
            name="commissioning_osystem"
        )
        commissioning_series, _ = Config.objects.get_or_create(
            name="commissioning_distro_series"
        )
        commissioning_osystem.value = boot_source_selection.os
        commissioning_osystem.save()
        commissioning_series.value = boot_source_selection.release
        commissioning_series.save()
        expected = (
            f"Unable to delete {commissioning_osystem.value} {commissioning_series.value}. "
            "It is the operating system used for commissioning."
        )
        with self.assertRaisesRegex(ValidationError, expected):
            boot_source_selection.delete()

    def test_force_delete_deletes_selection(self):
        boot_source_selection_legacy = factory.make_BootSourceSelection()
        boot_source_selection_new = factory.make_BootSourceSelectionNew(
            legacy_selection=boot_source_selection_legacy
        )

        boot_source_selection_legacy.force_delete()
        self.assertFalse(
            BootSourceSelection.objects.filter(
                id=boot_source_selection_legacy.id
            ).exists()
        )
        self.assertFalse(
            BootSourceSelectionNew.objects.filter(
                id=boot_source_selection_new.id
            ).exists()
        )

    def test_create_new_selections_single_arch(self):
        boot_source = factory.make_BootSource()
        boot_source_selection_legacy = factory.make_BootSourceSelection(
            boot_source=boot_source,
            os="ubuntu",
            release="focal",
            arches=["amd64"],
        )
        # boot_source_selection_legacy.create_new_selections()
        new_selections = BootSourceSelectionNew.objects.filter(
            boot_source=boot_source,
            os="ubuntu",
            release="focal",
            legacy_selection=boot_source_selection_legacy,
        ).all()
        self.assertEqual(1, len(new_selections))
        self.assertEqual("amd64", new_selections[0].arch)

    def test_create_new_selections_multiple_arch(self):
        boot_source = factory.make_BootSource()
        arches = ["i386", "amd64", "arm64"]
        boot_source_selection_legacy = factory.make_BootSourceSelection(
            boot_source=boot_source,
            os="ubuntu",
            release="focal",
            arches=arches,
        )
        new_selections = BootSourceSelectionNew.objects.filter(
            boot_source=boot_source,
            os="ubuntu",
            release="focal",
            legacy_selection=boot_source_selection_legacy,
        ).all()
        self.assertEqual(len(arches), len(new_selections))
        new_selection_arches = [selection.arch for selection in new_selections]
        for arch in arches:
            self.assertIn(arch, new_selection_arches)

    def test_create_new_selections_with_wildcard_arches(self):
        boot_source = factory.make_BootSource()
        arches = ["i386", "amd64", "arm64"]
        for arch in arches:
            factory.make_BootSourceCache(
                boot_source=boot_source,
                os="ubuntu",
                release="focal",
                arch=arch,
            )
        boot_source_selection_legacy = factory.make_BootSourceSelection(
            boot_source=boot_source,
            os="ubuntu",
            release="focal",
            arches=["*"],
        )
        new_selections = BootSourceSelectionNew.objects.filter(
            boot_source=boot_source,
            os="ubuntu",
            release="focal",
            legacy_selection=boot_source_selection_legacy,
        ).all()
        self.assertEqual(len(arches), len(new_selections))
        new_selection_arches = [selection.arch for selection in new_selections]
        for arch in arches:
            self.assertIn(arch, new_selection_arches)
