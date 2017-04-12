# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Service that periodically checks that system services are running."""

__all__ = [
    "ServiceMonitorService"
]

from datetime import timedelta

from maasserver.models.service import Service as ServiceModel
from maasserver.service_monitor import service_monitor
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.config import is_dev_environment
from provisioningserver.logger import LegacyLogger
from twisted.application.internet import TimerService
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks


log = LegacyLogger()


class ServiceMonitorService(TimerService, object):
    """Service to monitor external services that the region requires."""

    check_interval = timedelta(minutes=1).total_seconds()

    def __init__(self, advertisingService, clock=reactor):
        # Call self.monitorServices() every self.check_interval.
        super(ServiceMonitorService, self).__init__(
            self.check_interval, self.monitorServices)
        self.advertisingService = advertisingService
        self.clock = clock

    def monitorServices(self):
        """Monitors all of the external services and makes sure they
        stay running.
        """
        if is_dev_environment():
            log.msg(
                "Skipping check of services; they're not running under "
                "the supervision of systemd.")
        else:
            d = service_monitor.ensureServices()
            d.addCallback(self._updateDatabase)
            d.addErrback(
                log.err, "Failed to monitor services and update database.")
            return d

    @inlineCallbacks
    def _updateDatabase(self, services):
        """Update database about services status."""
        advertising = yield self.advertisingService.advertising.get()
        services = yield self._buildServices(services)
        process = yield deferToDatabase(advertising.getRegionProcess)
        yield deferToDatabase(
            self._saveIntoDatabase, process, services)

    @transactional
    def _saveIntoDatabase(self, process, services):
        """Save the `services` in the the database for process by `processId`.
        """
        for service in services:
            ServiceModel.objects.update_service_for(
                process.region, service["name"],
                service["status"], service["status_info"])

    @inlineCallbacks
    def _buildServices(self, services):
        """Build the list of services so they can be updated into the database.
        """
        msg_services = []
        for name, state in services.items():
            service = service_monitor.getServiceByName(name)
            status, status_info = yield state.getStatusInfo(service)
            msg_services.append({
                "name": name,
                "status": status,
                "status_info": status_info,
            })
        return msg_services
