# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Services monitored on regiond."""

__all__ = [
    ]

from datetime import timedelta

from maasserver.enum import SERVICE_STATUS
from maasserver.models.config import Config
from maasserver.models.regioncontrollerprocess import RegionControllerProcess
from maasserver.models.service import Service as ServiceModel
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.config import is_dev_environment
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.service_monitor import (
    AlwaysOnService,
    Service,
    ServiceMonitor,
)
from twisted.application.internet import TimerService
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.python import log


maaslog = get_maas_logger("service_monitor_service")


class BIND9Service(AlwaysOnService):
    """Monitored bind9 service."""

    name = "bind9"
    service_name = "bind9"


class ProxyService(Service):
    """Monitored proxy service."""

    name = "proxy"
    service_name = "maas-proxy"

    def get_expected_state(self):

        @transactional
        def db_get_expected_state():
            if (Config.objects.get_config("enable_http_proxy") and
                    Config.objects.get_config("http_proxy")):
                return (SERVICE_STATUS.OFF,
                        "disabled, alternate proxy is configured in settings.")
            else:
                return (SERVICE_STATUS.ON, None)

        return deferToDatabase(db_get_expected_state)


# Global service monitor for regiond.
service_monitor = ServiceMonitor(
    BIND9Service(),
    ProxyService(),
)


class ServiceMonitorService(TimerService, object):
    """Service to monitor external services that the region requires."""

    check_interval = timedelta(minutes=1).total_seconds()

    def __init__(self, advertisingService, clock=reactor):
        # Call self.monitorServices() every self.check_interval.
        super(ServiceMonitorService, self).__init__(
            self.check_interval, self.monitorServices)
        self.clock = clock
        self.advertisingService = advertisingService

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
        processId = yield self.advertisingService.processId.get()
        services = yield self._buildServices(services)
        yield deferToDatabase(self._saveIntoDatabase, processId, services)

    @transactional
    def _saveIntoDatabase(self, processId, services):
        """Save the `services` in the the database for process by `processId`.
        """
        process = RegionControllerProcess.objects.get(id=processId)
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
            status, status_info = yield state.get_status_and_status_info_for(
                service)
            msg_services.append({
                "name": name,
                "status": status,
                "status_info": status_info,
            })
        return msg_services
