# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Base chassis driver."""

__all__ = [
    "ChassisActionError",
    "ChassisAuthError",
    "ChassisConnError",
    "ChassisDriver",
    "ChassisDriverBase",
    "ChassisError",
    "ChassisFatalError",
    ]

from abc import abstractmethod

from jsonschema import validate
from provisioningserver.drivers import JSON_SETTING_SCHEMA
from provisioningserver.drivers.power import (
    PowerDriver,
    PowerDriverBase,
)
from provisioningserver.utils.registry import Registry


JSON_CHASSIS_DRIVERS_SCHEMA = {
    'title': "Chassis drivers parameters set",
    'type': 'array',
    'items': JSON_SETTING_SCHEMA,
}


class ChassisError(Exception):
    """Base error for all chassis driver failure commands."""


class ChassisFatalError(ChassisError):
    """Error that is raised when the chassis action should not continue to
    retry at all.

    This exception will cause the chassis action to fail instantly,
    without retrying.
    """


class ChassisAuthError(ChassisFatalError):
    """Error raised when chassis driver fails to authenticate to the chassis.

    This exception will cause the chassis action to fail instantly,
    without retrying.
    """


class ChassisConnError(ChassisError):
    """Error raised when chassis driver fails to communicate to the chassis."""


class ChassisActionError(ChassisError):
    """Error when actually performing an action on the chassis, like `compose`
    or `discover`."""


class ChassisDriverBase(PowerDriverBase):
    """Base driver for a chassis driver."""

    @abstractmethod
    def discover(self, system_id, context):
        """Discover the chassis resources.

        :param system_id: Chassis system_id.
        :param context: Chassis settings.
        `"""

    @abstractmethod
    def compose(self, system_id, context):
        """Compose a node from parameters in context.

        :param system_id: Chassis system_id.
        :param context: Chassis settings.
        """

    @abstractmethod
    def decompose(self, system_id, context):
        """Decompose a node.

        :param system_id: Chassis system_id.
        :param context:  Chassis settings.
        """


def get_error_message(err):
    """Returns the proper error message based on error."""
    if isinstance(err, ChassisAuthError):
        return "Could not authenticate to node's chassis: %s" % err
    elif isinstance(err, ChassisConnError):
        return "Could not contact node's chassis: %s" % err
    elif isinstance(err, ChassisActionError):
        return "Failed to complete chassis action: %s" % err
    else:
        return "Failed talking to node's chassis: %s" % err


class ChassisDriver(PowerDriver, ChassisDriverBase):
    """Default chassis driver."""


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
]
for driver in chassis_drivers:
    ChassisDriverRegistry.register_item(driver.name, driver)
