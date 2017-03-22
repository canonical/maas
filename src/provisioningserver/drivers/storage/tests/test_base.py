# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.storage`."""

__all__ = []

import random
from unittest.mock import sentinel

from jsonschema import validate
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers import (
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.pod.tests.test_base import (
    make_pod_driver_base,
)
from provisioningserver.drivers.storage import (
    DiscoveredStorage,
    DiscoveredVolume,
    get_error_message,
    JSON_STORAGE_DRIVER_SCHEMA,
    RequestedVolume,
    StorageActionError,
    StorageAuthError,
    StorageConnError,
    StorageDriver,
    StorageError,
)
from testtools.matchers import (
    Equals,
    IsInstance,
    MatchesAll,
    MatchesDict,
    MatchesListwise,
    MatchesStructure,
)


class TestDiscoveredClasses(MAASTestCase):

    def test_volume_size(self):
        size = random.randint(512, 512 * 1024)
        volume = DiscoveredVolume(size=size)
        self.assertEquals(size, volume.size)
        self.assertEquals(512, volume.block_size)
        self.assertEquals([], volume.tags)

    def test_volume_size_block_size_tags(self):
        size = random.randint(512, 512 * 1024)
        block_size = random.randint(512, 4096)
        tags = [
            factory.make_name("tag")
            for _ in range(3)
        ]
        volume = DiscoveredVolume(
            size=size, block_size=block_size, tags=tags)
        self.assertEquals(size, volume.size)
        self.assertEquals(block_size, volume.block_size)
        self.assertEquals(tags, volume.tags)

    def test_machine(self):
        size = random.randint(1024 ** 3, (1024 ** 3) * 5)
        volumes = [
            DiscoveredVolume(
                size=random.randint(512, 1024))
            for _ in range(3)
        ]
        params = {
            factory.make_name('key'): factory.make_name('volume')
            for _ in range(3)
        }
        driver_type = factory.make_name('storage')
        storage = DiscoveredStorage(
            size=size,
            volumes=volumes,
            parameters=params,
            driver_type=driver_type)
        self.assertEquals(size, storage.size)
        self.assertEquals(volumes, storage.volumes)
        self.assertEquals(params, storage.parameters)
        self.assertEquals(driver_type, storage.driver_type)

    def test_storage_asdict(self):
        size = random.randint(1024 ** 3, (1024 ** 3) * 5)
        volumes = [
            DiscoveredVolume(
                size=random.randint(512, 1024))
            for _ in range(3)
        ]
        params = {
            factory.make_name('key'): factory.make_name('volume')
            for _ in range(3)
        }
        driver_type = factory.make_name('storage')
        storage = DiscoveredStorage(
            size=size,
            volumes=volumes,
            parameters=params,
            driver_type=driver_type)
        self.assertThat(storage.asdict(), MatchesDict({
            "size": Equals(size),
            "driver_type": Equals(driver_type),
            "parameters": MatchesDict({
                key: Equals(value)
                for key, value in params.items()
            }),
            "volumes": MatchesListwise([
                MatchesDict({
                    "size": Equals(volume.size),
                    "block_size": Equals(512),
                    "tags": Equals([]),
                })
                for volume in volumes
            ]),
        }))

    def test_storage_fromdict(self):
        size = random.randint(1024 ** 3, (1024 ** 3) * 5)
        volumes = [
            dict(
                size=random.randint(512, 1024))
            for _ in range(3)
        ]
        params = {
            factory.make_name('key'): factory.make_name('volume')
            for _ in range(3)
        }
        driver_type = factory.make_name('storage')
        storage_data = dict(
            size=size, volumes=volumes, parameters=params,
            driver_type=driver_type)
        storage = DiscoveredStorage.fromdict(storage_data)
        self.assertThat(storage, IsInstance(DiscoveredStorage))
        self.assertThat(storage, MatchesStructure(
            size=Equals(size),
            driver_type=Equals(driver_type),
            parameters=MatchesDict({
                key: Equals(value)
                for key, value in params.items()
            }),
            volumes=MatchesListwise([
                MatchesAll(
                    IsInstance(DiscoveredVolume),
                    MatchesStructure(
                        size=Equals(volume['size']),
                        block_size=Equals(512),
                        tags=Equals([]),
                    )
                )
                for volume in volumes
            ])
        ))


class TestRequestClasses(MAASTestCase):

    def test_volume(self):
        size = random.randint(512, 512 * 1024)
        volume = RequestedVolume(size=size)
        self.assertEquals(size, volume.size)

    def test_volume_asdict(self):
        size = random.randint(512, 512 * 1024)
        volume = RequestedVolume(size=size)
        self.assertEquals({
            'size': size,
        }, volume.asdict())

    def test_volume_fromdict(self):
        size = random.randint(512, 512 * 1024)
        volume_data = {
            'size': size,
        }
        volume = RequestedVolume.fromdict(volume_data)
        self.assertIsInstance(volume, RequestedVolume)
        self.assertEquals(size, volume.size)


class FakeStorageDriver(StorageDriver):

    name = ""
    description = ""
    settings = []
    ip_extractor = None

    def __init__(self, name, description, settings):
        self.name = name
        self.description = description
        self.settings = settings
        super(FakeStorageDriver, self).__init__()

    def discover(self, context, storage_id=None):
        raise NotImplementedError

    def create_volume(self, storage_id, context, request):
        raise NotImplementedError

    def delete_volume(self, storage_id, context, request):
        raise NotImplementedError

    def detect_missing_packages(self):
        return []


def make_storage_driver(name=None, description=None, settings=None):
    if name is None:
        name = factory.make_name('storage')
    if description is None:
        description = factory.make_name('description')
    if settings is None:
        settings = []
    return FakeStorageDriver(name, description, settings)


class TestFakeStorageDriver(MAASTestCase):

    def test__init__fails_when_setting_in_wrong_scope(self):
        fake_name = factory.make_name('name')
        fake_description = factory.make_name('description')
        fake_setting = factory.make_name('setting')
        fake_settings = [
            make_setting_field(
                fake_setting, fake_setting.title()),
            ]
        self.assertRaises(
            ValueError, FakeStorageDriver,
            fake_name, fake_description, fake_settings)

    def test_attributes(self):
        fake_name = factory.make_name('name')
        fake_description = factory.make_name('description')
        fake_setting = factory.make_name('setting')
        fake_settings = [
            make_setting_field(
                fake_setting, fake_setting.title(),
                scope=SETTING_SCOPE.STORAGE),
            ]
        attributes = {
            'name': fake_name,
            'description': fake_description,
            'settings': fake_settings,
            }
        fake_driver = FakeStorageDriver(
            fake_name, fake_description, fake_settings)
        self.assertAttributes(fake_driver, attributes)

    def test_make_storage_driver(self):
        fake_name = factory.make_name('name')
        fake_description = factory.make_name('description')
        fake_setting = factory.make_name('setting')
        fake_settings = [
            make_setting_field(
                fake_setting, fake_setting.title(),
                scope=SETTING_SCOPE.STORAGE),
            ]
        attributes = {
            'name': fake_name,
            'description': fake_description,
            'settings': fake_settings,
            }
        fake_driver = make_storage_driver(
            name=fake_name, description=fake_description,
            settings=fake_settings)
        self.assertAttributes(fake_driver, attributes)

    def test_make_storage_driver_makes_name_and_description(self):
        fake_driver = make_storage_driver()
        self.assertNotEqual("", fake_driver.name)
        self.assertNotEqual("", fake_driver.description)

    def test_discover_raises_not_implemented(self):
        fake_driver = make_storage_driver()
        self.assertRaises(
            NotImplementedError,
            fake_driver.discover, sentinel.context,
            storage_id=sentinel.storage_id)

    def test_create_volume_raises_not_implemented(self):
        fake_driver = make_storage_driver()
        self.assertRaises(
            NotImplementedError,
            fake_driver.create_volume,
            sentinel.storage_id, sentinel.context, sentinel.request)

    def test_delete_volume_raises_not_implemented(self):
        fake_driver = make_storage_driver()
        self.assertRaises(
            NotImplementedError,
            fake_driver.delete_volume,
            sentinel.storage_id, sentinel.context, sentinel.request)

    def test_get_schema(self):
        fake_name = factory.make_name('name')
        fake_description = factory.make_name('description')
        fake_setting = factory.make_name('setting')
        fake_settings = [
            make_setting_field(
                fake_setting, fake_setting.title(),
                scope=SETTING_SCOPE.STORAGE),
            ]
        fake_driver = make_storage_driver(
            fake_name, fake_description, fake_settings)
        fake_pod_driver = make_pod_driver_base()
        fake_driver.pod_driver = fake_pod_driver
        self.assertEquals({
            'name': fake_name,
            'description': fake_description,
            'fields': fake_settings,
            'missing_packages': [],
            'pod_driver': fake_pod_driver.name,
            },
            fake_driver.get_schema())

    def test_get_schema_returns_valid_schema(self):
        fake_driver = make_storage_driver()
        #: doesn't raise ValidationError
        validate(fake_driver.get_schema(), JSON_STORAGE_DRIVER_SCHEMA)


class TestGetErrorMessage(MAASTestCase):

    scenarios = [
        ('auth', dict(
            exception=StorageAuthError('auth'),
            message="Could not authenticate to storage system: auth",
            )),
        ('conn', dict(
            exception=StorageConnError('conn'),
            message="Could not contact storage system: conn",
            )),
        ('action', dict(
            exception=StorageActionError('action'),
            message="Failed to complete storage action: action",
            )),
        ('unknown', dict(
            exception=StorageError('unknown error'),
            message="Failed talking to storage system: unknown error",
            )),
    ]

    def test_return_msg(self):
        self.assertEqual(self.message, get_error_message(self.exception))
