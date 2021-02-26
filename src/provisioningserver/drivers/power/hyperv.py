"""Hyper-V Power Driver."""

__all__ = []

import importlib
REQUIRED_PACKAGES = [["winrm", "pywinrm"], ]
HYPERV_YES="y"
HYPERV_NO="n"

HYPERV_USE_SSL_CHOICES = [
    [HYPERV_YES, "Yes"],
    [HYPERV_NO, "No"]]

from provisioningserver.drivers import (
    IP_EXTRACTOR_PATTERNS,
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)

from provisioningserver.drivers.power import PowerDriver
from provisioningserver.drivers.hardware.hyperv import (
    power_control_hyperv,
    power_state_hyperv,
)
from provisioningserver.logger import get_maas_logger

maaslog = get_maas_logger("drivers.power.hyperv")

def extract_hyperv_parameters(context):
    poweraddr = context.get("power_address")
    machine = context.get("power_id")
    username = context.get("power_user")
    password = context.get("power_pass")
    use_ssl = (context.get("use_ssl")==HYPERV_YES)

    return poweraddr, machine, username, password, use_ssl

class HypervPowerDriver(PowerDriver):

    name = "hyperv"
    chassis = False
    description = "Hyper-V Power Driver."
    settings = [
        make_setting_field(
            "power_id", 
            "VM Name", 
            required=True,
            scope=SETTING_SCOPE.NODE,
        ),
        make_setting_field(
            "power_address", 
            "Hyper-V hostname", 
            required=True,
        ),
        make_setting_field(
            "power_user", 
            "Hyper-V username", 
            required=True,
        ),
        make_setting_field(
            "power_pass", 
            "Hyper-V password", 
            field_type="password",
            required=True,
        ),
        make_setting_field(
            "power_use_ssl", 
            "Use ssl", 
            field_type='choice', 
            required=True, 
            choices=HYPERV_USE_SSL_CHOICES, 
            default=HYPERV_NO,
        ),
    ]
    ip_extractor = make_ip_extractor("power_address")

    def detect_missing_packages(self):
        missing_packages = set()
        for module, package in REQUIRED_PACKAGES:
            try:
                importlib.import_module(module)
            except ImportError:
                missing_packages.add(package)
        return list(missing_packages)

    def power_on(self, system_id, context):
        """Power on Hyper-V node."""
        power_change = "on"
        poweraddr, machine, username, password, use_ssl = extract_hyperv_parameters(context)
        power_control_hyperv(poweraddr, machine, power_change, username, password, use_ssl)

    def power_off(self, system_id, context):
        """Power off Hyper-V node."""
        power_change = "off"
        poweraddr, machine, username, password, use_ssl = extract_hyperv_parameters(context)
        power_control_hyperv(poweraddr, machine, power_change, username, password, use_ssl)

    def power_query(self, system_id, context):
        """Power query Hyper-V node."""
        poweraddr, machine, username, password, use_ssl = extract_hyperv_parameters(context)
        a = power_state_hyperv(poweraddr, machine, username, password, use_ssl)
        maaslog.warning("state: %s", a)
        return a

