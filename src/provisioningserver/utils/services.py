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
import json
import os

from provisioningserver.config import is_dev_environment
from provisioningserver.logger.log import get_maas_logger
from provisioningserver.utils.fs import (
    get_maas_provision_command,
    NamedLock,
)
from provisioningserver.utils.network import get_all_interfaces_definition
from provisioningserver.utils.shell import select_c_utf8_bytes_locale
from provisioningserver.utils.twisted import (
    callOut,
    deferred,
)
from twisted.application.internet import TimerService
from twisted.application.service import MultiService
from twisted.internet import reactor
from twisted.internet.defer import (
    Deferred,
    maybeDeferred,
)
from twisted.internet.error import (
    ProcessDone,
    ProcessExitedAlready,
)
from twisted.internet.interfaces import ILoggingContext
from twisted.internet.protocol import ProcessProtocol
from twisted.internet.threads import deferToThread
from twisted.python import log
from zope.interface import implementer


maaslog = get_maas_logger("networks.monitor")


@implementer(ILoggingContext)
class NeighbourObservationProtocol(ProcessProtocol):

    def __init__(self, interface, prefix=None, callback=None):
        super().__init__()
        self.done = Deferred()
        self.interface = interface
        self.prefix = prefix
        self.callback = callback
        self.outbuf = b''
        self.errbuf = b''

    def logPrefix(self):
        return "-" if self.prefix is None else self.prefix

    def connectionMade(self):
        self.outbuf = b''
        self.errbuf = b''

    def outReceived(self, data):
        lines, self.outbuf = self.splitLines(self.outbuf + data)
        for line in lines:
            self.outLineReceived(line)

    def errReceived(self, data):
        lines, self.errbuf = self.splitLines(self.errbuf + data)
        for line in lines:
            self.errLineReceived(line)

    @staticmethod
    def splitLines(data):
        lines = data.splitlines(True)
        if len(lines) == 0:
            # Nothing to do.
            remaining = b''
        elif lines[-1].endswith(b'\n'):
            # All lines are complete.
            remaining = b''
        else:
            # The last line is incomplete.
            remaining = lines.pop()
        return lines, remaining

    def outLineReceived(self, line):
        line = line.decode("utf-8")
        obj = json.loads(line)
        obj['interface'] = self.interface
        # Report one observation at a time for now. (The API is designed to
        # support multiple, but that will be done in a future branch.)
        self.callback([obj])

    def errLineReceived(self, line):
        line = line.decode("utf-8")
        log.msg(line.rstrip())

    def processEnded(self, reason):
        if len(self.errbuf) != 0:
            self.errLineReceived(self.errbuf)
        if reason.check(ProcessDone):
            self.done.callback(None)
        else:
            self.done.errback(reason)


class NeighbourDiscoveryService(TimerService):
    """Service to spawn the per-interface device discovery subprocess."""

    def __init__(self, ifname):
        super().__init__(60.0, self.observeInterface, ifname)
        self._ifname = ifname
        self._process = None

    @deferred
    def observeInterface(self, ifname):
        """Start a network observation process for the specified interface."""
        observer_protocol = NeighbourObservationProtocol(
            ifname, callback=self.parent.reportNeighbours)
        env = select_c_utf8_bytes_locale()
        maas_rack_cmd = get_maas_provision_command().encode("utf-8")
        self._process = reactor.spawnProcess(
            observer_protocol, maas_rack_cmd,
            [maas_rack_cmd, b"observe-arp", ifname.encode("utf-8")],
            env=env)
        log.msg("Started neighbour observation on interface: %s" % ifname)
        return observer_protocol.done.addErrback(
            log.err,
            "Neighbour observation process failed for interface: %s" % (
                self._ifname
            ))

    def stopObservationProcess(self):
        """Attempts to kill the neighbour observation process gracefully."""
        if self._process is not None:
            try:
                self._process.signalProcess("INT")
            except ProcessExitedAlready:
                pass  # Our work here is done.
            except OSError:
                log.err(
                    None,
                    "Neighbour observation process for %s failed to "
                    "shut down." % self._ifname)
            else:
                return self._process.done

    def stopService(self):
        """Stops the neighbour observation service."""
        d = super().stopService()
        d.addCallback(callOut, self.stopObservationProcess)
        return d


