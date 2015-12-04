# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test forms settings."""

__all__ = []


from django import forms
from maasserver.forms import BootSourceSettingsForm
from maasserver.forms_settings import (
    CONFIG_ITEMS,
    get_config_doc,
    get_config_field,
    get_config_form,
)
from maasserver.models import Config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.forms import compose_invalid_choice_text


class TestGetConfigField(MAASServerTestCase):

    def test_get_config_field_validates_config_name(self):
        config_name = factory.make_string()
        self.assertRaises(
            forms.ValidationError, get_config_field, config_name)

    def test_get_config_field_creates_field(self):
        field = get_config_field('maas_name')
        label = CONFIG_ITEMS['maas_name']['form_kwargs']['label']
        self.assertEqual(label, field.label)


class TestGetConfigForm(MAASServerTestCase):

    def test_get_config_form_returns_initialized_form(self):
        maas_name = factory.make_string()
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


class TestSpecificConfigSettings(MAASServerTestCase):

    def test_commissioning_distro_series_config(self):
        field = get_config_field('commissioning_distro_series')
        self.assertEqual(
            compose_invalid_choice_text(
                'commissioning_distro_series', field.choices),
            field.error_messages['invalid_choice'])

    def test_upstream_dns_accepts_ip_list(self):
        field = get_config_field('upstream_dns')
        ips1 = [factory.make_ip_address() for _ in range(3)]
        ips2 = [factory.make_ip_address() for _ in range(3)]
        input = ' '.join(ips1) + ' ' + ','.join(ips2)
        self.assertEqual(' '.join(ips1 + ips2), field.clean(input))


class TestBootSourceSettingsForm(MAASServerTestCase):

    def setUp(self):
        super(TestBootSourceSettingsForm, self).setUp()
        self.form_data = {
            'boot_source_url': 'http://example.com/good',
            'boot_source_keyring': '/a/path'}

    def test_happy_with_good_data(self):
        form = BootSourceSettingsForm(data=self.form_data)
        self.assertTrue(form.is_valid())
        self.assertEqual(
            "http://example.com/good",
            form.cleaned_data['boot_source_url'])
        self.assertEqual("/a/path", form.cleaned_data['boot_source_keyring'])

    def test_unhappy_by_default(self):
        form = BootSourceSettingsForm()
        self.assertFalse(form.is_valid())

    def test_reject_leading_spaces_in_boot_source_url(self):
        # https://bugs.launchpad.net/maas/+bug/1499062
        self.form_data['boot_source_url'] = ' http://example.com/leadingspace'
        form = BootSourceSettingsForm(data=self.form_data)
        self.assertFalse(form.is_valid())

    def test_reject_non_url_in_boot_source_url(self):
        self.form_data['boot_source_url'] = 'not_a_URL'
        form = BootSourceSettingsForm(data=self.form_data)
        self.assertFalse(form.is_valid())

    def test_strips_boot_source_keyring(self):
        self.form_data['boot_source_keyring'] = ' /a/path '
        form = BootSourceSettingsForm(data=self.form_data)
        self.assertTrue(form.is_valid())
        self.assertEqual("/a/path", form.cleaned_data['boot_source_keyring'])
