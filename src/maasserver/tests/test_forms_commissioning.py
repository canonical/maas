# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for commissioning forms."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django.core.files.uploadedfile import SimpleUploadedFile
from maasserver.forms import (
    CommissioningForm,
    CommissioningScriptForm,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.forms import compose_invalid_choice_text
from metadataserver.models import CommissioningScript
from testtools.matchers import MatchesStructure


class TestCommissioningFormForm(MAASServerTestCase):

    def test_commissioningform_error_msg_lists_series_choices(self):
        form = CommissioningForm()
        field = form.fields['commissioning_distro_series']
        self.assertEqual(
            compose_invalid_choice_text(
                'commissioning_distro_series', field.choices),
            field.error_messages['invalid_choice'])


class TestCommissioningScriptForm(MAASServerTestCase):

    def test_creates_commissioning_script(self):
        content = factory.make_string().encode('ascii')
        name = factory.make_name('filename')
        uploaded_file = SimpleUploadedFile(content=content, name=name)
        form = CommissioningScriptForm(files={'content': uploaded_file})
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        new_script = CommissioningScript.objects.get(name=name)
        self.assertThat(
            new_script,
            MatchesStructure.byEquality(name=name, content=content))

    def test_raises_if_duplicated_name(self):
        content = factory.make_string().encode('ascii')
        name = factory.make_name('filename')
        factory.make_CommissioningScript(name=name)
        uploaded_file = SimpleUploadedFile(content=content, name=name)
        form = CommissioningScriptForm(files={'content': uploaded_file})
        self.assertEqual(
            (False, {'content': ["A script with that name already exists."]}),
            (form.is_valid(), form._errors))

    def test_rejects_whitespace_in_name(self):
        name = factory.make_name('with space')
        content = factory.make_string().encode('ascii')
        uploaded_file = SimpleUploadedFile(content=content, name=name)
        form = CommissioningScriptForm(files={'content': uploaded_file})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            ["Name contains disallowed characters (e.g. space or quotes)."],
            form._errors['content'])

    def test_rejects_quotes_in_name(self):
        name = factory.make_name("l'horreur")
        content = factory.make_string().encode('ascii')
        uploaded_file = SimpleUploadedFile(content=content, name=name)
        form = CommissioningScriptForm(files={'content': uploaded_file})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            ["Name contains disallowed characters (e.g. space or quotes)."],
            form._errors['content'])
