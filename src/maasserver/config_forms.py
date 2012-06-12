# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Config forms utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'DictCharField',
    'DictCharWidget',
    'SKIP_CHECK_NAME',
    ]

from collections import OrderedDict

from django import forms
from django.core import validators
from django.core.exceptions import ValidationError
from django.forms.fields import Field
from django.forms.util import ErrorList
from django.utils.safestring import mark_safe


SKIP_CHECK_NAME = 'skip_check'


class DictCharField(forms.MultiValueField):
    """A field to edit a dictionary of strings.  Each entry in the
    dictionary corresponds to a sub-field.

    The field is constructed with a list of tuples containing the name of the
    sub-fields and the sub-field themselves.  An optional parameter
    'skip_check' allows the storing of an arbitrary dictionary in the field,
    bypassing any validation made by the sub-fields.

    For instance, if we create a form with a single DictCharField:

    >>> from django import forms
    >>> class ExampleForm(forms.Form)
            example = DictCharField(
                [
                    ('field1', forms.CharField(label="Field 1"),
                    ('field2', forms.CharField(label="Field 2"),
                ])
    >>> data = QueryDict('example_field1=subvalue1&example_field2=subvalue2')
    >>> form = ExampleForm(data)
    >>> # The 'cleaned_data' of the 'example' field is populated with the
    >>> # values of the subfields.
    >>> form.cleaned_data['example']
    {'field1': 'subvalue1', 'field2': 'subvalue2'}
    """

    def __init__(self, field_items, skip_check=False, *args,
                 **kwargs):
        self.field_dict = OrderedDict(field_items)
        self.skip_check = skip_check
        # Make sure no subfield is named 'SKIP_CHECK_NAME'. If
        # skip_check is True this field will clash with the addtional
        # subfield added by the DictCharField constructor.  We perform
        # this check even if skip_check=False because having a field named
        # 'skip_check' that isn't used to actually skip the checks would be
        # very confusing.
        if SKIP_CHECK_NAME in self.field_dict.keys():
            raise RuntimeError(
                "'%s' is a reserved name "
                "(it can't be used to name a subfield)." % SKIP_CHECK_NAME)
        # if skip_check: add a BooleanField to the list of fields, this will
        # be used to skip the validation of the fields and accept arbitrary
        # data.
        if skip_check:
            self.field_dict[SKIP_CHECK_NAME] = forms.BooleanField(
                required=False)
        self.names = [name for name in self.field_dict.keys()]
        # Create the DictCharWidget with init values from the list of fields.
        self.fields = self.field_dict.values()
        self.widget = DictCharWidget(
            [field.widget for field in self.fields],
            self.names,
            [field.label for field in self.fields],
            skip_check=skip_check,
            )
        # Upcall to Field and not MultiValueField to avoid setting all the
        # subfields' 'required' attributes to False.
        Field.__init__(self, *args, **kwargs)

    def compress(self, data):
        """Returns a single value for the given list of values."""
        if data:
            if isinstance(data, dict):
                # If the data is a dict, this means that we're in the
                # situation where skip_check was true and we simply
                # return the dict.
                return data
            else:
                # Here data is the list of the values of the subfields,
                # return a dict with all the right keys:
                # For instance, for a DictCharField created with two
                # subfields 'field1' and 'field2', data will be
                # ['value1', 'value2'] and we will return:
                # {'field1': 'value1', 'field2': 'value2'}
                return dict(zip(self.names, data))
        return None

    def get_names(self):
        if self.skip_check:
            return self.names[:-1]
        else:
            return self.names

    def clean(self, value):
        """Validates every value in the given list. A value is validated
        against the corresponding Field in self.fields.

        This is an adapted version of Django's MultiValueField_ clean method.

        The differences are:
        - the method is split into clean_global_empty and
             clean_sub_fields;
        - the field and value corresponding to the SKIP_CHECK_NAME boolean
            field are removed;
        - each individual field 'required' attribute is used instead of the
            DictCharField's 'required' attribute.  This allows a more
            fine-grained control of what's required and what's not required.

        .. _MultiValueField: http://code.djangoproject.com/
            svn/django/tags/releases/1.3.1/django/forms/fields.py
        """
        skip_check = (
            self.skip_check and
            self.widget.widgets[-1].value_from_datadict(
                value, files=None, name=SKIP_CHECK_NAME))
        # Remove the 'skip_check' value from the list of values.
        try:
            value.pop(SKIP_CHECK_NAME)
        except KeyError:
            pass
        if skip_check:
            # If the skip_check option is on and the value of the boolean
            # field is true: don't perform any validation and simply return
            # the dictionary.
            return value
        else:
            self.clean_unknown_params(value)
            values = [value.get(name) for name in self.get_names()]
            result = self.clean_global_empty(values)
            if result is None:
                return None
            else:
                return self.clean_sub_fields(values)

    def clean_unknown_params(self, value):
        unknown_params = set(value.keys()).difference(self.get_names())
        if len(unknown_params) != 0:
            raise ValidationError(
                "Unknown parameter(s): %s." % ', '.join(unknown_params))

    def clean_global_empty(self, value):
        """Make sure the value is not empty and is thus suitable to be
        feed to the sub fields' validators."""
        if not value or isinstance(value, (list, tuple)):
            # value is considered empty if it is in
            # validators.EMPTY_VALUES, or if each of the subvalues is
            # None.
            is_empty = (
                value in validators.EMPTY_VALUES or
               len(filter(lambda x: x is not None, value)) == 0)
            if is_empty:
                if self.required:
                    raise ValidationError(self.error_messages['required'])
                else:
                    return None
            else:
                return True
        else:
            raise ValidationError(self.error_messages['invalid'])

    def clean_sub_fields(self, value):
        """'value' being the list of the values of the subfields, validate
        each subfield."""
        clean_data = []
        errors = ErrorList()
        # Remove the field corresponding to the SKIP_CHECK_NAME boolean field
        # if required.
        fields = self.fields if not self.skip_check else self.fields[:-1]
        for index, field in enumerate(fields):
            try:
                field_value = value[index]
            except IndexError:
                field_value = None
            # Check the field's 'required' field instead of the global
            # 'required' field to allow subfields to be required or not.
            if field.required and field_value in validators.EMPTY_VALUES:
                errors.append(
                    '%s: %s' % (field.label, self.error_messages['required']))
                continue
            try:
                clean_data.append(field.clean(field_value))
            except ValidationError, e:
                # Collect all validation errors in a single list, which we'll
                # raise at the end of clean(), rather than raising a single
                # exception for the first error we encounter.
                errors.extend(
                    ['%s: %s' % (field.label, message)
                    for message in e.messages])
        if errors:
            raise ValidationError(errors)

        out = self.compress(clean_data)
        self.validate(out)
        return out


