# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Service to periodically check that all the other services that MAAS depends
on stays running."""

from datetime import timedelta

from twisted.application.internet import TimerService
from twisted.internet.defer import inlineCallbacks

from provisioningserver.config import is_dev_environment
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import UpdateServices
from provisioningserver.service_monitor import service_monitor
from provisioningserver.utils.twisted import pause, retries

maaslog = get_maas_logger("service_monitor_service")
log = LegacyLogger()


class ServiceMonitorService(TimerService):
    """Service to monitor external services that the cluster requires."""

    # Services that we don't perform any checks on at the moment and we
    # always considered working as since they run in the same process as rackd.
    # "rackd" should not show in this list as the region controller handles
    # updating the status of "rackd". This is because its status all depends
    # on the connections across the multiple regions.
    ALWAYS_RUNNING_SERVICES = [
        {"name": "tftp", "status": "running", "status_info": ""}
    ]

    check_interval = timedelta(seconds=30).total_seconds()

    def __init__(self, client_service, clock):
        # Call self.monitorServices() every self.check_interval.
        super().__init__(self.check_interval, self.monitorServices)
        self.client_service = client_service
        self.clock = clock

    def monitorServices(self):
        """Monitors all of the external services and makes sure they
        stay running.
        """
        if is_dev_environment():
            log.msg(
                "Skipping check of services; they're not running under "
                "the supervision of systemd."
            )
        else:
            d = self._getConnection()
            d.addCallback(self._ensureServices)
            d.addCallback(self._updateRegion)
            d.addErrback(
                log.err, "Failed to monitor services and update region."
            )
            return d

    @inlineCallbacks
    def _getConnection(self):
        """Get a connection to the region."""
        client = None
        for elapsed, remaining, wait in retries(30, 10, self.clock):  # noqa: B007
            try:
                client = yield self.client_service.getClientNow()
                break
            except NoConnectionsAvailable:
                yield pause(wait, self.clock)
        else:
            maaslog.error(
                "Can't update service statuses, no RPC connection to region."
            )
        return client

    @inlineCallbacks
    def _ensureServices(self, client):
        if client:
            services = yield service_monitor.ensureServices()
            return (client, services)
        return None, None

    @inlineCallbacks
    def _updateRegion(self, result):
        """Update region about services status."""
        client, services = result
        if client:
            services = yield self._buildServices(services)
            yield client(
                UpdateServices, system_id=client.localIdent, services=services
            )

    @inlineCallbacks
    def _buildServices(self, services):
        """Build the list of services to be sent over RPC."""
        msg_services = list(self.ALWAYS_RUNNING_SERVICES)
        for name, state in services.items():
            service = service_monitor.getServiceByName(name)
            status, status_info = yield state.getStatusInfo(service)
            msg_services.append(
                {"name": name, "status": status, "status_info": status_info}
            )
        return msg_services
