# Copyright 2014-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Base power driver."""

from abc import ABCMeta, abstractmethod
import sys

from jsonschema import validate
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.threads import deferToThread

from provisioningserver.drivers import (
    IP_EXTRACTOR_SCHEMA,
    MULTIPLE_CHOICE_SETTING_PARAMETER_FIELD_SCHEMA,
    SETTING_PARAMETER_FIELD_SCHEMA,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.twisted import IAsynchronous, pause

# We specifically declare this here so that a node not knowing its own
# powertype won't fail to enlist. However, we don't want it in the list
# of power types since setting a node's power type to "I don't know"
# from another type doens't make any sense.
UNKNOWN_POWER_TYPE = ""

# A policy used when waiting between retries of power changes.
DEFAULT_WAITING_POLICY = (1, 2, 2, 4, 6, 8, 12)

# JSON schema for what a power driver definition should look like
JSON_POWER_DRIVER_SCHEMA = {
    "title": "Power driver setting set",
    "type": "object",
    "properties": {
        "driver_type": {"type": "string"},
        "name": {"type": "string"},
        "chassis": {"type": "boolean"},
        "can_probe": {"type": "boolean"},
        "can_set_boot_order": {"type": "boolean"},
        "description": {"type": "string"},
        "fields": {
            "type": "array",
            "items": {
                "anyOf": [
                    SETTING_PARAMETER_FIELD_SCHEMA,
                    MULTIPLE_CHOICE_SETTING_PARAMETER_FIELD_SCHEMA,
                ],
            },
        },
        "ip_extractor": IP_EXTRACTOR_SCHEMA,
        "queryable": {"type": "boolean"},
        "missing_packages": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["driver_type", "name", "description", "fields"],
}

# JSON schema for multiple power drivers.
JSON_POWER_DRIVERS_SCHEMA = {
    "title": "Power drivers parameters set",
    "type": "array",
    "items": JSON_POWER_DRIVER_SCHEMA,
}


maaslog = get_maas_logger("drivers.power")


def is_power_parameter_set(param):
    return not (param is None or param == "" or param.isspace())


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


class PowerAuthError(PowerFatalError):
    """Error raised when power driver fails to authenticate to BMC.

    This exception will cause the power action to fail instantly,
    without retrying.
    """


class PowerConnError(PowerError):
    """Error raised when power driver fails to communicate to BMC."""


class PowerActionError(PowerError):
    """Error when actually performing an action on the BMC, like `on`
    or `off`."""


class PowerDriverBase(metaclass=ABCMeta):
    """Base driver for a power driver."""

    def __init__(self):
        super().__init__()
        validate(
            self.get_schema(detect_missing_packages=False),
            JSON_POWER_DRIVER_SCHEMA,
        )

    @property
    @abstractmethod
    def name(self):
        """Name of the power driver."""

    @property
    @abstractmethod
    def description(self):
        """Description of the power driver."""

    @property
    @abstractmethod
    def settings(self):
        """List of settings for the driver.

        Each setting in this list will be different per user. They are passed
        to the `on`, `off`, and `query` using the context. It is up
        to the driver to read these options before performing the operation.
        """

    @property
    @abstractmethod
    def ip_extractor(self):
        """IP extractor.

        Name of the settings field and python REGEX pattern for extracting IP
        the address from the value.
        """

    @property
    @abstractmethod
    def queryable(self):
        """Whether or not the power driver is queryable."""

    @property
    @abstractmethod
    def chassis(self):
        """Return True if the power driver is for a chassis."""

    @property
    @abstractmethod
    def can_probe(self):
        """Return True if the power driver can be used with add_chassis."""

    @property
    @abstractmethod
    def can_set_boot_order(self):
        """Returns True if the boot order can be remotely set."""

    @abstractmethod
    def detect_missing_packages(self):
        """Implement this method for the actual implementation
        of the check for the driver's missing support packages.
        """

    @abstractmethod
    def on(self, system_id, context):
        """Perform the power on action for `system_id`.

        :param system_id: `Node.system_id`
        :param context: Power settings for the node.
        """

    @abstractmethod
    def off(self, system_id, context):
        """Perform the power off action for `system_id`.

        :param system_id: `Node.system_id`
        :param context: Power settings for the node.
        """

    @abstractmethod
    def cycle(self, system_id, context):
        """Perform the cycle action for `system_id`.

        :param system_id: `Node.system_id`
        :param context: Power settings for the node.
        """

    @abstractmethod
    def query(self, system_id, context):
        """Perform the query action for `system_id`.

        :param system_id: `Node.system_id`
        :param context: Power settings for the node.
        :return: status of power on BMC. `on` or `off`.
        :raises PowerError: states unable to get status from BMC. It is
            up to this method to report the actual issue to the Region. The
            calling function should ignore this error, and continue on.
        """

    def set_boot_order(self, system_id, context, order):
        """Set the specified boot order.

        :param system_id: `Node.system_id`
        :param context: Power settings for the node.
        :param order: An ordered list of network or storage devices.
        """
        raise NotImplementedError()

    def get_schema(self, detect_missing_packages=True):
        """Returns the JSON schema for the driver.

        Calculates the missing packages on each invoke.
        """
        schema = dict(
            driver_type="power",
            name=self.name,
            description=self.description,
            chassis=self.chassis,
            can_probe=self.can_probe,
            fields=self.settings,
            queryable=self.queryable,
            missing_packages=(
                self.detect_missing_packages()
                if detect_missing_packages
                else []
            ),
        )
        if self.ip_extractor is not None:
            schema["ip_extractor"] = self.ip_extractor
        return schema

    def get_setting(self, name):
        """Return the setting field by its name."""
        for setting in self.settings:
            if setting["name"] == name:
                return setting
        return None


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
        return "Failed talking to node's BMC: %s" % err


class PowerDriver(PowerDriverBase):
    """Default power driver logic."""

    wait_time = DEFAULT_WAITING_POLICY
    queryable = True

    def __init__(self, clock=reactor):
        self.clock = clock

    @abstractmethod
    def power_on(self, system_id, context):
        """Implement this method for the actual implementation
        of the power on command.
        """

    @abstractmethod
    def power_off(self, system_id, context):
        """Implement this method for the actual implementation
        of the power off command.
        """

    @abstractmethod
    def power_query(self, system_id, context):
        """Implement this method for the actual implementation
        of the power query command."""

    def on(self, system_id, context):
        """Performs the power on action for `system_id`.

        Do not override `on` method unless you want to provide custom logic on
        how retries and error detection is handled. Override `power_on` for
        just the power on action, and `on` will handle the retrying.
        """
        return self.perform_power(self.power_on, "on", system_id, context)

    def off(self, system_id, context):
        """Performs the power off action for `system_id`.

        Do not override `off` method unless you want to provide custom logic on
        how retries and error detection is handled. Override `power_off` for
        just the power off action, and `off` will handle the retrying and error
        reporting.
        """
        return self.perform_power(self.power_off, "off", system_id, context)

    @inlineCallbacks
    def cycle(self, system_id, context):
        """Performs the power cycle action for `system_id`.

        Do not override `cycle` method unless you want to provide custom logic
        on how retries and error detection is handled.
        """
        state = yield self.query(system_id, context)
        if state == "on":
            yield self.perform_power(self.power_off, "off", system_id, context)
        yield self.perform_power(self.power_on, "on", system_id, context)

    @inlineCallbacks
    def query(self, system_id, context):
        """Performs the power query action for `system_id`."""
        exc_info = None, None, None
        for waiting_time in self.wait_time:
            try:
                # Power queries are predominantly transactional and thus
                # blocking/synchronous. Genuinely non-blocking/asynchronous
                # methods must out themselves explicitly.
                if IAsynchronous.providedBy(self.power_query):
                    # The @asynchronous decorator will DTRT.
                    state = yield self.power_query(system_id, context)
                else:
                    state = yield deferToThread(
                        self.power_query, system_id, context
                    )
            except PowerFatalError:
                raise  # Don't retry.
            except PowerError:
                exc_info = sys.exc_info()
                # Wait before retrying.
                yield pause(waiting_time, self.clock)
            else:
                returnValue(state)
        else:
            raise exc_info[0](exc_info[1]).with_traceback(exc_info[2])

    @inlineCallbacks
    def perform_power(self, power_func, state_desired, system_id, context):
        """Provides the logic to perform the power actions.

        :param power_func: Function used to change the power state of the
            node. Typically this will be `self.power_on` or `self.power_off`.
        :param state_desired: The desired state for this node to be in,
            typically "on" or "off".
        :param system_id: The node's system ID.
        """

        state = "unknown"
        exc_info = None, None, None

        for waiting_time in self.wait_time:
            # Try to change state.
            try:
                # Power methods are predominantly transactional and thus
                # blocking/synchronous. Genuinely non-blocking/asynchronous
                # methods must out themselves explicitly.
                if IAsynchronous.providedBy(power_func):
                    # The @asynchronous decorator will DTRT.
                    yield power_func(system_id, context)
                else:
                    yield deferToThread(power_func, system_id, context)
            except PowerFatalError:
                raise  # Don't retry.
            except PowerError:
                exc_info = sys.exc_info()
                # Wait before retrying.
                yield pause(waiting_time, self.clock)
            else:
                # LP:1768659 - If the power driver isn't queryable(manual)
                # checking the power state will always fail.
                if not self.queryable:
                    return
                # Wait before checking state.
                maaslog.debug(f"Pausing {waiting_time} before checking state")
                yield pause(waiting_time, self.clock)
                # Try to get power state.
                try:
                    # Power queries are predominantly transactional and thus
                    # blocking/synchronous. Genuinely non-blocking/asynchronous
                    # methods must out themselves explicitly.
                    if IAsynchronous.providedBy(self.power_query):
                        # The @asynchronous decorator will DTRT.
                        state = yield self.power_query(system_id, context)
                    else:
                        state = yield deferToThread(
                            self.power_query, system_id, context
                        )
                except PowerFatalError:
                    raise  # Don't retry.
                except PowerError:
                    exc_info = sys.exc_info()
                else:
                    # If state is now the correct state, done.
                    if state == state_desired:
                        return
                    else:
                        maaslog.info(
                            f"Machine is {state} and not {state_desired} as expected."
                        )

        if exc_info == (None, None, None):
            # No error found, so communication to the BMC is good, state must
            # have not changed in the elapsed time. That is the only reason we
            # should make it this far.
            raise PowerError(
                "Failed to power %s. BMC never transitioned from %s to %s."
                % (system_id, state, state_desired)
            )
        else:
            # Report the last error.
            raise exc_info[0](exc_info[1]).with_traceback(exc_info[2])
