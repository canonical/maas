# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Networks monitoring service."""

__all__ = [
    "NetworksMonitoringService",
]

from abc import (
    ABCMeta,
    abstractmethod,
)
from datetime import timedelta

from provisioningserver.logger.log import get_maas_logger
from provisioningserver.utils.network import get_all_interfaces_definition
from provisioningserver.utils.twisted import callOut
from twisted.application.internet import TimerService
from twisted.internet.defer import maybeDeferred
from twisted.internet.threads import deferToThread


maaslog = get_maas_logger("networks.monitor")


class NetworksMonitoringService(TimerService, metaclass=ABCMeta):
    """Service to monitor network interfaces for configuration changes.

    Parse ``/etc/network/interfaces`` and the output from ``ip addr show`` to
    update MAAS's records of network interfaces on this host.

    :param reactor: An `IReactor` instance.
    """

    interval = timedelta(seconds=30).total_seconds()

    def __init__(self, reactor):
        super().__init__(self.interval, self.updateInterfaces)
        self.clock = reactor
        self._recorded = None

    def updateInterfaces(self):
        """Update interfaces, catching and logging errors.

        This can be overridden by subclasses to conditionally update based on
        some external configuration.
        """
        d = self.getInterfaces()
        d.addCallback(self._maybeRecordInterfaces)
        d.addErrback(lambda failure: maaslog.error(
            "Failed to update and/or record network interface "
            "configuration: %s", failure.getErrorMessage()))
        return d

    def getInterfaces(self):
        """Get the current network interfaces configuration.

        This can be overridden by subclasses.
        """
        return deferToThread(get_all_interfaces_definition)

    @abstractmethod
    def recordInterfaces(self, interfaces):
        """Record the interfaces information.

        This MUST be overridden in subclasses.
        """

    def _maybeRecordInterfaces(self, interfaces):
        """Record `interfaces` if they've changed."""
        if interfaces != self._recorded:
            d = maybeDeferred(self.recordInterfaces, interfaces)
            d.addCallback(callOut, self._interfacesRecorded, interfaces)
            return d

    def _interfacesRecorded(self, interfaces):
        """The given `interfaces` were recorded successfully."""
        self._recorded = interfaces
