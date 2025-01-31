# Copyright 2016-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Manual Power Driver."""


from twisted.internet.defer import maybeDeferred

from provisioningserver.drivers.power import PowerDriver
from provisioningserver.logger import get_maas_logger

maaslog = get_maas_logger("drivers.power.manual")


class ManualPowerDriver(PowerDriver):
    name = "manual"
    chassis = False
    can_probe = False
    can_set_boot_order = False
    description = "Manual"
    settings = []
    ip_extractor = None
    queryable = False

    def detect_missing_packages(self):
        # no required packages
        return []

    def on(self, system_id, context):
        """Override `on` as we do not need retry logic."""
        return maybeDeferred(self.power_on, system_id, context)

    def off(self, system_id, context):
        """Override `off` as we do not need retry logic."""
        return maybeDeferred(self.power_off, system_id, context)

    def query(self, system_id, context):
        """Override `query` as we do not need retry logic."""
        return maybeDeferred(self.power_query, system_id, context)

    def reset(self, system_id, context):
        """Override `reset` as we do not need retry logic."""
        return maybeDeferred(self.power_reset, system_id, context)

    def power_on(self, system_id, context):
        """Power on machine manually."""
        maaslog.info(f"You need to power on {system_id} manually.")

    def power_off(self, system_id, context):
        """Power off machine manually."""
        maaslog.info(f"You need to power off {system_id} manually.")

    def power_query(self, system_id, context):
        """Power query machine manually."""
        maaslog.info(f"You need to check power state of {system_id} manually.")
        return "unknown"

    def power_reset(self, system_id, context):
        """Power reset machine manually."""
        maaslog.info(f"You need to power reset {system_id} manually.")
