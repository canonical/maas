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
from json.decoder import JSONDecodeError
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
from twisted.internet.protocol import ProcessProtocol
from twisted.internet.threads import deferToThread
from twisted.python import log


maaslog = get_maas_logger("networks.monitor")


class JSONPerLineProtocol(ProcessProtocol):
    """ProcessProtocol which allows easy parsing of a single JSON object per
    line of text.
    """

    def __init__(self, callback):
        super().__init__()
        self._callback = callback
        self.done = Deferred()

    def connectionMade(self):
        self._outbuf = b''
        self._errbuf = b''

    def outReceived(self, data):
        lines, self._outbuf = self.splitLines(self._outbuf + data)
        for line in lines:
            self.outLineReceived(line)

    def errReceived(self, data):
        lines, self._errbuf = self.splitLines(self._errbuf + data)
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
        try:
            obj = json.loads(line)
        except JSONDecodeError:
            log.msg("Failed to parse JSON: %r" % line)
        else:
            self.objectReceived(obj)

    def objectReceived(self, obj):
        self._callback([obj])

    def errLineReceived(self, line):
        line = line.decode("utf-8")
        log.msg(line.rstrip())

    def processEnded(self, reason):
        if len(self._errbuf) != 0:
            self.errLineReceived(self._errbuf)
        # If the process finished normally, fire _done with
        # None. Otherwise, pass the reason through.
        if reason.check(ProcessDone):
            self.done.callback(None)
        else:
            self.done.errback(reason)


