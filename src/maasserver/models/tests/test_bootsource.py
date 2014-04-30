# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the bootsource model module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django.core.exceptions import ValidationError
from maasserver.models.bootsource import (
    BootSource,
    BootSourceSelection,
    )
from maastesting.testcase import MAASTestCase
from maasserver.testing.factory import factory


class TestBootSource(MAASTestCase):
    """Tests for the `BootSource` model."""

    def test_valid_boot_source_is_valid(self):
        cluster = factory.make_node_group()
        boot_source = BootSource(
            cluster=cluster,
            url="http://example.com",
            keyring_filename="/path/to/something")
        boot_source.save()
        self.assertEqual(
            [boot_source.id],
            [source.id for source in BootSource.objects.all()])

    def test_cannot_set_keyring_data_and_filename(self):
        # A BootSource cannot have both a keyring filename and keyring
        # data. Attempting to set both will raise an error.
        cluster = factory.make_node_group()
        boot_source = BootSource(
            cluster=cluster, url="http://example.com",
            keyring_filename="/path/to/something",
            keyring_data=b"blahblahblahblah")
        self.assertRaises(ValidationError, boot_source.clean)

    def test_cannot_leave_keyring_data_and_filename_unset(self):
        cluster = factory.make_node_group()
        boot_source = BootSource(
            cluster=cluster, url="http://example.com",
            keyring_filename="", keyring_data=b"")
        self.assertRaises(ValidationError, boot_source.clean)


class TestBootSourceSelection(MAASTestCase):
    """Tests for the `BootSourceSelection` model."""

    def test_can_create_selection(self):
        cluster = factory.make_node_group()
        boot_source = BootSource(
            cluster=cluster,
            url="http://example.com",
            keyring_filename="/path/to/something")
        boot_source.save()
        selection = BootSourceSelection(
            boot_source=boot_source,
            release="trusty", arches=["i386"], subarches=["generic"],
            labels=["release"])
        selection.save()
        self.assertEqual(
            (
                "trusty",
                ["i386"],
                ["generic"],
                ["release"]
            ),
            (
                selection.release,
                selection.arches,
                selection.subarches,
                selection.labels,
            ))