def get_all_prefixed_values(data, name):
    """From a dictionary, extract a sub-dictionary of all the keys/values for
    which the key starts with a particular prefix.  In the resulting
    dictionary, strip the prefix from the keys.

    >>> get_all_prefixed_values(
        {'prefix_test': 'a', 'key': 'b'}, 'prefix_')
    {'test': 'a'}
    """
    result = {}
    for key, value in data.items():
        if key.startswith(name):
            new_key = key[len(name):]
            result[new_key] = value
    return result


class DictCharWidget(forms.widgets.MultiWidget):
    """A widget to display the content of a dictionary.  Each key will
    correspond to a subwidget.  Although there is no harm in using this class
    directly, note that this is mostly destined to be used internally
    by DictCharField.

    The customization compared to Django's MultiWidget_ are:
    - DictCharWidget displays all the subwidgets inside a fieldset tag;
    - DictCharWidget displays a label for each subwidget;
    - DictCharWidget names each subwidget 'main_widget_sub_widget_name'
        instead of 'main_widget_0';
    - DictCharWidget has the (optional) ability to skip all the validation
        and instead fetch all the values prefixed by 'main_widget_' in the
        input data.

    To achieve that, we customize:
    - 'render' which returns the HTML code to display this widget;
    - 'id_for_label' which return the HTML ID attribute for this widget
        for use by a label.  This widget is composed of multiple widgets so
        the id of the first widget is used;
    - 'value_from_datadict' which fetches the value of the data to be
        processed by this form to give a 'data' dictionary.  We need to
        customize that because we've changed the way MultiWidget names
        sub-widgets;
    - 'decompress' which takes a single "compressed" value and returns a list
        of values to be used by the widgets.

    .. _MultiWidget: http://code.djangoproject.com/
        svn/django/tags/releases/1.3.1/django/forms/widgets.py
    """

    def __init__(self, widgets, names, labels, skip_check=False, attrs=None):
        self.names = names
        self.labels = labels
        self.skip_check = skip_check
        super(DictCharWidget, self).__init__(widgets, attrs)

    def render(self, name, value, attrs=None):
        # value is a list of values, each corresponding to a widget
        # in self.widgets.
        # Do not display the 'skip_check' boolean widget.
        if self.skip_check:
            widgets = self.widgets[:-1]
        else:
            widgets = self.widgets
        if not isinstance(value, list):
            value = self.decompress(value)
        if len(widgets) == 0:
            return mark_safe(self.format_output(''))

        output = ['<fieldset>']
        final_attrs = self.build_attrs(attrs)
        id_ = final_attrs.get('id', None)

        for index, widget in enumerate(widgets):
            try:
                widget_value = value[index]
            except IndexError:
                widget_value = None
            if id_:
                final_attrs = dict(
                    final_attrs, id='%s_%s' % (id_, self.names[index]))
            # Add label to each sub-field.
            if id_:
                label_for = ' for="%s"' % final_attrs['id']
            else:
                label_for = ''
            output.append(
                '<label%s>%s</label>' % (
                    label_for, self.labels[index]))
            output.append(
                widget.render(
                    '%s_%s' % (name, self.names[index]), widget_value,
                    final_attrs))
        output.append('</fieldset>')
        return mark_safe(self.format_output(output))

    def id_for_label(self, id_):
        """Returns the HTML ID attribute of this Widget.  Since this is a
        widget with multiple HTML elements, this method returns an ID
        corresponding to the first ID in the widget's tags."""
        # See the comment for RadioSelect.id_for_label()
        if id_:
            id_ += '_%s' % self.names[0]
        return id_

    def value_from_datadict(self, data, files, name):
        """Extract the values for this widget from a data dict (QueryDict).
        :param data: The data dict (usually request.data or request.GET where
            request is a django.http.HttpRequest).
        :type data: dict
        :param files: The files dict (usually request.FILES where request is a
            django.http.HttpRequest).
        :type files: dict
        :param name: The name of the widget.
        :type name: basestring
        :return: The extracted values as a dictionary.
        :rtype: dict or list
        """
        return get_all_prefixed_values(data, name + '_')

    def decompress(self, value):
        """Returns a list of decompressed values for the given compressed
        value.  The given value can be assumed to be valid, but not
        necessarily non-empty."""
        if value not in validators.EMPTY_VALUES:
            return [value.get(name, None) for name in self.names]
        else:
            return [None] * len(self.names)
