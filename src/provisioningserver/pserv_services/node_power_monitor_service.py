# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Service to periodically query the power state on this cluster's nodes."""


from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "NodePowerMonitorService"
]

from datetime import timedelta

from provisioningserver.logger.log import get_maas_logger
from provisioningserver.rpc import getRegionClient
from provisioningserver.rpc.exceptions import (
    NoConnectionsAvailable,
    NoSuchCluster,
)
from provisioningserver.rpc.power import query_all_nodes
from provisioningserver.rpc.region import ListNodePowerParameters
from provisioningserver.utils.twisted import (
    pause,
    retries,
)
from twisted.application.internet import TimerService
from twisted.internet.defer import inlineCallbacks
from twisted.python import log


maaslog = get_maas_logger("power_monitor_service")


class NodePowerMonitorService(TimerService, object):
    """Service to monitor the power status of all nodes in this cluster."""

    check_interval = timedelta(minutes=5).total_seconds()
    max_nodes_at_once = 5

    def __init__(self, cluster_uuid, clock=None):
        # Call self.query_nodes() every self.check_interval.
        super(NodePowerMonitorService, self).__init__(
            self.check_interval, self.try_query_nodes, cluster_uuid)
        self.clock = clock

    def try_query_nodes(self, uuid):
        """Attempt to query nodes' power states.

        Log errors on failure, but do not propagate them up; that will
        stop the timed loop from running.
        """
        def query_nodes_failed(failure):
            # Log the error in full to the Twisted log.
            log.err(failure)
            # Log something concise to the MAAS log.
            maaslog.error(
                "Failed to query nodes' power status: %s",
                failure.getErrorMessage())

        return self.query_nodes(uuid).addErrback(query_nodes_failed)

    @inlineCallbacks
    def query_nodes(self, uuid):
        # Retry a few times, since this service usually comes up before
        # the RPC service.
        for elapsed, remaining, wait in retries(15, 5, self.clock):
            try:
                client = getRegionClient()
            except NoConnectionsAvailable:
                yield pause(wait, self.clock)
            else:
                break
        else:
            maaslog.error(
                "Cannot monitor nodes' power status; "
                "region not available.")
            return

        # Get the nodes' power parameters from the region.
        try:
            response = yield client(ListNodePowerParameters, uuid=uuid)
        except NoSuchCluster:
            maaslog.error(
                "This cluster (%s) is not recognised by the region.",
                uuid)
        else:
            node_power_parameters = response['nodes']
            yield query_all_nodes(
                node_power_parameters,
                max_concurrency=self.max_nodes_at_once, clock=self.clock)
