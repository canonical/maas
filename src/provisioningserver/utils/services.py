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
from provisioningserver.utils.fs import NamedLock
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

    # The last successfully recorded interfaces.
    _recorded = None

    # Use a named filesystem lock to prevent more than one monitoring service
    # running on each host machine. This service attempts to acquire this lock
    # on each loop, and then it holds the lock until the service stops.
    _lock = NamedLock("networks-monitoring")
    _locked = False

    def __init__(self, reactor):
        super().__init__(self.interval, self.updateInterfaces)
        self.clock = reactor

    def updateInterfaces(self):
        """Update interfaces, catching and logging errors.

        This can be overridden by subclasses to conditionally update based on
        some external configuration.
        """
        d = maybeDeferred(self._assumeSoleResponsibility)

        def update(responsible):
            if responsible:
                d = maybeDeferred(self.getInterfaces)
                d.addCallback(self._maybeRecordInterfaces)
                return d

        def failed(failure):
            maaslog.error(
                "Failed to update and/or record network interface "
                "configuration: %s", failure.getErrorMessage())

        return d.addCallback(update).addErrback(failed)

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

    def stopService(self):
        """Stop the service.

        Ensures that sole responsiblility for monitoring networks is released.
        """
        d = super().stopService()
        d.addBoth(callOut, self._releaseSoleResponsibility)
        return d

    def _assumeSoleResponsibility(self):
        """Assuming sole responsibility for monitoring networks.

        It does this by attempting to acquire a host-wide lock. If this
        service already holds the lock this is a no-op.

        :return: True if we have responsibility, False otherwise.
        """
        if self._locked:
            return True
        else:
            try:
                self._lock.acquire()
            except self._lock.NotAvailable:
                return False
            else:
                self._locked = True
                return True

    def _releaseSoleResponsibility(self):
        """Releases sole responsibility for monitoring networks.

        Another network monitoring service on this host may then take up
        responsibility. If this service is not currently responsible this is a
        no-op.
        """
        if self._locked:
            self._lock.release()
            self._locked = False

    def _maybeRecordInterfaces(self, interfaces):
        """Record `interfaces` if they've changed."""
        if interfaces != self._recorded:
            d = maybeDeferred(self.recordInterfaces, interfaces)
            d.addCallback(callOut, self._interfacesRecorded, interfaces)
            return d

    def _interfacesRecorded(self, interfaces):
        """The given `interfaces` were recorded successfully."""
        self._recorded = interfaces
