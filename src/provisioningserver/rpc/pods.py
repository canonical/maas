# Copyright 2016-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Pod RPC functions."""

__all__ = [
    "discover_pod",
]

from provisioningserver.drivers.pod import (
    DiscoveredPod,
    get_error_message,
)
from provisioningserver.drivers.pod.registry import PodDriverRegistry
from provisioningserver.logger import (
    get_maas_logger,
    LegacyLogger,
)
from provisioningserver.rpc.exceptions import (
    PodActionFail,
    UnknownPodType,
)
from provisioningserver.utils.twisted import asynchronous
from twisted.internet.defer import Deferred


maaslog = get_maas_logger("pod")
log = LegacyLogger()


@asynchronous
def discover_pod(pod_type, context, pod_id=None, name=None):
    """Discover all the pod information and return the result to the
    region controller.

    The region controller handles parsing the output and updating the database
    as required.
    """
    pod_driver = PodDriverRegistry.get_item(pod_type)
    if pod_driver is None:
        raise UnknownPodType(pod_type)
    d = pod_driver.discover(pod_id, context)
    if not isinstance(d, Deferred):
        raise PodActionFail("bad pod driver; did not return Deferred.")

    def convert(result):
        """Convert the result to send over RPC."""
        if result is None:
            raise PodActionFail("unable to discover pod information.")
        elif not isinstance(result, DiscoveredPod):
            raise PodActionFail("bad pod driver; invalid result.")
        else:
            return {
                "pod": result
            }

    def catch_all(failure):
        """Convert all failures into `PodActionFail` unless already a
        `PodActionFail` or `NotImplementedError`."""
        # Log locally to help debugging.
        log.err(failure, "Failed to discover pod.")
        if failure.check(NotImplementedError, PodActionFail):
            return failure
        else:
            raise PodActionFail(get_error_message(failure.value))

    d.addCallback(convert)
    d.addErrback(catch_all)
    return d
