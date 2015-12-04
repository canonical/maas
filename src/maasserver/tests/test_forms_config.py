# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `ConfigForm`."""

__all__ = []

from django import forms
from maasserver.forms import ConfigForm
from maasserver.models import Config
from maasserver.models.config import DEFAULT_CONFIG
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestOptionForm(ConfigForm):
    field1 = forms.CharField(label="Field 1", max_length=10)
    field2 = forms.BooleanField(label="Field 2", required=False)


class TestValidOptionForm(ConfigForm):
    maas_name = forms.CharField(label="Field 1", max_length=10)


class TestCompositeForm(ConfigForm):
    config_fields = ['maas_name']

    maas_name = forms.CharField(label="Field 1", max_length=10)
    non_config_field = forms.CharField(label="Field 2", max_length=10)


class ConfigFormTest(MAASServerTestCase):

    def test_form_valid_saves_into_db(self):
        value = factory.make_string(10)
        form = TestValidOptionForm({'maas_name': value})
        result = form.save()

        self.assertTrue(result, form._errors)
        self.assertEqual(value, Config.objects.get_config('maas_name'))

    def test_form_rejects_unknown_settings(self):
        value = factory.make_string(10)
        value2 = factory.make_string(10)
        form = TestOptionForm({'field1': value, 'field2': value2})
        valid = form.is_valid()

        self.assertFalse(valid, form._errors)
        self.assertIn('field1', form._errors)
        self.assertIn('field2', form._errors)

    def test_form_invalid_does_not_save_into_db(self):
        value_too_long = factory.make_string(20)
        form = TestOptionForm({'field1': value_too_long, 'field2': False})
        result = form.save()

        self.assertFalse(result, form._errors)
        self.assertIn('field1', form._errors)
        self.assertIsNone(Config.objects.get_config('field1'))
        self.assertIsNone(Config.objects.get_config('field2'))

    def test_form_loads_initial_values(self):
        value = factory.make_string()
        Config.objects.set_config('field1', value)
        form = TestOptionForm()

        self.assertItemsEqual(['field1'], form.initial)
        self.assertEqual(value, form.initial['field1'])

    def test_form_loads_initial_values_from_default_value(self):
        value = factory.make_string()
        DEFAULT_CONFIG['field1'] = value
        form = TestOptionForm()

        self.assertItemsEqual(['field1'], form.initial)
        self.assertEqual(value, form.initial['field1'])

    def test_validates_composite_form(self):
        value1 = factory.make_string(5)
        value2 = factory.make_string(5)
        form = TestCompositeForm(
            {'maas_name': value1, 'non_config_field': value2})
        result = form.save()

        self.assertTrue(result, form._errors)
        self.assertEqual(value1, Config.objects.get_config('maas_name'))
