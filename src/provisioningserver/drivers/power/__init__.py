# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Base power driver."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "get_power_address",
    "get_mandatory_setting",
    "PowerActionError",
    "PowerAuthError",
    "PowerConnError",
    "PowerDriver",
    "PowerDriverBase",
    "PowerError",
    "PowerFatalError",
    "PowerSettingError",
    "PowerToolError",
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


JSON_POWER_DRIVERS_SCHEMA = {
    'title': "Power drivers parameters set",
    'type': 'array',
    'items': JSON_SETTING_SCHEMA,
}


class PowerError(Exception):
    """Base error for all power driver failure commands."""


class PowerFatalError(PowerError):
    """Error that is raised when the power action should not continue to
    retry at all.

    This exception will cause the power action to fail instantly,
    without retrying.
    """


class PowerSettingError(PowerFatalError):
    """Error that is raised when the power type is missing argument
    that is required to control the BMC.

    This exception will cause the power action to fail instantly,
    without retrying.
    """


class PowerToolError(PowerFatalError):
    """Error that is raised when the power tool is missing completely
    for use.

    This exception will cause the power action to fail instantly,
    without retrying.
    """


class PowerAuthError(PowerError):
    """Error raised when power driver fails to authenticate to BMC."""


class PowerConnError(PowerError):
    """Error raised when power driver fails to communicate to BMC."""


class PowerActionError(PowerError):
    """Error when actually performing an action on the BMC, like `on`
    or `off`."""


class PowerDriverBase:
    """Base driver for a power driver."""

    __metaclass__ = ABCMeta

    def __init__(self):
        super(PowerDriverBase, self).__init__()
        validate_settings(self.get_schema())

    @abstractproperty
    def name(self):
        """Name of the power driver."""

    @abstractproperty
    def description(self):
        """Description of the power driver."""

    @abstractproperty
    def settings(self):
        """List of settings for the driver.

        Each setting in this list will be different per user. They are passed
        to the `on`, `off`, and `query` using the kwargs. It is up
        to the driver to read these options before performing the operation.
        """

    @abstractmethod
    def on(self, system_id, **kwargs):
        """Perform the power on action for `system_id`.

        :param system_id: `Node.system_id`
        :param kwargs: Power settings for the node.
        """

    @abstractmethod
    def off(self, system_id, **kwargs):
        """Perform the power off action for `system_id`.

        :param system_id: `Node.system_id`
        :param kwargs: Power settings for the node.
        """

    @abstractmethod
    def query(self, system_id, **kwargs):
        """Perform the query action for `system_id`.

        :param system_id: `Node.system_id`
        :param kwargs: Power settings for the node.
        :return: status of power on BMC. `on` or `off`.
        :raises PowerError: states unable to get status from BMC. It is
            up to this method to report the actual issue to the Region. The
            calling function should ignore this error, and continue on.
        """

    def get_schema(self):
        """Returns the JSON schema for the driver."""
        return dict(
            name=self.name, description=self.description,
            fields=self.settings)


def get_error_message(err):
    """Returns the proper error message based on error."""
    if isinstance(err, PowerAuthError):
        return "Could not authenticate to node's BMC: %s" % err
    elif isinstance(err, PowerConnError):
        return "Could not contact node's BMC: %s" % err
    elif isinstance(err, PowerSettingError):
        return "Missing or invalid power setting: %s" % err
    elif isinstance(err, PowerToolError):
        return "Missing power tool: %s" % err
    elif isinstance(err, PowerActionError):
        return "Failed to complete power action: %s" % err
    else:
        return "Failed talking to node's BMC for an unknown reason."


class PowerDriverRegistry(Registry):
    """Registry for power drivers."""

    @classmethod
    def get_schema(cls):
        """Returns the full schema for the registry."""
        schemas = [drivers.get_schema() for _, drivers in cls]
        validate(schemas, JSON_POWER_DRIVERS_SCHEMA)
        return schemas


builtin_power_drivers = [
    ]
for driver in builtin_power_drivers:
    PowerDriverRegistry.register_item(driver.name, driver)
