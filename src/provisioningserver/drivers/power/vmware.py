# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""VMware Power Driver."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from provisioningserver.drivers.hardware.vmware import (
    power_control_vmware,
    power_query_vmware,
)
from provisioningserver.drivers.power import PowerDriver


def extract_vmware_parameters(params):
    host = params.get('power_address')
    username = params.get('power_user')
    password = params.get('power_pass')
    vm_name = params.get('power_vm_name')
    uuid = params.get('power_uuid')
    port = params.get('power_port')
    protocol = params.get('power_protocol')
    return host, username, password, vm_name, uuid, port, protocol


class VMwarePowerDriver(PowerDriver):

    name = 'vmware'
    description = "VMware Power Driver."
    settings = []

    def power_on(self, system_id, **kwargs):
        """Power on VMware node."""
        power_change = 'on'
        host, username, password, vm_name, uuid, port, protocol = (
            extract_vmware_parameters(kwargs))
        power_control_vmware(
            host, username, password, vm_name,
            uuid, power_change, port, protocol)

    def power_off(self, system_id, **kwargs):
        """Power off VMware node."""
        power_change = 'off'
        host, username, password, vm_name, uuid, port, protocol = (
            extract_vmware_parameters(kwargs))
        power_control_vmware(
            host, username, password, vm_name,
            uuid, power_change, port, protocol)

    def power_query(self, system_id, **kwargs):
        """Power query VMware node."""
        host, username, password, vm_name, uuid, port, protocol = (
            extract_vmware_parameters(kwargs))
        return power_query_vmware(
            host, username, password, vm_name, uuid, port, protocol)
