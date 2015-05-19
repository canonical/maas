# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Service to periodically check that all the other services that MAAS depends
on stays running."""


from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "ServiceMonitorService"
]

from datetime import timedelta

from provisioningserver.service_monitor import service_monitor
from twisted.application.internet import TimerService
from twisted.internet.threads import deferToThread
from twisted.python import log


class ServiceMonitorService(TimerService, object):
    """Service to monitor external services that the cluster requires."""

    check_interval = timedelta(minutes=2).total_seconds()

    def __init__(self, clock=None):
        # Call self.monitor_services() every self.check_interval.
        super(ServiceMonitorService, self).__init__(
            self.check_interval, self.monitor_services)
        self.clock = clock

    def monitor_services(self):
        """Monitors all of the external services and makes sure they
        stay running.
        """
        d = deferToThread(service_monitor.ensure_all_services)
        d.addErrback(log.err, "Failed to monitor services.")
        return d
