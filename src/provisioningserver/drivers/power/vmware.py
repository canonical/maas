# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""VMware Power Driver."""

__all__ = []

from provisioningserver.drivers.hardware import vmware
from provisioningserver.drivers.hardware.vmware import (
    power_control_vmware,
    power_query_vmware,
)
from provisioningserver.drivers.power import PowerDriver


def extract_vmware_parameters(context):
    host = context.get('power_address')
    username = context.get('power_user')
    password = context.get('power_pass')
    vm_name = context.get('power_vm_name')
    uuid = context.get('power_uuid')
    port = context.get('power_port')
    protocol = context.get('power_protocol')
    return host, username, password, vm_name, uuid, port, protocol


class VMwarePowerDriver(PowerDriver):

    name = 'vmware'
    description = "VMware Power Driver."
    settings = []

    def detect_missing_packages(self):
        if not vmware.try_pyvmomi_import():
            return ["python-pyvmomi"]
        return []

    def power_on(self, system_id, context):
        """Power on VMware node."""
        power_change = 'on'
        host, username, password, vm_name, uuid, port, protocol = (
            extract_vmware_parameters(context))
        power_control_vmware(
            host, username, password, vm_name,
            uuid, power_change, port, protocol)

    def power_off(self, system_id, context):
        """Power off VMware node."""
        power_change = 'off'
        host, username, password, vm_name, uuid, port, protocol = (
            extract_vmware_parameters(context))
        power_control_vmware(
            host, username, password, vm_name,
            uuid, power_change, port, protocol)

    def power_query(self, system_id, context):
        """Power query VMware node."""
        host, username, password, vm_name, uuid, port, protocol = (
            extract_vmware_parameters(context))
        return power_query_vmware(
            host, username, password, vm_name, uuid, port, protocol)
