# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.nos`."""


from unittest.mock import sentinel

from jsonschema import validate
from twisted.internet import reactor

from maastesting.factory import factory
from maastesting.runtest import MAASTwistedRunTest
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers import make_setting_field
from provisioningserver.drivers.nos import (
    JSON_NOS_DRIVER_SCHEMA,
    NOSDriver,
    NOSDriverBase,
)


class FakeNOSDriverBase(NOSDriverBase):

    name = ""
    description = ""
    settings = []
    deployable = False

    def __init__(self, name, description, settings):
        self.name = name
        self.description = description
        self.settings = settings
        super().__init__()

    def is_switch_supported(self, vendor, model):
        raise NotImplementedError()


def make_nos_driver_base(name=None, description=None, settings=None):
    if name is None:
        name = factory.make_name("cardless")
    if description is None:
        description = factory.make_name("description")
    if settings is None:
        settings = []
    return FakeNOSDriverBase(name, description, settings)


class TestFakeNOSDriverBase(MAASTestCase):
    def test_attributes(self):
        fake_name = factory.make_name("name")
        fake_description = factory.make_name("description")
        fake_setting = factory.make_name("setting")
        fake_settings = [
            make_setting_field(fake_setting, fake_setting.title())
        ]
        attributes = {
            "name": fake_name,
            "description": fake_description,
            "settings": fake_settings,
        }
        fake_driver = FakeNOSDriverBase(
            fake_name, fake_description, fake_settings
        )
        self.assertAttributes(fake_driver, attributes)

    def test_make_nos_driver_base(self):
        fake_name = factory.make_name("name")
        fake_description = factory.make_name("description")
        fake_setting = factory.make_name("setting")
        fake_settings = [
            make_setting_field(fake_setting, fake_setting.title())
        ]
        attributes = {
            "name": fake_name,
            "description": fake_description,
            "settings": fake_settings,
        }
        fake_driver = make_nos_driver_base(
            name=fake_name,
            description=fake_description,
            settings=fake_settings,
        )
        self.assertAttributes(fake_driver, attributes)

    def test_make_nos_driver_base_makes_name_and_description(self):
        fake_driver = make_nos_driver_base()
        self.assertNotEqual("", fake_driver.name)
        self.assertNotEqual("", fake_driver.description)

    def test_is_switch_supported_raises_not_implemented(self):
        fake_driver = make_nos_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.is_switch_supported,
            sentinel.vendor,
            sentinel.model,
        )


class TestNOSDriverBase(MAASTestCase):
    def test_get_schema(self):
        fake_name = factory.make_name("name")
        fake_description = factory.make_name("description")
        fake_setting = factory.make_name("setting")
        fake_settings = [
            make_setting_field(fake_setting, fake_setting.title())
        ]
        fake_driver = make_nos_driver_base(
            name=fake_name,
            description=fake_description,
            settings=fake_settings,
        )
        self.assertEqual(
            {
                "driver_type": "nos",
                "name": fake_name,
                "description": fake_description,
                "fields": fake_settings,
                "deployable": fake_driver.deployable,
            },
            fake_driver.get_schema(),
        )

    def test_get_schema_returns_valid_schema(self):
        fake_driver = make_nos_driver_base()
        #: doesn't raise ValidationError
        validate(fake_driver.get_schema(), JSON_NOS_DRIVER_SCHEMA)


class FakeNOSDriver(NOSDriver):

    name = ""
    description = ""
    settings = []
    deployable = True

    def __init__(self, name, description, settings, clock=reactor):
        self.name = name
        self.description = description
        self.settings = settings
        super().__init__(clock)

    def is_switch_supported(self, vendor, model):
        if vendor == "Canonical" and model == "BigSwitch":
            return True
        return False


def make_nos_driver(name=None, description=None, settings=None, clock=reactor):
    if name is None:
        name = factory.make_name("networkless")
    if description is None:
        description = factory.make_name("description")
    if settings is None:
        settings = []
    return FakeNOSDriver(name, description, settings, clock=clock)


class TestNOSDriver(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_is_switch_supported_yes(self):
        driver = make_nos_driver()
        self.assertTrue(driver.is_switch_supported("Canonical", "BigSwitch"))

    def test_is_switch_supported_nos(self):
        driver = make_nos_driver()
        self.assertFalse(driver.is_switch_supported("Foo", "SomeSwitch"))
