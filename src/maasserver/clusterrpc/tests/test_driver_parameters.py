# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django import forms
import jsonschema

from maasserver.clusterrpc import driver_parameters
from maasserver.clusterrpc.driver_parameters import (
    add_nos_driver_parameters,
    add_power_driver_parameters,
    get_driver_parameters_from_json,
    get_driver_types,
    JSON_POWER_DRIVERS_SCHEMA,
    make_form_field,
    SETTING_PARAMETER_FIELD_SCHEMA,
)
from maasserver.config_forms import DictCharField
from maasserver.fields import MACAddressFormField
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.forms import compose_invalid_choice_text
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers import make_setting_field


class TestGetPowerTypeParametersFromJSON(MAASServerTestCase):
    """Test that get_power_type_parametrs_from_json."""

    def test_validates_json_power_type_parameters(self):
        invalid_parameters = [
            {"name": "invalid_power_type", "fields": "nothing to see here"}
        ]
        self.assertRaises(
            jsonschema.ValidationError,
            get_driver_parameters_from_json,
            invalid_parameters,
        )

    def test_includes_empty_power_type(self):
        json_parameters = [
            {
                "driver_type": "power",
                "name": "something",
                "description": "Meaningless",
                "fields": [
                    {
                        "name": "some_field",
                        "label": "Some Field",
                        "field_type": "string",
                        "required": False,
                    }
                ],
            }
        ]
        power_type_parameters = get_driver_parameters_from_json(
            json_parameters
        )
        self.assertEqual(["", "something"], list(power_type_parameters))

    def test_creates_dict_char_fields(self):
        json_parameters = [
            {
                "driver_type": "power",
                "name": "something",
                "description": "Meaningless",
                "fields": [
                    {
                        "name": "some_field",
                        "label": "Some Field",
                        "field_type": "string",
                        "required": False,
                    }
                ],
            }
        ]
        power_type_parameters = get_driver_parameters_from_json(
            json_parameters
        )
        for name, field in power_type_parameters.items():  # noqa: B007
            self.assertIsInstance(field, DictCharField)

    def test_overrides_defaults(self):
        name = factory.make_name("name")
        field_name = factory.make_name("field_name")
        new_default = factory.make_name("new default")
        json_parameters = [
            {
                "driver_type": "power",
                "name": name,
                "description": factory.make_name("description"),
                "fields": [
                    {
                        "name": field_name,
                        "label": factory.make_name("field label"),
                        "field_type": factory.make_name("field type"),
                        "default": factory.make_name("field default"),
                        "required": False,
                    }
                ],
            }
        ]
        power_type_parameters = get_driver_parameters_from_json(
            json_parameters, {field_name: new_default}
        )
        self.assertEqual(
            new_default, power_type_parameters[name].fields[0].initial
        )

    def test_manual_does_not_require_power_params(self):
        json_parameters = [
            {
                "driver_type": "power",
                "name": "manual",
                "description": factory.make_name("description"),
                "fields": [
                    {
                        "name": factory.make_name("field name"),
                        "label": factory.make_name("field label"),
                        "field_type": factory.make_name("field type"),
                        "default": factory.make_name("field default"),
                        "required": False,
                    }
                ],
            }
        ]
        power_type_parameters = get_driver_parameters_from_json(
            json_parameters
        )
        self.assertFalse(power_type_parameters["manual"].required)

    def test_parameter_with_multiple_choice(self):
        json_parameters = [
            {
                "driver_type": "power",
                "name": "ipmi",
                "description": factory.make_name("description"),
                "fields": [
                    {
                        "name": factory.make_name("field name"),
                        "label": factory.make_name("field label"),
                        "field_type": "multiple_choice",
                        "choices": [
                            [factory.make_name("choice1"), "choice1"],
                            [factory.make_name("choice2"), "choice2"],
                        ],
                        "default": [factory.make_name("field default")],
                        "required": False,
                    }
                ],
            }
        ]
        power_type_parameters = get_driver_parameters_from_json(
            json_parameters
        )
        self.assertTrue(power_type_parameters["ipmi"])


