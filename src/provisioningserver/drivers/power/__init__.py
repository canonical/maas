# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
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
from provisioningserver.utils import pause
from provisioningserver.utils.registry import Registry
from twisted.internet import reactor
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
)
from twisted.internet.threads import deferToThread


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


class PowerDriver(PowerDriverBase):
    """Default power driver logic."""

    # Checks 4 times, in a minute
    wait_time = (5, 10, 20, 25)

    def __init__(self, clock=reactor):
        self.clock = reactor

    @abstractmethod
    def power_on(self, system_id, **kwargs):
        """Implement this method for the actual implementation
        of the power on command.
        """

    @abstractmethod
    def power_off(self, system_id, **kwargs):
        """Implement this method for the actual implementation
        of the power off command.
        """

    @abstractmethod
    def power_query(self, system_id, **kwargs):
        """Implement this method for the actual implementation
        of the power query command."""

    def find_error(self, system_id, **kwargs):
        """Performs checks to identify why comminication to the node using
        these settings fail.

        This method should raises exceptions based on the failure type. Return
        None means no error, and communication to the node is working as
        expected.

        This is called after `power_on`, `power_off`, or `power_query` fail to
        complete succefully, or the end of the `wait_time` has been reached.
        """
        raise NotImplementedError

    def on(self, system_id, **kwargs):
        """Performs the power on action for `system_id`.

        Do not override `on` method unless you want to provide custom logic on
        how retries and error detection is handled. Override `power_on` for
        just the power on action, and `on` will handle the retrying.
        """
        return self.perform_power('on', system_id, **kwargs)

    def off(self, system_id, **kwargs):
        """Performs the power off action for `system_id`.

        Do not override `off` method unless you want to provide custom logic on
        how retries and error detection is handled. Override `power_off` for
        just the power off action, and `off` will handle the retrying and error
        reporting.
        """
        return self.perform_power('off', system_id, **kwargs)

    @inlineCallbacks
    def query(self, system_id, **kwargs):
        """Performs the power query action for `system_id`."""
        try:
            state = yield deferToThread(
                self.power_query, system_id, **kwargs)
        except PowerError as e:
            try:
                yield deferToThread(self.find_error, system_id, **kwargs)
            except NotImplementedError:
                # Doesn't provide fine grain error detection, so the
                # original error will be reported.
                pass
            except PowerError as e:
                raise e
            # Didn't find the error
            raise e
        returnValue(state)

    @inlineCallbacks
    def perform_power(self, action, system_id, **kwargs):
        """Provides the logic to perform the power actions."""
        if action == 'on':
            action_func = self.power_on
        elif action == 'off':
            action_func = self.power_off

        for waiting_time in self.wait_time:
            error = None
            try:
                # Try to perform power action
                yield deferToThread(
                    action_func, system_id, **kwargs)
            except PowerFatalError as e:
                # Fatal error, no reason to retry.
                raise e
            except PowerError as e:
                # Hold error
                error = e

            # Wait for retry or check
            yield pause(waiting_time, self.clock)

            # Only check power state if no error
            if error is None:
                # Try to get power state
                try:
                    new_power_state = yield deferToThread(
                        self.power_query, system_id, **kwargs)
                except PowerError as e:
                    # Hold error
                    error = e
                    continue

                # If state is now the correct state, done
                if new_power_state == action:
                    return

        # End of waiting, check error
        if error is not None:
            try:
                yield deferToThread(
                    self.find_error, system_id, **kwargs)
            except NotImplementedError:
                # Doesn't provide fine grain error detection, so the
                # original error will be reported.
                pass
            except PowerError as e:
                # Found the error, report it
                raise e
            # Didn't find the error, report the last error
            raise error

        # No error found, so communication to the BMC is good, state
        # must not of changed in the elapsed time. That is the only
        # reason we should make it this far.
        raise PowerError(
            "Failed to power %s. BMC never transitioned from %s to %s."
            % (system_id, new_power_state, action))


class PowerDriverRegistry(Registry):
    """Registry for power drivers."""

    @classmethod
    def get_schema(cls):
        """Returns the full schema for the registry."""
        schemas = [drivers.get_schema() for _, drivers in cls]
        validate(schemas, JSON_POWER_DRIVERS_SCHEMA)
        return schemas


from provisioningserver.drivers.power.mscm import MSCMPowerDriver

builtin_power_drivers = [
    MSCMPowerDriver(),
]
for driver in builtin_power_drivers:
    PowerDriverRegistry.register_item(driver.name, driver)
