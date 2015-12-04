# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers`."""

__all__ = []

import random

from jsonschema import (
    validate,
    ValidationError,
)
from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import sentinel
from provisioningserver import drivers
from provisioningserver.drivers import (
    Architecture,
    ArchitectureRegistry,
    BootResourceRegistry,
    JSON_SETTING_SCHEMA,
    make_setting_field,
    SETTING_PARAMETER_FIELD_SCHEMA,
    validate_settings,
)
from provisioningserver.utils.testing import RegistryFixture
from testtools.matchers import ContainsAll


class TestMakeSettingField(MAASTestCase):

    def test_returns_valid_schema(self):
        setting = make_setting_field(
            factory.make_name('name'), factory.make_name('label'))
        #: doesn't raise ValidationError
        validate(setting, SETTING_PARAMETER_FIELD_SCHEMA)

    def test_returns_dict_with_required_fields(self):
        setting = make_setting_field(
            factory.make_name('name'), factory.make_name('label'))
        self.assertThat(
            setting,
            ContainsAll([
                'name', 'label', 'required',
                'field_type', 'choices', 'default']))

    def test_defaults_field_type_to_string(self):
        setting = make_setting_field(
            factory.make_name('name'), factory.make_name('label'))
        self.assertEqual('string', setting['field_type'])

    def test_defaults_choices_to_empty_list(self):
        setting = make_setting_field(
            factory.make_name('name'), factory.make_name('label'))
        self.assertEqual([], setting['choices'])

    def test_defaults_default_to_empty_string(self):
        setting = make_setting_field(
            factory.make_name('name'), factory.make_name('label'))
        self.assertEqual("", setting['default'])

    def test_validates_choices(self):
        choices = [('invalid')]
        self.assertRaises(
            ValidationError,
            make_setting_field, factory.make_name('name'),
            factory.make_name('label'), field_type='choice', choices=choices)

    def test_returns_dict_with_correct_values(self):
        name = factory.make_name('name')
        label = factory.make_name('label')
        field_type = random.choice(['string', 'mac_address', 'choice'])
        choices = [
            [factory.make_name('key'), factory.make_name('value')]
            for _ in range(3)
            ]
        default = factory.make_name('default')
        setting = make_setting_field(
            name, label, field_type=field_type,
            choices=choices, default=default, required=True)
        self.assertItemsEqual({
            'name': name,
            'label': label,
            'field_type': field_type,
            'choices': choices,
            'default': default,
            'required': True
            }, setting)


class TestValidateSettings(MAASTestCase):

    def test_calls_validate(self):
        mock_validate = self.patch(drivers, 'validate')
        validate_settings(sentinel.settings)
        self.assertThat(
            mock_validate,
            MockCalledOnceWith(sentinel.settings, JSON_SETTING_SCHEMA))


class TestRegistries(MAASTestCase):

    def setUp(self):
        super(TestRegistries, self).setUp()
        # Ensure the global registry is empty for each test run.
        self.useFixture(RegistryFixture())

    def test_bootresource_registry(self):
        self.assertItemsEqual([], BootResourceRegistry)
        BootResourceRegistry.register_item("resource", sentinel.resource)
        self.assertIn(
            sentinel.resource,
            (item for name, item in BootResourceRegistry))

    def test_architecture_registry(self):
        self.assertItemsEqual([], ArchitectureRegistry)
        ArchitectureRegistry.register_item("resource", sentinel.resource)
        self.assertIn(
            sentinel.resource,
            (item for name, item in ArchitectureRegistry))

    def test_get_by_pxealias_returns_valid_arch(self):
        arch1 = Architecture(
            name="arch1", description="arch1",
            pxealiases=["archibald", "reginald"])
        arch2 = Architecture(
            name="arch2", description="arch2",
            pxealiases=["fake", "foo"])
        ArchitectureRegistry.register_item("arch1", arch1)
        ArchitectureRegistry.register_item("arch2", arch2)
        self.assertEqual(
            arch1, ArchitectureRegistry.get_by_pxealias("archibald"))

    def test_get_by_pxealias_returns_None_if_none_matching(self):
        arch1 = Architecture(
            name="arch1", description="arch1",
            pxealiases=["archibald", "reginald"])
        arch2 = Architecture(name="arch2", description="arch2")
        ArchitectureRegistry.register_item("arch1", arch1)
        ArchitectureRegistry.register_item("arch2", arch2)
        self.assertEqual(
            None, ArchitectureRegistry.get_by_pxealias("stinkywinky"))

    def test_gen_power_types(self):

        from provisioningserver.drivers import power
        from provisioningserver.power import schema

        class TestGenPowerTypesPowerDriver(power.PowerDriver):
            name = 'test_gen_power_types'
            description = "test_gen_power_types Power Driver."
            settings = []

            def detect_missing_packages(self):
                # these packages are forever missing
                return ['fake-package-one', 'fake-package-two']

            def power_on(self, system_id, **kwargs):
                raise NotImplementedError

            def power_off(self, system_id, **kwargs):
                raise NotImplementedError

            def power_query(self, system_id, **kwargs):
                raise NotImplementedError

        # add my fake driver
        driver = TestGenPowerTypesPowerDriver()
        power.power_drivers_by_name[driver.name] = driver
        schema.JSON_POWER_TYPE_PARAMETERS += [{'name': "test_gen_power_types"}]

        # make sure fake packages are reported missing
        power_types = list(drivers.gen_power_types())
        self.assertEqual(15, len(power_types))
        self.assertItemsEqual(
            ['fake-package-one', 'fake-package-two'],
            power_types[-1].get('missing_packages'))
