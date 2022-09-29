# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Template model."""

from maasserver.models import VersionedTextFile
from maasserver.models.template import Template
from maasserver.testing.testcase import MAASServerTestCase


class TemplateTest(MAASServerTestCase):
    def test_creates_template(self):
        default_version = VersionedTextFile(data="foo")
        default_version.save()
        template = Template(
            default_version=default_version, filename="foo/bar"
        )
        template.save()
        from_db = Template.objects.get(id=template.id)
        self.assertEqual("foo", from_db.default_version.data)

    def test_creates_or_update_default_creates_new(self):
        Template.objects.create_or_update_default("foo", "bar")
        from_db = Template.objects.get(filename="foo")
        self.assertEqual("bar", from_db.value)

    def test_creates_or_update_default_updates_existing(self):
        Template.objects.create_or_update_default("foo", "bar")
        Template.objects.create_or_update_default("foo", "bar2")
        from_db = Template.objects.get(filename="foo")
        self.assertEqual("bar2", from_db.value)

    def test_delete_related_versionedtextfile_deletes_template(self):
        Template.objects.create_or_update_default("foo", "bar")
        self.assertEqual(1, Template.objects.count())
        VersionedTextFile.objects.all().delete()
        self.assertEqual(0, Template.objects.count())
