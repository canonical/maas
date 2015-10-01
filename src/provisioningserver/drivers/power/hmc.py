# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Moonshot HP iLO Chassis Power Driver."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from provisioningserver.drivers.hardware.hmc import (
    power_control_hmc,
    power_state_hmc,
    required_package,
)
from provisioningserver.drivers.power import PowerDriver
from provisioningserver.utils import shell


def extract_hmc_parameters(params):
    ip = params.get('power_address')
    username = params.get('power_user')
    password = params.get('power_pass')
    server_name = params.get('server_name')
    lpar = params.get('lpar')
    return ip, username, password, server_name, lpar


class HMCPowerDriver(PowerDriver):

    name = 'hmc'
    description = "IBM Hardware Management Console Power Driver."
    settings = []

    def detect_missing_packages(self):
        binary, package = required_package()
        if not shell.has_command_available(binary):
            return [package]
        return []

    def power_on(self, system_id, **kwargs):
        ip, username, password, server_name, lpar = (
            extract_hmc_parameters(kwargs))
        power_control_hmc(
            ip, username, password, server_name, lpar, power_change='on')

    def power_off(self, system_id, **kwargs):
        ip, username, password, server_name, lpar = (
            extract_hmc_parameters(kwargs))
        power_control_hmc(
            ip, username, password, server_name, lpar, power_change='off')

    def power_query(self, system_id, **kwargs):
        ip, username, password, server_name, lpar = (
            extract_hmc_parameters(kwargs))
        return power_state_hmc(ip, username, password, server_name, lpar)
