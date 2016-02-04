# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Manual Power Driver."""

__all__ = []

from provisioningserver.drivers.power import PowerDriver
from provisioningserver.logger import get_maas_logger
from twisted.internet.defer import inlineCallbacks


maaslog = get_maas_logger("drivers.power.manual")


class ManualPowerDriver(PowerDriver):

    name = 'manual'
    description = "Manual Power Driver."
    settings = []

    def detect_missing_packages(self):
        # no required packages
        return []

    def on(self, system_id, context):
        """Override `on` as we do not need retry logic."""
        return self.power_on(system_id, context)

    def off(self, system_id, context):
        """Override `off` as we do not need retry logic."""
        return self.power_off(system_id, context)

    def query(self, system_id, context):
        """Override `query` as we do not need retry logic."""
        return self.power_query(system_id, context)

    @inlineCallbacks
    def power_on(self, system_id, context):
        """Power on machine manually."""
        yield maaslog.info(
            "You need to power on %s manually." % system_id)

    @inlineCallbacks
    def power_off(self, system_id, context):
        """Power off machine manually."""
        yield maaslog.info(
            "You need to power off %s manually." % system_id)

    @inlineCallbacks
    def power_query(self, system_id, context):
        """Power query machine manually."""
        yield maaslog.info(
            "You need to check power state of %s manually." % system_id)
