# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Base NOS driver."""


from abc import ABCMeta, abstractmethod, abstractproperty

from jsonschema import validate
from twisted.internet import reactor

from provisioningserver.drivers import SETTING_PARAMETER_FIELD_SCHEMA

# We specifically declare this here so that a switch not knowing its own
# NOS driver won't fail to enlist nor do we want this in the list of NOS
# drivers.
UNKNOWN_NOS_DRIVER = ""

# JSON schema for what a NOS driver definition should look like.
JSON_NOS_DRIVER_SCHEMA = {
    "title": "NOS driver setting set",
    "type": "object",
    "properties": {
        "driver_type": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "fields": {"type": "array", "items": SETTING_PARAMETER_FIELD_SCHEMA},
    },
    "required": ["driver_type", "name", "description", "fields"],
}


# JSON schema for multiple NOS drivers.
JSON_NOS_DRIVERS_SCHEMA = {
    "title": "NOS drivers parameters set",
    "type": "array",
    "items": JSON_NOS_DRIVER_SCHEMA,
}


class NOSError(Exception):
    """Base error for all network operating system failure commands."""


class NOSDriverBase(metaclass=ABCMeta):
    """Base driver for a NOS driver."""

    def __init__(self):
        super().__init__()
        validate(self.get_schema(), JSON_NOS_DRIVER_SCHEMA)

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
        to the `on`, `off`, and `query` using the context. It is up
        to the driver to read these options before performing the operation.
        """

    @abstractproperty
    def deployable(self):
        """Whether or not the NOS driver is deployable."""

    @abstractmethod
    def is_switch_supported(self, vendor, model):
        """Returns whether this driver supports a particular switch model."""

    def get_schema(self):
        """Returns the JSON schema for the driver."""
        schema = dict(
            driver_type="nos",
            name=self.name,
            description=self.description,
            fields=self.settings,
            deployable=self.deployable,
        )
        return schema

    def get_setting(self, name):
        """Return the setting field by its name."""
        for setting in self.settings:
            if setting["name"] == name:
                return setting
        return None


class NOSDriver(NOSDriverBase):
    """Default NOS driver logic."""

    deployable = False

    def __init__(self, clock=reactor):
        self.clock = reactor
