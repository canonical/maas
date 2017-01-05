# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Load all power drivers."""

__all__ = [
    "PowerDriverRegistry",
    ]

from jsonschema import validate
from provisioningserver.drivers.chassis import ChassisDriverBase
from provisioningserver.drivers.chassis.registry import ChassisDriverRegistry
from provisioningserver.drivers.power import JSON_POWER_DRIVERS_SCHEMA
from provisioningserver.drivers.power.amt import AMTPowerDriver
from provisioningserver.drivers.power.apc import APCPowerDriver
from provisioningserver.drivers.power.dli import DLIPowerDriver
from provisioningserver.drivers.power.fence_cdu import FenceCDUPowerDriver
from provisioningserver.drivers.power.hmc import HMCPowerDriver
from provisioningserver.drivers.power.ipmi import IPMIPowerDriver
from provisioningserver.drivers.power.manual import ManualPowerDriver
from provisioningserver.drivers.power.moonshot import MoonshotIPMIPowerDriver
from provisioningserver.drivers.power.mscm import MSCMPowerDriver
from provisioningserver.drivers.power.msftocs import MicrosoftOCSPowerDriver
from provisioningserver.drivers.power.nova import NovaPowerDriver
from provisioningserver.drivers.power.seamicro import SeaMicroPowerDriver
from provisioningserver.drivers.power.ucsm import UCSMPowerDriver
from provisioningserver.drivers.power.virsh import VirshPowerDriver
from provisioningserver.drivers.power.vmware import VMwarePowerDriver
from provisioningserver.drivers.power.wedge import WedgePowerDriver
from provisioningserver.utils.registry import Registry


class PowerDriverRegistry(Registry):
    """Registry for power drivers."""

    @classmethod
    def get_schema(cls, detect_missing_packages=True):
        """Returns the full schema for the registry."""
        # Chassis drivers are not included in the schema because they should
        # be used through `ChassisDriverRegistry`, except when a power action
        # is to be performed.
        schemas = [
            driver.get_schema(detect_missing_packages=detect_missing_packages)
            for _, driver in cls.only_power()
        ]
        validate(schemas, JSON_POWER_DRIVERS_SCHEMA)
        return schemas

    @classmethod
    def only_power(cls):
        """Return only drivers that are not also chassis drivers."""
        for driver_name, driver in cls:
            if not isinstance(driver, ChassisDriverBase):
                yield (driver_name, driver)


# Register all the power drivers.
power_drivers = [
    AMTPowerDriver(),
    APCPowerDriver(),
    DLIPowerDriver(),
    FenceCDUPowerDriver(),
    HMCPowerDriver(),
    IPMIPowerDriver(),
    ManualPowerDriver(),
    MoonshotIPMIPowerDriver(),
    MSCMPowerDriver(),
    MicrosoftOCSPowerDriver(),
    NovaPowerDriver(),
    SeaMicroPowerDriver(),
    UCSMPowerDriver(),
    VirshPowerDriver(),
    VMwarePowerDriver(),
    WedgePowerDriver(),
]
for driver in power_drivers:
    PowerDriverRegistry.register_item(driver.name, driver)


# Chassis drivers are also power drivers.
for driver_name, driver in ChassisDriverRegistry:
    PowerDriverRegistry.register_item(driver_name, driver)
