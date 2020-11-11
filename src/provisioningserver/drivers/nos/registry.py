# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Load all NOS drivers."""


from jsonschema import validate

from provisioningserver.drivers.nos import JSON_NOS_DRIVERS_SCHEMA
from provisioningserver.drivers.nos.flexswitch import FlexswitchNOSDriver
from provisioningserver.utils.registry import Registry


class NOSDriverRegistry(Registry):
    """Registry for NOS drivers."""

    @classmethod
    def get_schema(cls):
        """Returns the full schema for the registry."""
        schemas = [driver.get_schema() for _, driver in cls]
        validate(schemas, JSON_NOS_DRIVERS_SCHEMA)
        return schemas


# Register all the NOS drivers.
nos_drivers = [FlexswitchNOSDriver()]
for driver in nos_drivers:
    NOSDriverRegistry.register_item(driver.name, driver)
