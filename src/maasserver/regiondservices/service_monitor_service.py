# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Service that periodically checks that system services are running."""

from datetime import timedelta

from twisted.application.internet import TimerService
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from maasserver.models.node import RegionController
from maasserver.models.service import Service as ServiceModel
from maasserver.service_monitor import service_monitor
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.config import is_dev_environment
from provisioningserver.logger import LegacyLogger

log = LegacyLogger()


class ServiceMonitorService(TimerService):
    """Service to monitor external services that the region requires."""

    check_interval = timedelta(seconds=30).total_seconds()

    def __init__(self, clock=reactor):
        # Call self.monitorServices() every self.check_interval.
        super().__init__(self.check_interval, self.monitorServices)
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
            d = service_monitor.ensureServices()
            d.addCallback(self._updateDatabase)
            d.addErrback(
                log.err, "Failed to monitor services and update database."
            )
            return d

    @inlineCallbacks
    def _updateDatabase(self, services):
        """Update database about services status."""
        services = yield self._buildServices(services)
        yield deferToDatabase(self._saveIntoDatabase, services)

    @transactional
    def _saveIntoDatabase(self, services):
        """Save the `services` in the the database for process by `processId`."""
        region_obj = RegionController.objects.get_running_controller()
        for service in services:
            ServiceModel.objects.update_service_for(
                region_obj,
                service["name"],
                service["status"],
                service["status_info"],
            )

    @inlineCallbacks
    def _buildServices(self, services):
        """Build the list of services so they can be updated into the database."""
        msg_services = []
        for name, state in services.items():
            service = service_monitor.getServiceByName(name)
            status, status_info = yield state.getStatusInfo(service)
            msg_services.append(
                {"name": name, "status": status, "status_info": status_info}
            )
        return msg_services
