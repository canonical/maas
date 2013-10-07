# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test forms settings."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django import forms
from maasserver.forms_settings import (
    CONFIG_ITEMS,
    get_config_doc,
    get_config_field,
    get_config_form,
    )
from maasserver.models import Config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestGetConfigField(MAASServerTestCase):

    def test_get_config_field_validates_config_name(self):
        config_name = factory.getRandomString()
        self.assertRaises(
            forms.ValidationError, get_config_field, config_name)

    def test_get_config_field_creates_field(self):
        field = get_config_field('maas_name')
        label = CONFIG_ITEMS['maas_name']['form_kwargs']['label']
        self.assertEqual(label, field.label)


class TestGetConfigForm(MAASServerTestCase):

    def test_get_config_form_returns_initialized_form(self):
        maas_name = factory.getRandomString()
        Config.objects.set_config('maas_name', maas_name)
        form = get_config_form('maas_name')
        # The form contains only one field.
        self.assertItemsEqual(['maas_name'], form.fields)
        # The form is populated with the value of the 'maas_name'
        # config item.
        self.assertEqual(
            {'maas_name': maas_name}, form.initial)


class TestGetConfigDoc(MAASServerTestCase):

    def test_get_config_doc(self):
        doc = get_config_doc()
        # Just make sure that the doc looks okay.
        self.assertIn('maas_name', doc)
