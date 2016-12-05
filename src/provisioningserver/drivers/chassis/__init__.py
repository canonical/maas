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

from abc import (
    abstractmethod,
    abstractproperty,
)

import attr
from jsonschema import validate
from provisioningserver.drivers import (
    IP_EXTRACTOR_SCHEMA,
    SETTING_PARAMETER_FIELD_SCHEMA,
)
from provisioningserver.drivers.power import (
    PowerDriver,
    PowerDriverBase,
)
from provisioningserver.utils.registry import Registry

# JSON schema for what a chassis driver definition should look like.
JSON_CHASSIS_DRIVER_SCHEMA = {
    'title': "Chassis driver setting set",
    'type': 'object',
    'properties': {
        'name': {
            'type': 'string',
        },
        'description': {
            'type': 'string',
        },
        'fields': {
            'type': 'array',
            'items': SETTING_PARAMETER_FIELD_SCHEMA,
        },
        'ip_extractor': IP_EXTRACTOR_SCHEMA,
        'queryable': {
            'type': 'boolean',
        },
        'missing_packages': {
            'type': 'array',
            'items': {
                'type': 'string',
            },
        },
        'composable': {
            'type': 'boolean',
        },
    },
    'required': ['name', 'description', 'fields', 'composable'],
}

# JSON schema for multple chassis drivers.
JSON_CHASSIS_DRIVERS_SCHEMA = {
    'title': "Chassis drivers parameters set",
    'type': 'array',
    'items': JSON_CHASSIS_DRIVER_SCHEMA,
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


def convert_obj(expected):
    """Convert the given value to an object of type `expected`."""
    def convert(value):
        if isinstance(value, expected):
            return value
        elif isinstance(value, dict):
            return expected(**value)
        else:
            raise TypeError(
                "%r is not of type %s or dict" % (value, expected))
    return convert


def convert_list(expected):
    """Convert the given value to a list of objects of type `expected`."""
    def convert(value):
        if isinstance(value, list):
            if len(value) == 0:
                return value
            else:
                new_list = []
                for item in value:
                    if isinstance(item, expected):
                        new_list.append(item)
                    elif isinstance(item, dict):
                        new_list.append(expected(**item))
                    else:
                        raise TypeError(
                            "Item %r is not of type %s or dict" % (
                                item, expected))
                return new_list
        else:
            raise TypeError("%r is not of type list" % value)
    return convert


@attr.s
class DiscoveredMachineInterface:
    """Discovered machine interface."""
    mac_address = attr.ib(convert=str)
    vid = attr.ib(convert=int, default=-1)
    tags = attr.ib(convert=convert_list(str), default=[])


@attr.s
class DiscoveredMachineBlockDevice:
    """Discovered machine block device."""
    model = attr.ib(convert=str)
    serial = attr.ib(convert=str)
    size = attr.ib(convert=int)
    block_size = attr.ib(convert=int, default=512)
    tags = attr.ib(convert=convert_list(str), default=[])


@attr.s
class DiscoveredMachine:
    """Discovered machine."""
    cores = attr.ib(convert=int)
    cpu_speed = attr.ib(convert=int)
    memory = attr.ib(convert=int)
    interfaces = attr.ib(convert=convert_list(DiscoveredMachineInterface))
    block_devices = attr.ib(
        convert=convert_list(DiscoveredMachineBlockDevice))


@attr.s
class DiscoveredChassisHints:
    """Discovered chassis hints.

    Hints provide helpful information to a user trying to compose a machine.
    Limiting the maximum cores allow request on a per machine basis.
    """
    cores = attr.ib(convert=int)
    memory = attr.ib(convert=int)
    local_storage = attr.ib(convert=int)


@attr.s
class DiscoveredChassis:
    """Discovered chassis information."""

    cores = attr.ib(convert=int)
    cpu_speed = attr.ib(convert=int)
    memory = attr.ib(convert=int)
    local_storage = attr.ib(convert=int)
    hints = attr.ib(convert=convert_obj(DiscoveredChassisHints))
    machines = attr.ib(
        convert=convert_list(DiscoveredMachine), default=[])

    @classmethod
    def fromdict(cls, data):
        """Convert from a dictionary."""
        return cls(**data)

    def asdict(self):
        """Convert to a dictionary."""
        return attr.asdict(self)


class ChassisDriverBase(PowerDriverBase):
    """Base driver for a chassis driver."""

    @abstractproperty
    def composable(self):
        """Whether or not the chassis supports composition."""

    @abstractmethod
    def discover(self, system_id, context):
        """Discover the chassis resources.

        :param system_id: Chassis system_id.
        :param context: Chassis settings.
        :returns: `Deferred` returning `DiscoveredChassis`.
        :rtype: `twisted.internet.defer.Deferred`
        """

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

    def get_schema(self, detect_missing_packages=True):
        """Returns the JSON schema for the driver.

        Calculates the missing packages on each invoke.
        """
        schema = super(ChassisDriverBase, self).get_schema(
            detect_missing_packages=detect_missing_packages)
        schema['composable'] = self.composable
        return schema


def get_error_message(err):
    """Returns the proper error message based on error."""
    if isinstance(err, ChassisAuthError):
        return "Could not authenticate to chassis: %s" % err
    elif isinstance(err, ChassisConnError):
        return "Could not contact chassis: %s" % err
    elif isinstance(err, ChassisActionError):
        return "Failed to complete chassis action: %s" % err
    else:
        return "Failed talking to chassis: %s" % err


class ChassisDriver(PowerDriver, ChassisDriverBase):
    """Default chassis driver."""

    composable = False


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
