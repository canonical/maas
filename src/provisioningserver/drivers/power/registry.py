# Copyright 2017-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Load all power drivers."""

from jsonschema import validate

from provisioningserver.drivers.pod.registry import PodDriverRegistry
from provisioningserver.drivers.power import JSON_POWER_DRIVERS_SCHEMA
from provisioningserver.drivers.power.amt import AMTPowerDriver
from provisioningserver.drivers.power.apc import APCPowerDriver
from provisioningserver.drivers.power.dli import DLIPowerDriver
from provisioningserver.drivers.power.eaton import EatonPowerDriver
from provisioningserver.drivers.power.hmc import HMCPowerDriver
from provisioningserver.drivers.power.hmcz import HMCZPowerDriver
from provisioningserver.drivers.power.ipmi import IPMIPowerDriver
from provisioningserver.drivers.power.manual import ManualPowerDriver
from provisioningserver.drivers.power.moonshot import MoonshotIPMIPowerDriver
from provisioningserver.drivers.power.mscm import MSCMPowerDriver
from provisioningserver.drivers.power.msftocs import MicrosoftOCSPowerDriver
from provisioningserver.drivers.power.nova import NovaPowerDriver
from provisioningserver.drivers.power.openbmc import OpenBMCPowerDriver
from provisioningserver.drivers.power.proxmox import ProxmoxPowerDriver
from provisioningserver.drivers.power.raritan import RaritanPowerDriver
from provisioningserver.drivers.power.recs import RECSPowerDriver
from provisioningserver.drivers.power.redfish import RedfishPowerDriver
from provisioningserver.drivers.power.seamicro import SeaMicroPowerDriver
from provisioningserver.drivers.power.ucsm import UCSMPowerDriver
from provisioningserver.drivers.power.vmware import VMwarePowerDriver
from provisioningserver.drivers.power.webhook import WebhookPowerDriver
from provisioningserver.drivers.power.wedge import WedgePowerDriver
from provisioningserver.utils.registry import Registry


class PowerDriverRegistry(Registry):
    """Registry for power drivers."""

    @classmethod
    def get_schema(cls, detect_missing_packages=True):
        """Returns the full schema for the registry."""
        # Pod drivers are not included in the schema because they should
        # be used through `PodDriverRegistry`, except when a power action
        # is to be performed.
        schemas = [
            driver.get_schema(detect_missing_packages=detect_missing_packages)
            for _, driver in cls
        ]
        validate(schemas, JSON_POWER_DRIVERS_SCHEMA)
        return schemas


# Register all the power drivers.
power_drivers = [
    AMTPowerDriver(),
    APCPowerDriver(),
    DLIPowerDriver(),
    EatonPowerDriver(),
    HMCPowerDriver(),
    HMCZPowerDriver(),
    IPMIPowerDriver(),
    ManualPowerDriver(),
    MoonshotIPMIPowerDriver(),
    MSCMPowerDriver(),
    MicrosoftOCSPowerDriver(),
    NovaPowerDriver(),
    OpenBMCPowerDriver(),
    ProxmoxPowerDriver(),
    RaritanPowerDriver(),
    RECSPowerDriver(),
    RedfishPowerDriver(),
    SeaMicroPowerDriver(),
    UCSMPowerDriver(),
    VMwarePowerDriver(),
    WebhookPowerDriver(),
    WedgePowerDriver(),
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
