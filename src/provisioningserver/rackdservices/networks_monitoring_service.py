# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Networks monitoring service for rack controllers."""

from twisted.internet.defer import inlineCallbacks, returnValue

from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import (
    GetDiscoveryState,
    ReportMDNSEntries,
    ReportNeighbours,
    RequestRackRefresh,
)
from provisioningserver.utils.services import NetworksMonitoringService
from provisioningserver.utils.twisted import pause

maaslog = get_maas_logger("networks.monitor")


class RackNetworksMonitoringService(NetworksMonitoringService):
    """Rack service to monitor network interfaces for configuration changes."""

    def __init__(self, clientService, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.clientService = clientService

    def getDiscoveryState(self):
        """Get the discovery state from the region."""
        if self._recorded is None:
            # Wait until the rack has refreshed.
            return {}
        else:

            def getState(client):
                d = client(GetDiscoveryState, system_id=client.localIdent)
                d.addCallback(lambda args: args["interfaces"])
                return d

            d = self.clientService.getClientNow()
            d.addCallback(getState)
            return d

    @inlineCallbacks
    def getRefreshDetails(self):
        client = yield self._getRPCClient()
        if client is None:
            returnValue((None, None, None))
            return
        credentials = yield client(
            RequestRackRefresh,
            system_id=client.localIdent,
        )
        returnValue(
            (self.clientService.maas_url, client.localIdent, credentials)
        )

    def reportNeighbours(self, neighbours):
        """Report neighbour information to the region."""
        d = self.clientService.getClientNow()
        d.addCallback(
            lambda client: client(
                ReportNeighbours,
                system_id=client.localIdent,
                neighbours=neighbours,
            )
        )
        return d

    def reportMDNSEntries(self, mdns):
        """Report mDNS entries to the region."""
        d = self.clientService.getClientNow()
        d.addCallback(
            lambda client: client(
                ReportMDNSEntries, system_id=client.localIdent, mdns=mdns
            )
        )
        return d

    @inlineCallbacks
    def _getRPCClient(self):
        while self.running:
            try:
                client = yield self.clientService.getClientNow()
            except NoConnectionsAvailable:
                yield pause(1.0)
                continue
            else:
                returnValue(client)
