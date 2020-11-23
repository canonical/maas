# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test config forms utilities."""


from unittest.mock import ANY, Mock

from django import forms
from django.forms import widgets
from django.http import QueryDict
from lxml.etree import XPath
from lxml.html import fromstring

from maasserver.config_forms import (
    DictCharField,
    DictCharWidget,
    get_all_prefixed_values,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith


class TestDictCharField(MAASServerTestCase):
    def test_DictCharField_init(self):
        testField = DictCharField(
            [
                ("field_a", forms.CharField(label="Field a")),
                ("field_b", forms.CharField(label="Field b")),
                ("field_c", forms.CharField(label="Field c")),
            ]
        )
        self.assertEqual(["field_a", "field_b", "field_c"], testField.names)
        self.assertEqual(
            ["field_a", "field_b", "field_c"], testField.widget.names
        )
        # In Django 1.11, widgets are deep-copied in the Field constructor,
        # so instead of comparing directly, we compare their types and names.
        expected_widgets = [
            type(widget) for widget in testField.widget.widgets
        ]
        got_widgets = [
            type(field.widget) for field in testField.field_dict.values()
        ]
        self.assertEqual(got_widgets, expected_widgets)

    def test_DictCharField_does_not_allow_subfield_named_skip_check(self):
        # Creating a DictCharField with a subfield named 'skip_check' is not
        # allowed.
        self.assertRaises(
            RuntimeError,
            DictCharField,
            [("skip_check", forms.CharField(label="Skip Check"))],
        )


class TestFormWithDictCharField(MAASServerTestCase):
    def test_DictCharField_processes_QueryDict_into_a_dict(self):
        class FakeForm(forms.Form):
            multi_field = DictCharField(
                [
                    ("field_a", forms.CharField(label="Field a")),
                    (
                        "field_b",
                        forms.CharField(
                            label="Field b", required=False, max_length=3
                        ),
                    ),
                    (
                        "field_c",
                        forms.CharField(label="Field c", required=False),
                    ),
                ]
            )

        fielda_value = factory.make_string()
        fieldc_value = factory.make_string()
        data = QueryDict(
            "multi_field_field_a=%s&multi_field_field_c=%s"
            % (fielda_value, fieldc_value)
        )

        form = FakeForm(data)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            {"field_a": fielda_value, "field_b": "", "field_c": fieldc_value},
            form.cleaned_data["multi_field"],
        )

    def test_DictCharField_honors_field_constraint(self):
        class FakeForm(forms.Form):
            multi_field = DictCharField(
                [
                    ("field_a", forms.CharField(label="Field a")),
                    (
                        "field_b",
                        forms.CharField(
                            label="Field b", required=False, max_length=3
                        ),
                    ),
                ]
            )

        # Create a value that will fail validation because it's too long.
        fielda_value = factory.make_string(10)
        data = QueryDict("multi_field_field_b=%s" % fielda_value)
        form = FakeForm(data)

        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "multi_field": [
                    "Field a: This field is required.",
                    "Field b: Ensure this value has at "
                    "most 3 characters (it has 10).",
                ]
            },
            form.errors,
        )

    def test_DictCharField_skip_check_true_skips_validation(self):
        # Create a value that will fail validation because it's too long.
        field_name = factory.make_string(10)
        field_value = factory.make_string(10)
        # multi_field_skip_check=true will make the form accept the value
        # even if it's not valid.
        data = QueryDict(
            "multi_field_%s=%s&multi_field_skip_check=true"
            % (field_name, field_value)
        )

        class FakeFormSkip(forms.Form):
            multi_field = DictCharField(
                [(field_name, forms.CharField(label="Unused", max_length=3))],
                skip_check=True,
            )

        form = FakeFormSkip(data)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            {field_name: field_value}, form.cleaned_data["multi_field"]
        )

    def test_DictCharField_skip_check_false(self):
        # Create a value that will fail validation because it's too long.
        field_value = factory.make_string(10)
        field_name = factory.make_string()
        field_label = factory.make_string()
        # Force the check with multi_field_skip_check=false.
        data = QueryDict(
            "multi_field_%s=%s&multi_field_skip_check=false"
            % (field_name, field_value)
        )

        class FakeFormSkip(forms.Form):
            multi_field = DictCharField(
                [
                    (
                        field_name,
                        forms.CharField(label=field_label, max_length=3),
                    )
                ],
                skip_check=True,
            )

        form = FakeFormSkip(data)

        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "multi_field": [
                    "%s: Ensure this value has at most 3 characters "
                    "(it has 10)." % field_label
                ]
            },
            form.errors,
        )

    def test_DictCharField_accepts_required_false(self):
        # A form where the DictCharField instance is constructed with
        # required=False.
        class FakeFormRequiredFalse(forms.Form):
            multi_field = DictCharField(
                [("field_a", forms.CharField(label="Field a"))], required=False
            )
            char_field = forms.CharField(label="Field a")

        char_value = factory.make_string(10)
        data = QueryDict("char_field=%s" % char_value)
        form = FakeFormRequiredFalse(data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            {"char_field": char_value, "multi_field": None}, form.cleaned_data
        )

    def test_DictCharField_sets_default_value_for_subfields(self):
        default_value = factory.make_name("default_value")
        multi_field = DictCharField(
            [
                (
                    "field_a",
                    forms.CharField(label="Field a", initial=default_value),
                )
            ],
            required=False,
        )
        self.assertEquals(
            default_value, multi_field.clean_sub_fields("")["field_a"]
        )


