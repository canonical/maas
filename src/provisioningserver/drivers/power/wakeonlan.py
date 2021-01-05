# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Wake on LAN Power Driver."""

__all__ = []

from provisioningserver.drivers.power import PowerDriver
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils import shell
from twisted.internet.defer import maybeDeferred
from provisioningserver.drivers.power import (
    is_power_parameter_set,
    PowerAuthError,
    PowerConnError,
    PowerDriver,
    PowerError,
    PowerFatalError,
    PowerSettingError,
)
from provisioningserver.utils.network import (
    find_ip_via_arp,
    find_mac_via_arp
)
import subprocess
from provisioningserver.drivers import (
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.utils.shell import (
    call_and_check,
    ExternalProcessError,
)

maaslog = get_maas_logger("drivers.power.wakeonlan")

REQUIRED_PACKAGES = [["wakeonlan", "wakeonlan"]]

class WakeOnLANPowerDriver(PowerDriver):

    name = 'wakeonlan'
    description = "Wake on LAN Power Driver"
    chassis = True
    can_probe = True
    settings = [
        make_setting_field(
            "power_mac",
            "MAC address",
            required=False,
            scope=SETTING_SCOPE.NODE,
        )
    ]
    ip_extractor = None

    def _check_server_status(self, request):
        args = ["ping", "-c", "1"]
        if request.get("interface"):
            args += ["-I", request["interface"]]
        args += [request["ip_address"]]
        try:
            call_and_check(args)
            maaslog.info("Power state for %s is on" % request["ip_address"])
            return 'on'
        except Exception:
            maaslog.info("Power state %s is off" % request["ip_address"])
            return 'off'

    def detect_missing_packages(self):
        missing_packages = set()
        for binary, package in REQUIRED_PACKAGES:
            if not shell.has_command_available(binary):
                missing_packages.add(package)
        return list(missing_packages)

    def on(self, system_id, context):
        """Override `on` as we do not need retry logic."""
        
        return maybeDeferred(self.power_on, system_id, context)

    def off(self, system_id, context):
        """Override `off` as we do not need retry logic."""
        
        return maybeDeferred(self.power_off, system_id, context)

    def query(self, system_id, context):
        """Override `query` as we do not need retry logic."""
        
        return maybeDeferred(self.power_query, system_id, context)

    def power_on(self, system_id, context):
        """Power on machine using wake on lan."""
        
        subprocess.call(["wakeonlan", context.get("power_mac")])


    def power_off(self, system_id, context):
        """Power off machine manually."""
        
        maaslog.info("You need to power off %s manually." % system_id)

    def power_query(self, system_id, context):
        """Power query machine manually."""
        request = {}
        mac = context.get("power_mac")
        request["ip_address"] = find_ip_via_arp(mac)
        if request["ip_address"] is None:
            maaslog.info("Cannot find IP for %s" % mac)
            return 'off'
        return self._check_server_status(request)
            