class TestMakeFormField(MAASServerTestCase):
    """Test that make_form_field() converts JSON fields to Django."""

    def test_creates_char_field_for_strings(self):
        json_field = {
            "name": "some_field",
            "label": "Some Field",
            "field_type": "string",
            "required": False,
        }
        django_field = make_form_field(json_field)
        self.assertIsInstance(django_field, forms.CharField)

    def test_creates_string_field_for_passwords(self):
        json_field = {
            "name": "some_field",
            "label": "Some Field",
            "field_type": "password",
            "required": False,
        }
        django_field = make_form_field(json_field)
        self.assertIsInstance(django_field, forms.CharField)

    def test_creates_choice_field_for_choices(self):
        json_field = {
            "name": "some_field",
            "label": "Some Field",
            "field_type": "choice",
            "choices": [
                ["choice-one", "Choice One"],
                ["choice-two", "Choice Two"],
            ],
            "default": "choice-one",
            "required": False,
        }
        django_field = make_form_field(json_field)
        self.assertIsInstance(django_field, forms.ChoiceField)
        self.assertEqual(json_field["choices"], django_field.choices)
        invalid_msg = compose_invalid_choice_text(
            json_field["name"], json_field["choices"]
        )
        self.assertEqual(
            invalid_msg, django_field.error_messages["invalid_choice"]
        )
        self.assertEqual(json_field["default"], django_field.initial)

    def test_creates_mac_address_field_for_mac_addresses(self):
        json_field = {
            "name": "some_field",
            "label": "Some Field",
            "field_type": "mac_address",
            "required": False,
        }
        django_field = make_form_field(json_field)
        self.assertIsInstance(django_field, MACAddressFormField)

    def test_creates_multiple_choice_field_for_multiple_choice(self):
        json_field = {
            "name": "some_field",
            "label": "Some Field",
            "field_type": "multiple_choice",
            "choices": [["choice_1", "choice_2"]],
            "required": False,
        }
        django_field = make_form_field(json_field)
        self.assertIsInstance(django_field, forms.MultipleChoiceField)

    def test_sets_properties_on_form_field(self):
        json_field = {
            "name": "some_field",
            "label": "Some Field",
            "field_type": "string",
            "required": False,
        }
        django_field = make_form_field(json_field)
        self.assertEqual(
            (json_field["label"], json_field["required"]),
            (django_field.label, django_field.required),
        )

    def test_sets_default_not_required(self):
        json_field = {
            "name": "some_field",
            "label": "Some Field",
            "field_type": "string",
            "required": False,
            "default": "some default",
        }
        django_field = make_form_field(json_field)
        self.assertEqual("some default", django_field.initial)
        self.assertEqual("", django_field.empty_value)

    def test_sets_default_and_empty_value_required(self):
        json_field = {
            "name": "some_field",
            "label": "Some Field",
            "field_type": "string",
            "required": True,
            "default": "some default",
        }
        django_field = make_form_field(json_field)
        self.assertEqual("some default", django_field.initial)
        self.assertEqual("some default", django_field.empty_value)


class TestMakeSettingField(MAASServerTestCase):
    """Test that make_setting_field() creates JSON-verifiable fields."""

    def test_returns_json_verifiable_dict(self):
        json_field = make_setting_field("some_field", "Some Label")
        jsonschema.validate(json_field, SETTING_PARAMETER_FIELD_SCHEMA)

    def test_provides_sane_default_values(self):
        json_field = make_setting_field("some_field", "Some Label")
        expected_field = {
            "name": "some_field",
            "label": "Some Label",
            "required": False,
            "field_type": "string",
            "choices": [],
            "default": "",
            "scope": "bmc",
            "secret": False,
        }
        self.assertEqual(expected_field, json_field)

    def test_sets_field_values(self):
        expected_field = {
            "name": "yet_another_field",
            "label": "Can I stop writing tests now?",
            "required": True,
            "field_type": "string",
            "choices": [["spam", "Spam"], ["eggs", "Eggs"]],
            "default": "spam",
            "scope": "bmc",
            "secret": False,
        }
        json_field = make_setting_field(**expected_field)
        self.assertEqual(expected_field, json_field)

    def test_validates_choices(self):
        self.assertRaises(
            jsonschema.ValidationError,
            make_setting_field,
            "some_field",
            "Some Label",
            choices="Nonsense",
        )

    def test_creates_password_fields(self):
        json_field = make_setting_field(
            "some_field", "Some Label", field_type="password", secret=True
        )
        expected_field = {
            "name": "some_field",
            "label": "Some Label",
            "required": False,
            "field_type": "password",
            "choices": [],
            "default": "",
            "scope": "bmc",
            "secret": True,
        }
        self.assertEqual(expected_field, json_field)