class TestUtilities(MAASServerTestCase):
    def test_get_all_prefixed_values_returns_sub_dict(self):
        inputs = [
            {"prefix_test": "a", "key": "b", "prefix_2": "c"},
            {},
            {"b": factory.make_string()},
        ]
        prefix = "prefix_"
        expected = [{"test": "a", "2": "c"}, {}, {}]
        self.assertEqual(
            expected,
            [get_all_prefixed_values(data, prefix) for data in inputs],
        )


class TestDictCharWidget(MAASServerTestCase):
    def test_DictCharWidget_id_for_label_uses_first_fields_name(self):
        names = [factory.make_string()]
        initials = []
        labels = [factory.make_string()]
        widget = DictCharWidget(
            [widgets.TextInput, widgets.TextInput], names, initials, labels
        )
        self.assertEqual(" _%s" % names[0], widget.id_for_label(" "))

    def test_DictCharWidget_renders_fieldset_with_label_and_field_names(self):
        names = [factory.make_string(), factory.make_string()]
        initials = []
        labels = [factory.make_string(), factory.make_string()]
        values = [factory.make_string(), factory.make_string()]
        widget = DictCharWidget(
            [widgets.TextInput, widgets.TextInput, widgets.CheckboxInput],
            names,
            initials,
            labels,
            skip_check=True,
        )
        name = factory.make_string()
        html_widget = fromstring(
            "<root>" + widget.render(name, values) + "</root>"
        )
        widget_names = XPath("fieldset/input/@name")(html_widget)
        widget_labels = XPath("fieldset/label/text()")(html_widget)
        widget_values = XPath("fieldset/input/@value")(html_widget)
        expected_names = [
            "%s_%s" % (name, widget_name) for widget_name in names
        ]
        self.assertEqual(
            [expected_names, labels, values],
            [widget_names, widget_labels, widget_values],
        )

    def test_empty_DictCharWidget_renders_as_empty_string(self):
        widget = DictCharWidget(
            [widgets.CheckboxInput], [], [], [], skip_check=True
        )
        self.assertEqual("", widget.render(factory.make_string(), ""))

    def test_DictCharWidget_value_from_datadict_values_from_data(self):
        # 'value_from_datadict' extracts the values corresponding to the
        # field as a dictionary.
        names = [factory.make_string(), factory.make_string()]
        initials = []
        labels = [factory.make_string(), factory.make_string()]
        name = factory.make_string()
        field_1_value = factory.make_string()
        field_2_value = factory.make_string()
        # Create a query string with the field2 before the field1 and another
        # (unknown) value.
        data = QueryDict(
            "%s_%s=%s&%s_%s=%s&%s=%s"
            % (
                name,
                names[1],
                field_2_value,
                name,
                names[0],
                field_1_value,
                factory.make_string(),
                factory.make_string(),
            )
        )
        widget = DictCharWidget(
            [widgets.TextInput, widgets.TextInput], names, initials, labels
        )
        self.assertEqual(
            {names[0]: field_1_value, names[1]: field_2_value},
            widget.value_from_datadict(data, None, name),
        )

    def test_DictCharWidget_renders_with_empty_string_as_input_data(self):
        names = [factory.make_string(), factory.make_string()]
        initials = []
        labels = [factory.make_string(), factory.make_string()]
        widget = DictCharWidget(
            [widgets.TextInput, widgets.TextInput, widgets.CheckboxInput],
            names,
            initials,
            labels,
            skip_check=True,
        )
        name = factory.make_string()
        html_widget = fromstring(
            "<root>" + widget.render(name, "") + "</root>"
        )
        widget_names = XPath("fieldset/input/@name")(html_widget)
        widget_labels = XPath("fieldset/label/text()")(html_widget)
        expected_names = [
            "%s_%s" % (name, widget_name) for widget_name in names
        ]
        self.assertEqual(
            [expected_names, labels], [widget_names, widget_labels]
        )

    def test_DictCharWidget_renders_with_initial_when_no_value(self):
        """Widgets should use initial value if rendered without value."""
        names = [factory.make_name()]
        initials = [factory.make_name()]
        labels = [factory.make_name()]
        mock_widget = Mock()
        mock_widget.configure_mock(**{"render.return_value": ""})
        widget = DictCharWidget(
            [mock_widget, widgets.TextInput],
            names,
            initials,
            labels,
            skip_check=True,
        )
        widget.render("foo", [])

        self.assertThat(
            mock_widget.render, MockCalledOnceWith(ANY, initials[0], ANY)
        )
