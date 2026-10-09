# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootSourceSelection`."""

from unittest.mock import call

from django.core.exceptions import ValidationError

from maasserver.models import BootSource, BootSourceSelection, Config
import maasserver.models.bootsourceselection as bootsourceselection_module
from maasserver.models.signals import bootsources
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestBootSourceSelection(MAASServerTestCase):
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
        self.patch(bootsourceselection_module, "stop_workflow")
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

    def test_delete_stops_temporal_workflows(self):
        stop_wf_mock = self.patch(bootsourceselection_module, "stop_workflow")
        boot_source_selection = factory.make_BootSourceSelection(
            arches=["amd64"]
        )
        boot_source_selection.delete()
        stop_wf_mock.assert_called_once_with(
            f"sync-selection:{boot_source_selection.id}"
        )

    def test_delete_stops_temporal_workflows_multiple_selections(self):
        stop_wf_mock = self.patch(bootsourceselection_module, "stop_workflow")
        boot_source_selections = [
            factory.make_BootSourceSelection(arches=["amd64"]),
            factory.make_BootSourceSelection(arches=["amd64"]),
        ]
        for selection in boot_source_selections:
            selection.delete()
        calls = [
            call(f"sync-selection:{s.id}") for s in boot_source_selections
        ]
        stop_wf_mock.assert_has_calls(calls, any_order=True)
