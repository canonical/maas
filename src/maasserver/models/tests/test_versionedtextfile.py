# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the VersionedTextFile model."""

__all__ = []


from django.core.exceptions import ValidationError
from maasserver.models.versionedtextfile import VersionedTextFile
from maasserver.testing.testcase import MAASServerTestCase
from testtools import ExpectedException
from testtools.matchers import (
    Equals,
    Is,
)


SAMPLE_TEXT = """\
Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor
incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis
nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu
fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in
culpa qui officia deserunt mollit anim id est laborum.
"""


class VersionedTextFileTest(MAASServerTestCase):

    def test_creates_versionedtextfile(self):
        textfile = VersionedTextFile(data=SAMPLE_TEXT)
        textfile.save()
        from_db = VersionedTextFile.objects.get(id=textfile.id)
        self.assertEqual(
            (from_db.id, from_db.data),
            (textfile.id, SAMPLE_TEXT))

    def test_contents_immutable(self):
        textfile = VersionedTextFile(data=SAMPLE_TEXT)
        textfile.save()
        textfile.data = "foo"
        with ExpectedException(ValidationError, ".*immutable.*"):
            textfile.save()

    def test_update_links_previous_revision(self):
        textfile = VersionedTextFile(data=SAMPLE_TEXT)
        textfile.save()
        textfile2 = textfile.update(SAMPLE_TEXT + " 2")
        from_db = VersionedTextFile.objects.get(id=textfile2.id)
        self.assertThat(from_db.data, Equals(SAMPLE_TEXT + " 2"))
        self.assertThat(from_db.previous_version, Equals(textfile))

    def test_update_with_no_changes_returns_current_vision(self):
        textfile = VersionedTextFile(data=SAMPLE_TEXT)
        textfile.save()
        textfile2 = textfile.update(SAMPLE_TEXT)
        from_db = VersionedTextFile.objects.get(id=textfile2.id)
        self.assertThat(from_db.data, Equals(SAMPLE_TEXT))
        self.assertThat(from_db.previous_version, Is(None))

    def test_deletes_upstream_revisions(self):
        textfile = VersionedTextFile(data=SAMPLE_TEXT)
        textfile.save()
        textfile.update(SAMPLE_TEXT + " 2")
        self.assertThat(VersionedTextFile.objects.count(), Equals(2))
        textfile.delete()
        self.assertThat(VersionedTextFile.objects.count(), Equals(0))

    def test_deletes_all_upstream_revisions_from_oldest_parent(self):
        textfile = VersionedTextFile(data=SAMPLE_TEXT)
        textfile.save()
        textfile2 = textfile.update(SAMPLE_TEXT + " 2")
        textfile3 = textfile.update(SAMPLE_TEXT + " 3")
        # Create a text file with multiple children.
        textfile2.update(SAMPLE_TEXT + " 20")
        textfile2.update(SAMPLE_TEXT + " 21")
        self.assertThat(VersionedTextFile.objects.count(), Equals(5))
        textfile3.get_oldest_version().delete()
        self.assertThat(VersionedTextFile.objects.count(), Equals(0))