class NetworksMonitoringService(MultiService, metaclass=ABCMeta):
    """Service to monitor network interfaces for configuration changes.

    Parse ``/etc/network/interfaces`` and the output from ``ip addr show`` to
    update MAAS's records of network interfaces on this host.

    :param reactor: An `IReactor` instance.
    """

    interval = timedelta(seconds=30).total_seconds()

    # The last successfully recorded interfaces.
    _recorded = None
    _monitored = set()

    # Use a named filesystem lock to prevent more than one monitoring service
    # running on each host machine. This service attempts to acquire this lock
    # on each loop, and then it holds the lock until the service stops.
    _lock = NamedLock("networks-monitoring")
    _locked = False

    def __init__(self, reactor):
        super().__init__()
        self.interface_monitor = TimerService(
            self.interval, self.updateInterfaces)
        self.interface_monitor.setServiceParent(self)
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
            log.err(
                failure,
                "Failed to update and/or record network interface "
                "configuration: %s" % failure.getErrorMessage())

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

    @abstractmethod
    def reportNeighbours(self, neighbours):
        """Report on new or refreshed neighbours.

        This MUST be overridden in subclasses.
        """

    def stopService(self):
        """Stop the service.

        Ensures that sole responsibility for monitoring networks is released.
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
                maaslog.info(
                    "Networks monitoring service: Process ID %d assumed "
                    "responsibility." % os.getpid())
                self._locked = True
                self._updateMonitoredInterfaces(self._recorded)
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
            # If we were monitoring neighbours on any interfaces, we need to
            # stop the monitoring services.
            self._updateMonitoredInterfaces()

    def _maybeRecordInterfaces(self, interfaces):
        """Record `interfaces` if they've changed."""
        if interfaces != self._recorded:
            d = maybeDeferred(self.recordInterfaces, interfaces)
            d.addCallback(callOut, self._interfacesRecorded, interfaces)
            return d

    def _getInterfacesForNeighbourDiscovery(self, interfaces):
        """Return the interfaces which will be used for neighbour discovery.

        :return: The set of interface names to run neighbour discovery on.
        """
        # XXX Don't observe interfaces when running the test suite/dev env.
        # This will be fixed in a future branch. We need an RPC call to
        # determine the interfaces to run discovery on.
        # In addition, if we don't own the lock, we should not be monitoring
        # the interfaces any longer.
        if is_dev_environment() or not self._locked or interfaces is None:
            return set()
        # XXX Need to get this from the region instead. This is just a
        # temporary measure to get things working. (Currently, if we had called
        # the region, it would have returned the same result anyway.)
        monitored_interfaces = {
            ifname for ifname in interfaces
            if interfaces[ifname]['monitored'] is True
        }
        return monitored_interfaces

    def _startNeighbourDiscovery(self, ifname):
        """"Start neighbour discovery service on the specified interface."""
        service = NeighbourDiscoveryService(ifname)
        service.setName("neighbour_discovery:" + ifname)
        service.setServiceParent(self)

    def _startNeighbourDiscoveryServices(self, new_interfaces):
        """Start monitoring services for the specified set of interfaces."""
        for ifname in new_interfaces:
            # Sanity check to ensure the service isn't already started.
            try:
                self.getServiceNamed("neighbour_disovery:" + ifname)
            except KeyError:
                # This is an expected exception. (The call inside the `try`
                # is only necessary to ensure the service doesn't exist.
                self._startNeighbourDiscovery(ifname)

    def _stopNeighbourDiscoveryServices(self, deleted_interfaces):
        """Stop monitoring services for the specified set of interfaces."""
        for ifname in deleted_interfaces:
            try:
                service = self.getServiceNamed("neighbour_disovery:" + ifname)
            except KeyError:
                # Service doesn't exist, so no need to stop it.
                pass
            else:
                service.disownServiceParent()
                maaslog.info(
                    "Stopped neighbour observation on interface: %s" % ifname)

    def _updateMonitoredInterfaces(self, interfaces=None):
        """Update the set of monitored interfaces.

        Calculates the difference between the interfaces that are currently
        being monitored and the new list of interfaces enabled for discovery.

        Starts services for any new interfaces, and stops services for any
        deleted interface.

        Updates `self._monitored` with the current set of interfaces being
        monitored.
        """
        monitored_interfaces = self._getInterfacesForNeighbourDiscovery(
            interfaces)
        # Calculate the difference between the sets. We need to know which
        # interfaces were added and deleted (with respect to the interfaces we
        # were already monitoring).
        new_interfaces = monitored_interfaces.difference(self._monitored)
        deleted_interfaces = self._monitored.difference(monitored_interfaces)
        self._startNeighbourDiscoveryServices(new_interfaces)
        self._stopNeighbourDiscoveryServices(deleted_interfaces)
        self._monitored = monitored_interfaces

    def _interfacesRecorded(self, interfaces):
        """The given `interfaces` were recorded successfully."""
        self._recorded = interfaces
        self._updateMonitoredInterfaces(interfaces)
