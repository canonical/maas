# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootSourceSelection`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.models import (
    BootSource,
    BootSourceSelection,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestBootSourceSelection(MAASServerTestCase):
    """Tests for the `BootSourceSelection` model."""

    def test_can_create_selection(self):
        boot_source = BootSource(
            url="http://example.com",
            keyring_filename="/path/to/something")
        boot_source.save()
        selection = BootSourceSelection(
            boot_source=boot_source,
            os="ubuntu",
            release="trusty", arches=["i386"], subarches=["generic"],
            labels=["release"])
        selection.save()
        self.assertEqual(
            (
                "ubuntu",
                "trusty",
                ["i386"],
                ["generic"],
                ["release"]
            ),
            (
                selection.os,
                selection.release,
                selection.arches,
                selection.subarches,
                selection.labels,
            ))

    def test_deleting_boot_source_deletes_its_selections(self):
        # BootSource deletion cascade-deletes related
        # BootSourceSelections. This is implicit in Django but it's
        # worth adding a test for it all the same.
        boot_source = factory.make_BootSource()
        boot_source_selection = factory.make_BootSourceSelection(
            boot_source=boot_source)
        boot_source.delete()
        self.assertNotIn(
            boot_source_selection.id,
            [selection.id for selection in BootSourceSelection.objects.all()])

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
