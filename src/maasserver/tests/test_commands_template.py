# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `template` command."""

__all__ = []


from io import StringIO

from django.core.management import (
    call_command,
    CommandError,
)
from maasserver.data import templates
from maasserver.models import (
    Template,
    VersionedTextFile,
)
from maasserver.testing.testcase import MAASServerTestCase
from testtools import ExpectedException
from testtools.matchers import (
    Contains,
    Equals,
    Not,
)


class TestTemplateCommand(MAASServerTestCase):

    def test__fails_and_takes_no_action_with_no_arguments(self):
        with ExpectedException(CommandError):
            call_command('template')
        self.assertThat(Template.objects.count(), Equals(0))

    def test__fixture_contains_no_templates_by_default(self):
        self.assertThat(Template.objects.count(), Equals(0))
        self.assertThat(VersionedTextFile.objects.count(), Equals(0))

    def test__populates_default_templates(self):
        stdout = StringIO()
        call_command(
            'template', 'update-defaults', verbosity=1, stdout=stdout)
        result = stdout.getvalue()
        self.assertThat(Template.objects.count(), Equals(len(templates)))
        self.assertThat(result, Contains("Imported default:"))

    def test__skips_unmodified_templates(self):
        stdout = StringIO()
        call_command('template', 'update-defaults', stdout=stdout)
        call_command('template', 'update-defaults', stdout=stdout)
        result = stdout.getvalue()
        expected_templates = len(templates)
        self.assertThat(result, Contains("Skipped:"))
        self.assertThat(Template.objects.count(), Equals(expected_templates))
        self.assertThat(
            VersionedTextFile.objects.count(), Equals(expected_templates))

    def test__updates_existing_templates_and_keeps_previous_version(self):
        for filename in templates:
            # Create the templates with garbage data, so they'll need to
            # be updated.
            Template.objects.create_or_update_default(filename, "x" + filename)
        self.assertThat(Template.objects.count(), Equals(len(templates)))
        stdout = StringIO()
        call_command(
            'template', 'update-defaults', verbosity=1, stdout=stdout)
        result = stdout.getvalue()
        self.assertThat(Template.objects.count(), Equals(len(templates)))
        self.assertThat(result, Not(Contains("Imported default:")))
        self.assertThat(result, Contains("Updated default:"))
        for filename in templates:
            template = Template.objects.get(filename=filename)
            previous_data = template.default_version.previous_version.data
            self.assertThat(previous_data, Equals("x" + filename))
            data = template.default_version.data
            self.assertThat(data, Equals(templates[filename]))

    def test__show_command(self):
        call_command('template', 'update-defaults', verbosity=0)
        for file in templates:
            stdout = StringIO()
            args = ['show', file]
            call_command('template', *args, stdout=stdout)
            result = stdout.getvalue()
            self.assertThat(result, Equals(templates[file]))

    def test__show_command_shows_modified(self):
        call_command('template', 'update-defaults', verbosity=0)
        for template in Template.objects.all():
            template.update("x")
            template.save()
        for file in templates:
            stdout = StringIO()
            args = ['show', file]
            call_command('template', *args, stdout=stdout)
            result = stdout.getvalue()
            self.assertThat(result, Equals("x"))

    def test__show_default_command_shows_default(self):
        call_command('template', 'update-defaults', verbosity=0)
        for template in Template.objects.all():
            template.update("x")
            template.save()
        for file in templates:
            stdout = StringIO()
            args = ['show-default', file]
            call_command('template', *args, stdout=stdout)
            result = stdout.getvalue()
            self.assertThat(result, Equals(templates[file]))

    def test__deletes_related_versioned_files_after_modification(self):
        for filename in templates:
            # Create the templates with garbage data, so they'll need to
            # be updated.
            Template.objects.create_or_update_default(filename, "x" + filename)
        num_templates = len(templates)
        self.assertThat(Template.objects.count(), Equals(num_templates))
        self.assertThat(
            VersionedTextFile.objects.count(), Equals(num_templates))
        # Force each template to be updated
        call_command(
            'template', 'update-defaults', verbosity=1)
        self.assertThat(
            VersionedTextFile.objects.count(), Equals(num_templates * 2))
        stdout = StringIO()
        call_command(
            'template', 'force-delete-all', verbosity=1, stdout=stdout)
        result = stdout.getvalue()
        self.assertThat(Template.objects.count(), Equals(0))
        self.assertThat(
            result, Contains("Deleting %d templates" % num_templates))
        self.assertThat(VersionedTextFile.objects.count(), Equals(0))
