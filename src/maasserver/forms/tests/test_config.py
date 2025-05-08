# Copyright 2014-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from typing import Optional

from django import forms
from django.http import HttpRequest

from maasserver.enum import ENDPOINT_CHOICES
from maasserver.forms import ConfigForm
from maasserver.models import Config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
import maasservicelayer.models.configurations as maascommon_configuration
import maasservicelayer.services.configurations as servicelayer_config_module


class TestOptionForm(ConfigForm):
    field1 = forms.CharField(label="Field 1", max_length=10)
    field2 = forms.BooleanField(label="Field 2", required=False)


class TestValidOptionForm(ConfigForm):
    maas_name = forms.CharField(label="Field 1", max_length=10)


class TestCompositeForm(ConfigForm):
    config_fields = ["maas_name"]

    maas_name = forms.CharField(label="Field 1", max_length=10)
    non_config_field = forms.CharField(label="Field 2", max_length=10)


class TestConfigForm(MAASServerTestCase):
    def _get_config_stub(self, config_name, default_value):
        class Field1Stub(maascommon_configuration.Config[Optional[str]]):
            name = config_name
            default = default_value

        return Field1Stub

    def _get_factory_config_stub(self, config_name, default_value):
        class ConfigFactoryStub(maascommon_configuration.ConfigFactory):
            @classmethod
            def get_config_model(cls, name):
                if name == config_name:
                    return self._get_config_stub(config_name, default_value)
                else:
                    raise ValueError("Unkwnown config.")

        return ConfigFactoryStub

    def test_form_valid_saves_into_db(self):
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        request = HttpRequest()
        request.user = factory.make_User()
        value = factory.make_string(10)
        form = TestValidOptionForm({"maas_name": value})
        result = form.save(endpoint, request)

        self.assertTrue(result, form._errors)
        self.assertEqual(value, Config.objects.get_config("maas_name"))

    def test_form_rejects_unknown_settings(self):
        value = factory.make_string(10)
        value2 = factory.make_string(10)
        form = TestOptionForm({"field1": value, "field2": value2})
        valid = form.is_valid()

        self.assertFalse(valid, form._errors)
        self.assertIn("field1", form._errors)
        self.assertIn("field2", form._errors)

    def test_form_invalid_does_not_save_into_db(self):
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        request = HttpRequest()
        request.user = factory.make_User()
        value_too_long = factory.make_string(20)
        form = TestOptionForm({"field1": value_too_long, "field2": False})
        result = form.save(endpoint, request)

        self.assertFalse(result, form._errors)
        self.assertIn("field1", form._errors)
        self.assertIsNone(Config.objects.get_config("field1"))
        self.assertIsNone(Config.objects.get_config("field2"))

    def test_form_loads_initial_values(self):
        value = factory.make_string()
        Config.objects.set_config("field1", value)
        form = TestOptionForm()

        self.assertEqual({"field1": value}, form.initial)

    def test_form_loads_initial_values_from_default_value(self):
        value = factory.make_string()
        self.patch(
            servicelayer_config_module,
            "ConfigFactory",
            value=self._get_factory_config_stub("field1", value),
        )
        form = TestOptionForm()
        self.assertEqual({"field1": value}, form.initial)

    def test_validates_composite_form(self):
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        request = HttpRequest()
        request.user = factory.make_User()
        value1 = factory.make_string(5)
        value2 = factory.make_string(5)
        form = TestCompositeForm(
            {"maas_name": value1, "non_config_field": value2}
        )
        result = form.save(endpoint, request)

        self.assertTrue(result, form._errors)
        self.assertEqual(value1, Config.objects.get_config("maas_name"))
