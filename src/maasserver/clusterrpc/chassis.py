# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers related to chassis."""

__all__ = [
    "discover_chassis",
    ]

from maasserver.rpc import getAllClients
from provisioningserver.rpc.cluster import DiscoverChassis
from provisioningserver.rpc.exceptions import (
    ChassisActionFail,
    UnknownChassisType,
)
from provisioningserver.utils.twisted import (
    asynchronous,
    deferWithTimeout,
    FOREVER,
)
from twisted.internet.defer import DeferredList


@asynchronous(timeout=FOREVER)
def discover_chassis(
        chassis_type, context, system_id=None, hostname=None, timeout=120):
    """Discover a chassis.

    :param chassis_type: Type of chassis to discover.
    :param context: Chassis driver information to connect to chassis.
    :param system_id: ID of the chassis in the database (None if new chassis).
    :param hostname: Hostname of the chassis in the database (None if
        new chassis).

    :returns: Return a tuple with mapping of rack controller system_id and the
        discovered chassis information and a mapping of rack controller
        system_id and the failure exception.
    """
    def discover(client):
        return deferWithTimeout(
            timeout, client, DiscoverChassis, chassis_type=chassis_type,
            context=context, system_id=system_id, hostname=hostname)

    clients = getAllClients()
    dl = DeferredList(map(discover, clients), consumeErrors=True)

    def cb_results(results):
        discovered, failures = {}, {}
        for client, (success, result) in zip(clients, results):
            if success:
                discovered[client.ident] = result["chassis"]
            else:
                failures[client.ident] = result.value
        return discovered, failures

    return dl.addCallback(cb_results)


def get_best_discovered_result(discovered):
    """Return the `DiscoveredChassis` from `discovered` or raise an error
    if nothing was discovered or the best error return from the rack
    controlllers."""
    discovered, exceptions = discovered
    if len(discovered) > 0:
        # Return the first `DiscoveredChassis`. They should all be the same.
        return list(discovered.values())[0]
    elif len(exceptions) > 0:
        # Raise the best exception that provides the most detail.
        for exc_type in [
                ChassisActionFail, NotImplementedError,
                UnknownChassisType, None]:
            for _, exc in exceptions.items():
                if exc_type is not None:
                    if isinstance(exc, exc_type):
                        raise exc
                else:
                    raise exc
    else:
        return None
