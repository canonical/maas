# Copyright 2014 Canonical Ltd.  This software is licensed under the
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


from provisioningserver.logger.log import get_maas_logger
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.power import query_all_nodes
from provisioningserver.rpc.region import ListNodePowerParameters
from provisioningserver.utils.twisted import pause
from twisted.application.internet import TimerService
from twisted.internet.defer import inlineCallbacks


maaslog = get_maas_logger("power_monitor_service")


class NodePowerMonitorService(TimerService, object):
    """Twisted service to monitor the status of all nodes
    controlled by this cluster.

    :param client_service: A `ClusterClientService` instance for talking
        to the region controller.
    :param reactor: An `IReactor` instance.
    """

    # XXX 2014-08-27 bug=1361967
    # This service is COMPLETELY UNTESTED.

    check_interval = 600  # 5 minutes.

    def __init__(self, client_service, reactor, cluster_uuid):
        # Call self.check() every self.check_interval.
        super(NodePowerMonitorService, self).__init__(
            self.check_interval, self.query_nodes)
        self.clock = reactor
        self.client_service = client_service
        self.uuid = cluster_uuid

    @inlineCallbacks
    def query_nodes(self):
        client = None
        # Retry a few times, since this service usually comes up before
        # the RPC service.
        for _ in range(3):
            try:
                client = self.client_service.getClient()
                break
            except NoConnectionsAvailable:
                yield pause(5)
        if client is None:
            maaslog.error(
                "Can't query nodes's BMC for power state, no RPC connection "
                "to region.")
            return

        # Get the nodes from the Region
        response = yield client(ListNodePowerParameters, uuid=self.uuid)
        nodes = response['nodes']
        yield query_all_nodes(nodes)
