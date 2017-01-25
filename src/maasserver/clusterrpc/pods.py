# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers related to pod."""

__all__ = [
    "discover_pod",
    ]

from maasserver.rpc import getAllClients
from provisioningserver.rpc.cluster import DiscoverPod
from provisioningserver.rpc.exceptions import (
    PodActionFail,
    UnknownPodType,
)
from provisioningserver.utils.twisted import (
    asynchronous,
    deferWithTimeout,
    FOREVER,
)
from twisted.internet.defer import DeferredList


@asynchronous(timeout=FOREVER)
def discover_pod(
        pod_type, context, pod_id=None, name=None, timeout=120):
    """Discover a pod.

    :param pod_type: Type of pod to discover.
    :param context: Pod driver information to connect to pod.
    :param pod_id: ID of the pod in the database (None if new pod).
    :param name: Name of the pod in the database (None if
        new pod).

    :returns: Return a tuple with mapping of rack controller system_id and the
        discovered pod information and a mapping of rack controller
        system_id and the failure exception.
    """
    def discover(client):
        return deferWithTimeout(
            timeout, client, DiscoverPod, type=pod_type,
            context=context, pod_id=pod_id, name=name)

    clients = getAllClients()
    dl = DeferredList(map(discover, clients), consumeErrors=True)

    def cb_results(results):
        discovered, failures = {}, {}
        for client, (success, result) in zip(clients, results):
            if success:
                discovered[client.ident] = result["pod"]
            else:
                failures[client.ident] = result.value
        return discovered, failures

    return dl.addCallback(cb_results)


def get_best_discovered_result(discovered):
    """Return the `DiscoveredPod` from `discovered` or raise an error
    if nothing was discovered or the best error return from the rack
    controlllers."""
    discovered, exceptions = discovered
    if len(discovered) > 0:
        # Return the first `DiscoveredPod`. They should all be the same.
        return list(discovered.values())[0]
    elif len(exceptions) > 0:
        # Raise the best exception that provides the most detail.
        for exc_type in [
                PodActionFail, NotImplementedError,
                UnknownPodType, None]:
            for _, exc in exceptions.items():
                if exc_type is not None:
                    if isinstance(exc, exc_type):
                        raise exc
                else:
                    raise exc
    else:
        return None
