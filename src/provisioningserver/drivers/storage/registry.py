# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Load all storage drivers."""

__all__ = [
    "StorageDriverRegistry",
    ]

from jsonschema import validate
from provisioningserver.drivers.storage import JSON_STORAGE_DRIVERS_SCHEMA
from provisioningserver.utils.registry import Registry


class StorageDriverRegistry(Registry):
    """Registry for storage drivers."""

    @classmethod
    def get_schema(cls, detect_missing_packages=True):
        """Returns the full schema for the registry."""
        schemas = [
            driver.get_schema(detect_missing_packages=detect_missing_packages)
            for _, driver in cls
        ]
        validate(schemas, JSON_STORAGE_DRIVERS_SCHEMA)
        return schemas


storage_drivers = [
]
for driver in storage_drivers:
    StorageDriverRegistry.register_item(driver.name, driver)