class NeighbourObservationProtocol(JSONPerLineProtocol):

    def __init__(self, interface, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.interface = interface

    def objectReceived(self, obj):
        # The only difference between the JSONPerLineProtocol and the
        # NeighbourObservationProtocol is that the neighbour observation
        # protocol needs to insert the interface metadata into the resultant
        # object before the callback.
        obj['interface'] = self.interface
        super().objectReceived(obj)


class ProcessProtocolService(TimerService, metaclass=ABCMeta):

    def __init__(self, interval=60.0):
        super().__init__(interval, self.startProcess)
        self._process = self._protocol = None

    @deferred
    def startProcess(self):
        env = select_c_utf8_bytes_locale()
        log.msg("%s started." % self.getDescription())
        args = self.getProcessParameters()
        assert all(isinstance(arg, bytes) for arg in args), (
            "Process arguments must all be bytes, got: %s" % repr(args))
        self._protocol = self.createProcessProtocol()
        self._process = reactor.spawnProcess(
            self._protocol, args[0], args, env=env)
        return self._protocol.done.addBoth(self._processEnded)

    def _processEnded(self, failure):
        if failure is None:
            log.msg("%s ended normally." % self.getDescription())
        else:
            log.err(failure, "%s failed." % self.getDescription())

    @abstractmethod
    def getProcessParameters(self):
        """Return the parameters for the subprocess to launch.

        This MUST be overridden in subclasses.
        """

    @abstractmethod
    def getDescription(self):
        """Return the description of this process, suitable to use in verbose
        logging.

        This MUST be overridden in subclasses.
        """

    @abstractmethod
    def createProcessProtocol(self):
        """
        Creates and returns the ProcessProtocol that will be used to
        communicate with the process.

        This MUST be overridden in subclasses.
        """

    def stopProcess(self):
        try:
            self._process.signalProcess("INT")
        except ProcessExitedAlready:
            pass

    def stopService(self):
        """Stops the neighbour observation service."""
        if self._process is not None:
            self._process.loseConnection()
            # We don't care about the result; we just want to make sure the
            # process is dead.
            # XXX this causes us to log errors such as:
            #     mDNS resolver process failed.
            # reactor.callFromThread(self.stopProcess)
        return super().stopService()


class NeighbourDiscoveryService(ProcessProtocolService):
    """Service to spawn the per-interface device discovery subprocess."""

    def __init__(self, ifname: str, callback: callable):
        self.ifname = ifname
        self.callback = callback
        super().__init__()

    def getDescription(self) -> str:
        return "Neighbour observation process for %s" % self.ifname

    def getProcessParameters(self):
        maas_rack_cmd = get_maas_provision_command().encode("utf-8")
        return [
            maas_rack_cmd,
            b"observe-arp",
            self.ifname.encode("utf-8")
        ]

    def createProcessProtocol(self):
        return NeighbourObservationProtocol(
            self.ifname, callback=self.callback)


class MDNSResolverService(ProcessProtocolService):
    """Service to spawn the per-interface device discovery subprocess."""

    def __init__(self, callback):
        self.callback = callback
        super().__init__()

    def getDescription(self):
        return "mDNS observation process"

    def getProcessParameters(self):
        maas_rack_cmd = get_maas_provision_command().encode("utf-8")
        return [
            maas_rack_cmd,
            b"observe-mdns",
        ]

    def createProcessProtocol(self):
        return JSONPerLineProtocol(callback=self.callback)


class NetworksMonitoringService(MultiService, metaclass=ABCMeta):
    """Service to monitor network interfaces for configuration changes.

    Parse ``/etc/network/interfaces`` and the output from ``ip addr show`` to
    update MAAS's records of network interfaces on this host.

    :param reactor: An `IReactor` instance.
    """

    interval = timedelta(seconds=30).total_seconds()

    # The last successfully recorded interfaces.
    _recorded = None
    _monitored = frozenset()

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

    @abstractmethod
    def reportMDNSEntries(self, mdns):
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
        service = NeighbourDiscoveryService(ifname, self.reportNeighbours)
        service.setName("neighbour_discovery:" + ifname)
        service.setServiceParent(self)

    def _startMDNSDiscoveryService(self):
        """Start resolving mDNS entries on attached networks."""
        try:
            self.getServiceNamed("mdns_resolver")
        except KeyError:
            # This is an expected exception. (The call inside the `try`
            # is only necessary to ensure the service doesn't exist.)
            service = MDNSResolverService(self.reportMDNSEntries)
            service.setName("mdns_resolver")
            service.setServiceParent(self)

    def _stopMDNSDiscoveryService(self):
        """Stop resolving mDNS entries on attached networks."""
        try:
            service = self.getServiceNamed("mdns_resolver")
        except KeyError:
            # Service doesn't exist, so no need to stop it.
            pass
        else:
            service.disownServiceParent()
            maaslog.info("Stopped mDNS resolver service.")

    def _startNeighbourDiscoveryServices(self, new_interfaces):
        """Start monitoring services for the specified set of interfaces."""
        for ifname in new_interfaces:
            # Sanity check to ensure the service isn't already started.
            try:
                self.getServiceNamed("neighbour_discovery:" + ifname)
            except KeyError:
                # This is an expected exception. (The call inside the `try`
                # is only necessary to ensure the service doesn't exist.)
                self._startNeighbourDiscovery(ifname)

    def _stopNeighbourDiscoveryServices(self, deleted_interfaces):
        """Stop monitoring services for the specified set of interfaces."""
        for ifname in deleted_interfaces:
            try:
                service = self.getServiceNamed("neighbour_discovery:" + ifname)
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
        # Determine if we went from monitoring zero interfaces to monitoring
        # at least one. If so, we need to start mDNS discovery.
        # XXX Need to get this setting from the region.
        if len(self._monitored) == 0 and len(monitored_interfaces) > 0:
            # We weren't currently monitoring any interfaces, but we have been
            # requested to monitor at least one.
            self._startMDNSDiscoveryService()
        elif len(self._monitored) > 0 and len(monitored_interfaces) == 0:
            # We are currently monitoring at least one interface, but we have
            # been requested to stop monitoring them all.
            self._stopMDNSDiscoveryService()
        else:
            # No state change. We either still AREN'T monitoring any
            # interfaces, or we still ARE monitoring them. (Either way, it
            # doesn't matter for mDNS discovery purposes.)
            pass
        self._monitored = monitored_interfaces

    def _interfacesRecorded(self, interfaces):
        """The given `interfaces` were recorded successfully."""
        self._recorded = interfaces
        self._updateMonitoredInterfaces(interfaces)
