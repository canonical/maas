# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Base diskless driver."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DisklessDriver",
    "DisklessDriverError",
    "DisklessDriverRegistry",
    ]

from abc import (
    ABCMeta,
    abstractmethod,
    abstractproperty,
    )

from jsonschema import validate
from provisioningserver.drivers import (
    JSON_SETTING_SCHEMA,
    validate_settings,
    )
from provisioningserver.utils.registry import Registry


JSON_DISKLESS_DRIVERS_SCHEMA = {
    'title': "Diskless drivers parameters set",
    'type': 'array',
    'items': JSON_SETTING_SCHEMA,
}


class DisklessDriverError:
    """Error when driver fails to complete the needed task."""


class DisklessDriver:
    """Skeleton for a diskless driver."""

    __metaclass__ = ABCMeta

    def __init__(self):
        super(DisklessDriver, self).__init__()
        validate_settings(self.get_schema())

    @abstractproperty
    def name(self):
        """Name of the diskless driver."""

    @abstractproperty
    def description(self):
        """Description of the diskless driver."""

    @abstractproperty
    def settings(self):
        """List of settings for the driver.

        Each setting in this list can be changed by the user. They are passed
        to the `create_disk` and `delete_disk` using the kwargs. It is up
        to the driver to read these options before performing the operation.
        """

    @abstractmethod
    def create_disk(self, system_id, source_path, **kwargs):
        """Creates the disk for the `system_id` using the `source_path` as
        the data to place on the disk initially.

        :param system_id: `Node.system_id`
        :param source_path: Path to the source data
        :param kwargs: Settings user set from `get_settings`.
        :returns: Path to the newly created disk.
        """

    @abstractmethod
    def delete_disk(self, system_id, disk_path, **kwargs):
        """Deletes the disk for the `system_id`.

        :param system_id: `Node.system_id`
        :param disk_path: Path returned by `create_disk`.
        :param kwargs: Settings user set from `get_settings`.
        """

    def get_schema(self):
        """Returns the JSON schema for the driver."""
        return dict(
            name=self.name, description=self.description,
            fields=self.settings)


class DisklessDriverRegistry(Registry):
    """Registry for diskless drivers."""

    @classmethod
    def get_schema(cls):
        """Returns the full schema for the registry."""
        schemas = [drivers.get_schema() for _, drivers in cls]
        validate(schemas, JSON_DISKLESS_DRIVERS_SCHEMA)
        return schemas


builtin_diskless_drivers = [
    ]
for driver in builtin_diskless_drivers:
    DisklessDriverRegistry.register_item(driver.name, driver)