class TestAddPowerTypeParameters(MAASServerTestCase):
    def make_field(self):
        return make_setting_field(
            self.getUniqueString(), self.getUniqueString()
        )

    def make_multiple_choice_field(self):
        choices = [
            [factory.make_name("choice1"), "choice1"],
            [factory.make_name("choice2"), "choice2"],
        ]
        return make_setting_field(
            self.getUniqueString(),
            self.getUniqueString(),
            field_type="multiple_choice",
            choices=choices,
            default=[choices[0][0]],
        )

    def test_adding_existing_types_is_a_no_op(self):
        existing_parameters = [
            {
                "driver_type": "power",
                "name": "blah",
                "description": "baz",
                "chassis": True,
                "fields": {},
            }
        ]
        add_power_driver_parameters(
            driver_type="power",
            name="blah",
            description="baz",
            chassis=True,
            can_probe=False,
            fields=[self.make_field()],
            missing_packages=[],
            parameters_set=existing_parameters,
        )
        self.assertEqual(
            [
                {
                    "driver_type": "power",
                    "name": "blah",
                    "description": "baz",
                    "chassis": True,
                    "fields": {},
                }
            ],
            existing_parameters,
        )

    def test_adds_new_power_type_parameters(self):
        existing_parameters = []
        fields = [self.make_field()]
        missing_packages = ["package1", "package2"]
        add_power_driver_parameters(
            driver_type="power",
            name="blah",
            description="baz",
            chassis=False,
            can_probe=False,
            fields=fields,
            missing_packages=missing_packages,
            parameters_set=existing_parameters,
        )
        self.assertEqual(
            [
                {
                    "driver_type": "power",
                    "name": "blah",
                    "description": "baz",
                    "chassis": False,
                    "can_probe": False,
                    "fields": fields,
                    "missing_packages": missing_packages,
                }
            ],
            existing_parameters,
        )

    def test_validates_new_parameters(self):
        self.assertRaises(
            jsonschema.ValidationError,
            add_power_driver_parameters,
            driver_type="power",
            name="blah",
            description="baz",
            chassis=False,
            can_probe=False,
            fields=[{}],
            missing_packages=[],
            parameters_set=[],
        )

    def test_subsequent_parameters_set_is_valid(self):
        parameters_set = []
        fields = [self.make_field()]
        add_power_driver_parameters(
            driver_type="power",
            name="blah",
            description="baz",
            chassis=False,
            can_probe=False,
            fields=fields,
            missing_packages=[],
            parameters_set=parameters_set,
        )
        jsonschema.validate(parameters_set, JSON_POWER_DRIVERS_SCHEMA)

    def test_multiple_choice_power_parameters_are_valid(self):
        parameters_set = []
        fields = [self.make_field(), self.make_multiple_choice_field()]
        add_power_driver_parameters(
            driver_type="power",
            name=factory.make_name("name"),
            description=factory.make_name("description"),
            chassis=False,
            can_probe=False,
            fields=fields,
            missing_packages=[],
            parameters_set=parameters_set,
        )
        jsonschema.validate(parameters_set, JSON_POWER_DRIVERS_SCHEMA)


class TestAddNOSTypeParameters(MAASServerTestCase):
    def make_field(self):
        return make_setting_field(
            self.getUniqueString(), self.getUniqueString()
        )

    def test_adding_existing_types_is_a_no_op(self):
        existing_parameters = [
            {
                "driver_type": "nos",
                "name": "blah",
                "description": "baz",
                "fields": {},
            }
        ]
        add_nos_driver_parameters(
            driver_type="nos",
            name="blah",
            description="baz",
            fields=[self.make_field()],
            parameters_set=existing_parameters,
        )
        self.assertEqual(
            [
                {
                    "driver_type": "nos",
                    "name": "blah",
                    "description": "baz",
                    "fields": {},
                }
            ],
            existing_parameters,
        )

    def test_adds_new_nos_type_parameters(self):
        existing_parameters = []
        fields = [self.make_field()]
        add_nos_driver_parameters(
            driver_type="nos",
            name="blah",
            description="baz",
            fields=fields,
            parameters_set=existing_parameters,
        )
        self.assertEqual(
            [
                {
                    "driver_type": "nos",
                    "name": "blah",
                    "description": "baz",
                    "fields": fields,
                }
            ],
            existing_parameters,
        )

    def test_validates_new_parameters(self):
        self.assertRaises(
            jsonschema.ValidationError,
            add_nos_driver_parameters,
            driver_type="nos",
            name="blah",
            description="baz",
            fields=[{}],
            parameters_set=[],
        )

    def test_validates_driver_type(self):
        self.assertRaises(
            AssertionError,
            add_nos_driver_parameters,
            driver_type="power",
            name="blah",
            description="baz",
            fields=[],
            parameters_set=[],
        )


class TestPowerTypes(MAASTestCase):
    # This is deliberately not using a MAASServerTestCase as that
    # patches the get_all_power_types() function with data
    # that's hidden from tests in here.  Instead the tests patch
    # explicitly here.

    def test_get_power_driver_types_transforms_data_to_dict(self):
        mocked = self.patch(driver_parameters, "get_all_power_types")
        mocked.return_value = [
            {
                "driver_type": "power",
                "name": "namevalue",
                "description": "descvalue",
            },
            {
                "driver_type": "power",
                "name": "namevalue2",
                "description": "descvalue2",
            },
        ]
        expected = {"namevalue": "descvalue", "namevalue2": "descvalue2"}
        self.assertEqual(expected, get_driver_types())
