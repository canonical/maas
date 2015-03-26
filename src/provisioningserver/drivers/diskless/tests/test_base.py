# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.diskless`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from mock import sentinel
from provisioningserver.drivers import (
    make_setting_field,
    validate_settings,
)
from provisioningserver.drivers.diskless import (
    DisklessDriver,
    DisklessDriverRegistry,
)
from provisioningserver.utils.testing import RegistryFixture


class FakeDisklessDriver(DisklessDriver):

    name = ""
    description = ""
    settings = []

    def __init__(self, name, description, settings):
        self.name = name
        self.description = description
        self.settings = settings
        super(FakeDisklessDriver, self).__init__()

    def create_disk(self, system_id, source_path, **kwargs):
        raise NotImplementedError()

    def delete_disk(self, system_id, disk_path, **kwargs):
        raise NotImplementedError()


def make_diskless_driver(name=None, description=None, settings=None):
    if name is None:
        name = factory.make_name('diskless')
    if description is None:
        description = factory.make_name('description')
    if settings is None:
        settings = []
    return FakeDisklessDriver(name, description, settings)


class TestFakeDisklessDriver(MAASTestCase):

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
        fake_driver = FakeDisklessDriver(
            fake_name, fake_description, fake_settings)
        self.assertAttributes(fake_driver, attributes)

    def test_make_diskless_driver(self):
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
        fake_driver = make_diskless_driver(
            name=fake_name, description=fake_description,
            settings=fake_settings)
        self.assertAttributes(fake_driver, attributes)

    def test_make_diskless_driver_makes_name_and_description(self):
        fake_driver = make_diskless_driver()
        self.assertNotEqual("", fake_driver.name)
        self.assertNotEqual("", fake_driver.description)

    def test_create_disk_raises_not_implemented(self):
        fake_driver = make_diskless_driver()
        self.assertRaises(
            NotImplementedError,
            fake_driver.create_disk, sentinel.system_id, sentinel.source_path)

    def test_delete_disk_raises_not_implemented(self):
        fake_driver = make_diskless_driver()
        self.assertRaises(
            NotImplementedError,
            fake_driver.delete_disk, sentinel.system_id, sentinel.disk_path)


class TestDisklessDriver(MAASTestCase):

    def test_get_schema(self):
        fake_name = factory.make_name('name')
        fake_description = factory.make_name('description')
        fake_setting = factory.make_name('setting')
        fake_settings = [
            make_setting_field(
                fake_setting, fake_setting.title()),
            ]
        fake_driver = make_diskless_driver()
        self.assertItemsEqual({
            'name': fake_name,
            'description': fake_description,
            'fields': fake_settings,
            },
            fake_driver.get_schema())

    def test_get_schema_returns_valid_schema(self):
        fake_driver = make_diskless_driver()
        #: doesn't raise ValidationError
        validate_settings(fake_driver.get_schema())


class TestDisklessDriverRegistry(MAASTestCase):

    def setUp(self):
        super(TestDisklessDriverRegistry, self).setUp()
        # Ensure the global registry is empty for each test run.
        self.useFixture(RegistryFixture())

    def test_registry(self):
        self.assertItemsEqual([], DisklessDriverRegistry)
        DisklessDriverRegistry.register_item("driver", sentinel.driver)
        self.assertIn(
            sentinel.driver,
            (item for name, item in DisklessDriverRegistry))

    def test_get_schema(self):
        fake_driver_one = make_diskless_driver()
        fake_driver_two = make_diskless_driver()
        DisklessDriverRegistry.register_item(
            fake_driver_one.name, fake_driver_one)
        DisklessDriverRegistry.register_item(
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
            DisklessDriverRegistry.get_schema())
