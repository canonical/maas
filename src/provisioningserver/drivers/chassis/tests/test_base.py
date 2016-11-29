# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.chassis`."""

__all__ = []

from unittest.mock import sentinel

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers import (
    make_setting_field,
    validate_settings,
)
from provisioningserver.drivers.chassis import (
    ChassisActionError,
    ChassisAuthError,
    ChassisConnError,
    ChassisDriver,
    ChassisDriverBase,
    ChassisDriverRegistry,
    ChassisError,
    get_error_message,
)
from provisioningserver.utils.testing import RegistryFixture


class FakeChassisDriverBase(ChassisDriverBase):

    name = ""
    description = ""
    settings = []

    def __init__(self, name, description, settings):
        self.name = name
        self.description = description
        self.settings = settings
        super(FakeChassisDriverBase, self).__init__()

    def discover(self, system_id, context):
        raise NotImplementedError

    def compose(self, system_id, context):
        raise NotImplementedError

    def decompose(self, system_id, context):
        raise NotImplementedError


def make_chassis_driver_base(name=None, description=None, settings=None):
    if name is None:
        name = factory.make_name('chassis')
    if description is None:
        description = factory.make_name('description')
    if settings is None:
        settings = []
    return FakeChassisDriverBase(name, description, settings)


class TestFakeChassisDriverBase(MAASTestCase):

    def test_attributes(self):
        fake_name = factory.make_name('name')
        fake_description = factory.make_name('description')
        fake_setting = factory.make_name('setting')
        fake_settings = [
            make_setting_field(
                fake_setting, fake_setting.title()),
            ]
        attributes = {
            'name': fake_name,
            'description': fake_description,
            'settings': fake_settings,
            }
        fake_driver = FakeChassisDriverBase(
            fake_name, fake_description, fake_settings)
        self.assertAttributes(fake_driver, attributes)

    def test_make_chassis_driver_base(self):
        fake_name = factory.make_name('name')
        fake_description = factory.make_name('description')
        fake_setting = factory.make_name('setting')
        fake_settings = [
            make_setting_field(
                fake_setting, fake_setting.title()),
            ]
        attributes = {
            'name': fake_name,
            'description': fake_description,
            'settings': fake_settings,
            }
        fake_driver = make_chassis_driver_base(
            name=fake_name, description=fake_description,
            settings=fake_settings)
        self.assertAttributes(fake_driver, attributes)

    def test_make_chassis_driver_base_makes_name_and_description(self):
        fake_driver = make_chassis_driver_base()
        self.assertNotEqual("", fake_driver.name)
        self.assertNotEqual("", fake_driver.description)

    def test_discover_raises_not_implemented(self):
        fake_driver = make_chassis_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.discover, sentinel.system_id, sentinel.context)

    def test_compose_raises_not_implemented(self):
        fake_driver = make_chassis_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.compose, sentinel.system_id, sentinel.context)

    def test_decompose_raises_not_implemented(self):
        fake_driver = make_chassis_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.decompose, sentinel.system_id, sentinel.context)


class TestChassisDriverBase(MAASTestCase):

    def test_get_schema(self):
        fake_name = factory.make_name('name')
        fake_description = factory.make_name('description')
        fake_setting = factory.make_name('setting')
        fake_settings = [
            make_setting_field(
                fake_setting, fake_setting.title()),
            ]
        fake_driver = make_chassis_driver_base()
        self.assertItemsEqual({
            'name': fake_name,
            'description': fake_description,
            'fields': fake_settings,
            },
            fake_driver.get_schema())

    def test_get_schema_returns_valid_schema(self):
        fake_driver = make_chassis_driver_base()
        #: doesn't raise ValidationError
        validate_settings(fake_driver.get_schema())


class TestChassisDriverRegistry(MAASTestCase):

    def setUp(self):
        super(TestChassisDriverRegistry, self).setUp()
        # Ensure the global registry is empty for each test run.
        self.useFixture(RegistryFixture())

    def test_registry(self):
        self.assertItemsEqual([], ChassisDriverRegistry)
        ChassisDriverRegistry.register_item("driver", sentinel.driver)
        self.assertIn(
            sentinel.driver,
            (item for name, item in ChassisDriverRegistry))

    def test_get_schema(self):
        fake_driver_one = make_chassis_driver_base()
        fake_driver_two = make_chassis_driver_base()
        ChassisDriverRegistry.register_item(
            fake_driver_one.name, fake_driver_one)
        ChassisDriverRegistry.register_item(
            fake_driver_two.name, fake_driver_two)
        self.assertItemsEqual([
            {
                'name': fake_driver_one.name,
                'description': fake_driver_one.description,
                'fields': [],
            },
            {
                'name': fake_driver_two.name,
                'description': fake_driver_two.description,
                'fields': [],
            }],
            ChassisDriverRegistry.get_schema())


class TestGetErrorMessage(MAASTestCase):

    scenarios = [
        ('auth', dict(
            exception=ChassisAuthError('auth'),
            message="Could not authenticate to node's chassis: auth",
            )),
        ('conn', dict(
            exception=ChassisConnError('conn'),
            message="Could not contact node's chassis: conn",
            )),
        ('action', dict(
            exception=ChassisActionError('action'),
            message="Failed to complete chassis action: action",
            )),
        ('unknown', dict(
            exception=ChassisError('unknown error'),
            message="Failed talking to node's chassis: unknown error",
            )),
    ]

    def test_return_msg(self):
        self.assertEqual(self.message, get_error_message(self.exception))


class FakeChassisDriver(ChassisDriver):

    name = ""
    description = ""
    settings = []

    def __init__(self, name, description, settings):
        self.name = name
        self.description = description
        self.settings = settings
        super(FakeChassisDriver, self).__init__()

    def detect_missing_packages(self):
        raise NotImplementedError

    def power_on(self, system_id, context):
        raise NotImplementedError

    def power_off(self, system_id, context):
        raise NotImplementedError

    def power_query(self, system_id, context):
        raise NotImplementedError


def make_chassis_driver(name=None, description=None, settings=None):
    if name is None:
        name = factory.make_name('diskless')
    if description is None:
        description = factory.make_name('description')
    if settings is None:
        settings = []
    return FakeChassisDriver(
        name, description, settings)
