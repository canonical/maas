# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Service to periodically query the power state on this cluster's nodes."""

from datetime import timedelta

from twisted.application.internet import TimerService
from twisted.internet.defer import inlineCallbacks
from twisted.internet.error import ConnectionDone

from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.rpc import getRegionClient
from provisioningserver.rpc.exceptions import (
    NoConnectionsAvailable,
    NoSuchCluster,
)
from provisioningserver.rpc.power import query_all_nodes
from provisioningserver.rpc.region import ListNodePowerParameters

maaslog = get_maas_logger("power_monitor_service")
log = LegacyLogger()


class NodePowerMonitorService(TimerService):
    """Service to monitor the power status of all nodes in this cluster."""

    check_interval = timedelta(seconds=15).total_seconds()
    max_nodes_at_once = 5

    def __init__(self, clock=None):
        # Call self.query_nodes() every self.check_interval.
        super().__init__(self.check_interval, self.try_query_nodes)
        self.clock = clock

    def try_query_nodes(self):
        """Attempt to query nodes' power states.

        Log errors on failure, but do not propagate them up; that will
        stop the timed loop from running.
        """
        try:
            client = getRegionClient()
        except NoConnectionsAvailable:
            log.debug(
                "Cannot monitor nodes' power status; region not available."
            )
        else:
            d = self.query_nodes(client)
            d.addErrback(self.query_nodes_failed, client.localIdent)
            return d

    @inlineCallbacks
    def query_nodes(self, client):
        # Get the nodes' power parameters from the region. Keep getting more
        # power parameters until the region returns an empty list.
        while True:
            response = yield client(
                ListNodePowerParameters, uuid=client.localIdent
            )
            power_parameters = response["nodes"]
            if len(power_parameters) > 0:
                yield query_all_nodes(
                    power_parameters,
                    max_concurrency=self.max_nodes_at_once,
                    clock=self.clock,
                )
            else:
                break

    def query_nodes_failed(self, failure, localIdent):
        if failure.check(NoSuchCluster):
            maaslog.error(
                "Rack controller '%s' is not recognised.", localIdent
            )
        elif failure.check(ConnectionDone):
            maaslog.error("Lost connection to region controller.")
        else:
            # Log the error in full to the Twisted log.
            log.err(failure, "Querying node power states.")
            # Log something concise to the MAAS log.
            maaslog.error(
                "Failed to query nodes' power status: %s",
                failure.getErrorMessage(),
            )
