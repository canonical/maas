# Copyright 2017-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Load all power drivers."""

from jsonschema import validate

from maascommon.utils.registry import Registry
from provisioningserver.drivers.pod.registry import PodDriverRegistry
from provisioningserver.drivers.power import JSON_POWER_DRIVERS_SCHEMA
from provisioningserver.drivers.power.manual import ManualPowerDriver
from provisioningserver.drivers.power.webhook import WebhookPowerDriver


class PowerDriverRegistry(Registry):
    """Registry for power drivers."""

    @classmethod
    def get_schema(cls, detect_missing_packages=True):
        """Returns the full schema for the registry."""
        schemas = [
            driver.get_schema(detect_missing_packages=detect_missing_packages)
            for _, driver in cls
        ]
        validate(schemas, JSON_POWER_DRIVERS_SCHEMA)
        return schemas


# Register builtin power drivers.
power_drivers = [
    ManualPowerDriver(),
    WebhookPowerDriver(),
]
for driver in power_drivers:
    PowerDriverRegistry.register_item(driver.name, driver)


# Pod drivers are also power drivers.
for driver_name, driver in PodDriverRegistry:
    PowerDriverRegistry.register_item(driver_name, driver)


def sanitise_power_parameters(power_type, power_parameters):
    """Performs extraction of sensitive parameters and returns them separately.
    Extraction relies on a `secret` flag of the power parameters property.

    :param power_type: BMC power driver type
    :param power_parameters: BMC power parameters
    """
    power_driver = PowerDriverRegistry.get_item(power_type)

    if not power_driver:
        return power_parameters, {}

    secret_params = set(
        setting["name"]
        for setting in power_driver.settings
        if setting.get("secret")
    )

    parameters = {}
    secrets = {}

    for name, value in power_parameters.items():
        if name in secret_params:
            secrets[name] = value
        else:
            parameters[name] = value

    return parameters, secrets
