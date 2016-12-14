# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Null chassis driver."""

__all__ = [
    "NullChassisDriver",
    ]

from provisioningserver.drivers.chassis import (
    ChassisDriver,
    DiscoveredChassis,
    DiscoveredChassisHints,
)
from twisted.internet.defer import succeed


class NullChassisDriver(ChassisDriver):

    name = "null"
    description = "Null Test Chassis Driver"
    settings = []
    ip_extractor = None
    queryable = True

    def discover(self, system_id, context):
        return succeed(
            DiscoveredChassis(
                cores=0, cpu_speed=0, local_storage=0, memory=0,
                hints=DiscoveredChassisHints(
                    cores=0, local_storage=0, memory=0)))

    def compose(self, system_id, context):
        return None

    def decompose(self, system_id, context):
        return None

    def detect_missing_packages(self):
        return []

    def power_on(self, system_id, context):
        return 'on'

    def power_off(self, system_id, context):
        return 'off'

    def power_query(self, system_id, context):
        return 'unknown'
