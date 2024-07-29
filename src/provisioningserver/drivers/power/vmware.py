# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""VMware Power Driver."""


from provisioningserver.drivers import (
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.hardware import vmware
from provisioningserver.drivers.hardware.vmware import (
    power_control_vmware,
    power_query_vmware,
)
from provisioningserver.drivers.power import PowerDriver


def extract_vmware_parameters(context):
    host = context.get("power_address")
    username = context.get("power_user")
    password = context.get("power_pass")
    vm_name = context.get("power_vm_name")
    uuid = context.get("power_uuid")
    port = context.get("power_port")
    protocol = context.get("power_protocol")
    # Ensure the optional parameters are unambiguously present, or None.
    if port is not None and port.strip() == "":
        port = None
    if protocol is not None and protocol.strip() == "":
        protocol = None
    return host, username, password, vm_name, uuid, port, protocol


class VMwarePowerDriver(PowerDriver):
    name = "vmware"
    chassis = True
    can_probe = True
    can_set_boot_order = False
    description = "VMware"
    settings = [
        make_setting_field(
            "power_vm_name",
            "VM Name (if UUID unknown)",
            required=False,
            scope=SETTING_SCOPE.NODE,
        ),
        make_setting_field(
            "power_uuid",
            "VM UUID (if known)",
            required=False,
            scope=SETTING_SCOPE.NODE,
        ),
        make_setting_field(
            "power_address",
            "VMware IP",
            field_type="ip_address",
            required=True,
        ),
        make_setting_field("power_user", "VMware username", required=True),
        make_setting_field(
            "power_pass",
            "VMware password",
            field_type="password",
            required=True,
            secret=True,
        ),
        make_setting_field(
            "power_port", "VMware API port (optional)", required=False
        ),
        make_setting_field(
            "power_protocol", "VMware API protocol (optional)", required=False
        ),
    ]
    ip_extractor = make_ip_extractor("power_address")

    def detect_missing_packages(self):
        if not vmware.try_pyvmomi_import():
            return ["python3-pyvmomi"]
        return []

    def power_on(self, system_id, context):
        """Power on VMware node."""
        power_change = "on"
        (
            host,
            username,
            password,
            vm_name,
            uuid,
            port,
            protocol,
        ) = extract_vmware_parameters(context)
        power_control_vmware(
            host,
            username,
            password,
            vm_name,
            uuid,
            power_change,
            port,
            protocol,
        )

    def power_off(self, system_id, context):
        """Power off VMware node."""
        power_change = "off"
        (
            host,
            username,
            password,
            vm_name,
            uuid,
            port,
            protocol,
        ) = extract_vmware_parameters(context)
        power_control_vmware(
            host,
            username,
            password,
            vm_name,
            uuid,
            power_change,
            port,
            protocol,
        )

    def power_query(self, system_id, context):
        """Power query VMware node."""
        (
            host,
            username,
            password,
            vm_name,
            uuid,
            port,
            protocol,
        ) = extract_vmware_parameters(context)
        return power_query_vmware(
            host, username, password, vm_name, uuid, port, protocol
        )
