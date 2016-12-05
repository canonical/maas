# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Chassis RPC functions."""

__all__ = [
    "discover_chassis",
]

from provisioningserver.drivers.chassis import (
    ChassisDriverRegistry,
    DiscoveredChassis,
    get_error_message,
)
from provisioningserver.logger import (
    get_maas_logger,
    LegacyLogger,
)
from provisioningserver.rpc.exceptions import (
    ChassisActionFail,
    UnknownChassisType,
)
from provisioningserver.utils.twisted import asynchronous
from twisted.internet.defer import Deferred


maaslog = get_maas_logger("chassis")
log = LegacyLogger()


@asynchronous
def discover_chassis(chassis_type, context, system_id=None, hostname=None):
    """Discover all the chassis information and return the result to the
    region controller.

    The region controller handles parsing the output and updating the database
    as required.
    """
    chassis_driver = ChassisDriverRegistry.get_item(chassis_type)
    if chassis_driver is None:
        raise UnknownChassisType(chassis_type)
    d = chassis_driver.discover(system_id, context)
    if not isinstance(d, Deferred):
        raise ChassisActionFail("bad chassis driver; did not return Deferred.")

    def convert(result):
        """Convert the result to send over RPC."""
        if result is None:
            raise ChassisActionFail("unable to discover chassis information.")
        elif not isinstance(result, DiscoveredChassis):
            raise ChassisActionFail("bad chassis driver; invalid result.")
        else:
            return {
                "chassis": result
            }

    def catch_all(failure):
        """Convert all failures into `ChassisActionFail` unless already a
        `ChassisActionFail` or `NotImplementedError`."""
        if failure.check(NotImplementedError, ChassisActionFail):
            return failure
        else:
            raise ChassisActionFail(get_error_message(failure.value))

    d.addCallback(convert)
    d.addErrback(catch_all)
    return d
