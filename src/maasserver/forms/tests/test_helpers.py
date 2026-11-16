# Copyright 2014-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for forms helpers."""

from django.forms import CharField

from maasserver.forms import MAASModelForm
from maasserver.testing.testcase import MAASLegacyTransactionServerTestCase
from maasserver.tests.models import GenericTestModel


class TestMAASModelForm(MAASLegacyTransactionServerTestCase):
    apps = ["maasserver.tests"]

    def test_model_class_from_UI_has_hidden_field(self):
        class TestClass(MAASModelForm):
            class Meta:
                model = GenericTestModel
                fields = ["field"]

        form = TestClass(ui_submission=True)
        self.assertIn("ui_submission", form.fields)
        self.assertTrue(
            form.fields["ui_submission"].widget.is_hidden,
            "ui_submission field is not 'hidden'",
        )

    def test_model_class_from_API_doesnt_have_hidden_field(self):
        class TestClass(MAASModelForm):
            class Meta:
                model = GenericTestModel
                fields = ["field"]

        form = TestClass()
        self.assertNotIn("ui_submission", form.fields)

    def test_hidden_field_is_available_to_all_field_cleaning_methods(self):
        class EarlyFieldMixin:
            """Mixin to sneak a field into our form early.

            Proves that the `ui_submission` field is present for all field
            validators, regardless of the order in which the fields were added
            to the form.
            """

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fields["early_field"] = CharField(required=False)

        class TestForm(EarlyFieldMixin, MAASModelForm):
            extra_field = CharField(required=False)

            def clean_early_field(self, *args, **kwargs):
                """Cleaner for `GenericTestModel.field`."""
                self.while_early_field = "ui_submission" in self.cleaned_data

            def clean_field(self, *args, **kwargs):
                """Cleaner for `GenericTestModel.field`."""
                self.while_field = "ui_submission" in self.cleaned_data

            def clean_extra_field(self, *args, **kwargs):
                """Cleaner for `TestForm.extra_field`."""
                self.while_extra_field = "ui_submission" in self.cleaned_data

            class Meta:
                model = GenericTestModel
                fields = ("field",)

        form = TestForm(ui_submission=True, data={})
        self.assertTrue(form.is_valid(), form._errors)
        self.assertTrue(form.while_early_field)
        self.assertTrue(form.while_field)
        self.assertTrue(form.while_extra_field)
