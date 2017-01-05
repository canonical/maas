# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Load all chassis drivers."""

__all__ = [
    "ChassisDriverRegistry",
    ]

from jsonschema import validate
from provisioningserver.drivers.chassis import JSON_CHASSIS_DRIVERS_SCHEMA
from provisioningserver.drivers.chassis.null import NullChassisDriver
from provisioningserver.utils.registry import Registry


class ChassisDriverRegistry(Registry):
    """Registry for chassis drivers."""

    @classmethod
    def get_schema(cls, detect_missing_packages=True):
        """Returns the full schema for the registry."""
        schemas = [
            driver.get_schema(detect_missing_packages=detect_missing_packages)
            for _, driver in cls
        ]
        validate(schemas, JSON_CHASSIS_DRIVERS_SCHEMA)
        return schemas


chassis_drivers = [
    NullChassisDriver()
]
for driver in chassis_drivers:
    ChassisDriverRegistry.register_item(driver.name, driver)
