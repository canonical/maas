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
import re

from provisioningserver.config import is_dev_environment
from provisioningserver.logger import (
    get_maas_logger,
    LegacyLogger,
)
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.utils.fs import (
    get_maas_provision_command,
    NamedLock,
)
from provisioningserver.utils.network import get_all_interfaces_definition
from provisioningserver.utils.shell import select_c_utf8_bytes_locale
from provisioningserver.utils.twisted import (
    callOut,
    deferred,
    suppress,
    terminateProcess,
)
from twisted.application.internet import TimerService
from twisted.application.service import MultiService
from twisted.internet import reactor
from twisted.internet.defer import (
    Deferred,
    inlineCallbacks,
    maybeDeferred,
)
from twisted.internet.error import (
    ProcessDone,
    ProcessTerminated,
)
from twisted.internet.protocol import ProcessProtocol
from twisted.internet.threads import deferToThread


maaslog = get_maas_logger("networks.monitor")
log = LegacyLogger()


class JSONPerLineProtocol(ProcessProtocol):
    """ProcessProtocol which parses a single JSON object per line of text.

    This expects that a UTF-8 locale is used, i.e. that text written to stdout
    and stderr by the spawned process uses the UTF-8 character set.
    """

    def __init__(self, callback):
        super().__init__()
        self._callback = callback
        self.done = Deferred()

    def connectionMade(self):
        super().connectionMade()
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


class ProtocolForObserveARP(JSONPerLineProtocol):
    """Protocol used when spawning `maas-rack observe-arp`.

    The difference between `JSONPerLineProtocol` and `ProtocolForObserveARP`
    is that the neighbour observation protocol needs to insert the interface
    metadata into the resultant object before the callback.

    This also ensures that the spawned process is configured as a process
    group leader for its own process group.
    """

    def __init__(self, interface, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.interface = interface

    def objectReceived(self, obj):
        obj['interface'] = self.interface
        super().objectReceived(obj)

    def errLineReceived(self, line):
        line = line.decode("utf-8").rstrip()
        log.msg("observe-arp[%s]:" % self.interface, line)


class ProtocolForObserveMDNS(JSONPerLineProtocol):
    """Protocol used when spawning `maas-rack observe-mdns`.

    This ensures that the spawned process is configured as a process group
    leader for its own process group.

    The spawned process is assumed to be `avahi-browse` which prints a
    somewhat inane "Got SIG***, quitting" message when signalled. We do want
    to see if it has something useful to say so we filter out lines from
    stderr matching this pattern. Other lines are logged with the prefix
    "observe-mdns".
    """

    _re_ignore_stderr = re.compile(
        "^Got SIG[A-Z]+, quitting[.]")

    def errLineReceived(self, line):
        line = line.decode("utf-8").rstrip()
        if self._re_ignore_stderr.match(line) is None:
            log.msg("observe-mdns:", line)


class ProcessProtocolService(TimerService, metaclass=ABCMeta):

    def __init__(self, interval=60.0):
        super().__init__(interval, self.startProcess)
        self._process = self._protocol = None
        self._stopping = False

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
        elif failure.check(ProcessTerminated) and self._stopping:
            log.msg("%s was terminated." % self.getDescription())
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

    def startService(self):
        """Starts the neighbour observation service."""
        self._stopping = False
        return super().startService()

    def stopService(self):
        """Stops the neighbour observation service."""
        self._stopping = True
        if self._process is not None and self._process.pid is not None:
            terminateProcess(self._process.pid, self._protocol.done)
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
        return ProtocolForObserveARP(
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
        return ProtocolForObserveMDNS(callback=self.callback)


class NetworksMonitoringLock(NamedLock):
    """Host scoped lock to ensure only one network monitoring service runs."""

    def __init__(self):
        super().__init__("networks-monitoring")


class NetworksMonitoringService(MultiService, metaclass=ABCMeta):
    """Service to monitor network interfaces for configuration changes.

    Parse ``/etc/network/interfaces`` and the output from ``ip addr show`` to
    update MAAS's records of network interfaces on this host.

    :param reactor: An `IReactor` instance.
    """

    interval = timedelta(seconds=30).total_seconds()

    def __init__(self, clock=None, enable_monitoring=True):
        # Order is very important here. First we set the clock to the passed-in
        # reactor, so that unit tests can fake out the clock if necessary.
        # Then we call super(). The superclass will set up the structures
        # required to add parents to this service, which allows the remainder
        # of this method to succeed. (And do so without the side-effect of
        # executing calls that shouldn't be executed based on the desired
        # reactor.)
        self.clock = clock
        super().__init__()
        self.enable_monitoring = enable_monitoring
        # The last successfully recorded interfaces.
        self._recorded = None
        self._monitored = frozenset()
        self._monitoring_state = {}
        self._monitoring_mdns = False
        self._locked = False
        # Use a named filesystem lock to prevent more than one monitoring
        # service running on each host machine. This service attempts to
        # acquire this lock on each loop, and then it holds the lock until the
        # service stops.
        self._lock = NetworksMonitoringLock()
        # Set up child service to update interface.
        self.interface_monitor = TimerService(
            self.interval, self.updateInterfaces)
        self.interface_monitor.setName("updateInterfaces")
        self.interface_monitor.clock = self.clock
        self.interface_monitor.setServiceParent(self)

    def updateInterfaces(self):
        """Update interfaces, catching and logging errors.

        This can be overridden by subclasses to conditionally update based on
        some external configuration.
        """
        d = maybeDeferred(self._assumeSoleResponsibility)

        def update(responsible):
            if responsible:
                d = maybeDeferred(self.getInterfaces)
                d.addCallback(self._updateInterfaces)
                return d

        def failed(failure):
            log.err(
                failure,
                "Failed to update and/or record network interface "
                "configuration: %s" % failure.getErrorMessage())

        d = d.addCallback(update)
        # During the update, we might fail to get the interface monitoring
        # state from the region. We can safely ignore this, as it will be
        # retried shortly.
        d.addErrback(suppress, NoConnectionsAvailable)
        d.addErrback(failed)
        return d

    def getInterfaces(self):
        """Get the current network interfaces configuration.

        This can be overridden by subclasses.
        """
        return deferToThread(get_all_interfaces_definition)

    @abstractmethod
    def getDiscoveryState(self):
        """Record the interfaces information.

        This MUST be overridden in subclasses.
        """

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
            self._configureNetworkDiscovery({})

    def _updateInterfaces(self, interfaces):
        """Record `interfaces` if they've changed."""
        if interfaces != self._recorded:
            d = maybeDeferred(self.recordInterfaces, interfaces)
            # Note: _interfacesRecorded() will reconfigure discovery after
            # recording the interfaces, so there is no need to call
            # _configureNetworkDiscovery() here.
            d.addCallback(callOut, self._interfacesRecorded, interfaces)
            return d
        else:
            # If the interfaces didn't change, we still need to poll for
            # monitoring state changes.
            d = maybeDeferred(self._configureNetworkDiscovery, interfaces)
            return d

    def _getInterfacesForNeighbourDiscovery(
            self, interfaces: dict, monitoring_state: dict):
        """Return the interfaces which will be used for neighbour discovery.

        :return: The set of interface names to run neighbour discovery on.
        """
        # Don't observe interfaces when running the test suite/dev env.
        # In addition, if we don't own the lock, we should not be monitoring
        # any interfaces.
        if is_dev_environment() or not self._locked or interfaces is None:
            return set()
        monitored_interfaces = {
            ifname for ifname in interfaces
            if (ifname in monitoring_state and
                monitoring_state[ifname].get('neighbour', False) is True)
        }
        return monitored_interfaces

    def _startNeighbourDiscovery(self, ifname):
        """"Start neighbour discovery service on the specified interface."""
        service = NeighbourDiscoveryService(ifname, self.reportNeighbours)
        service.clock = self.clock
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
            service.clock = self.clock
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
                    "Stopped neighbour observation service for %s." % ifname)

    def _shouldMonitorMDNS(self, monitoring_state):
        # If any interface is configured for mDNS, we must start the monitoring
        # process. (You cannot select interfaces when using `avahi-browse`.)
        mdns_state = {
            monitoring_state[ifname].get('mdns', False)
            for ifname in monitoring_state.keys()
        }
        return True in mdns_state

    @inlineCallbacks
    def _configureNetworkDiscovery(self, interfaces):
        """Update the set of monitored interfaces.

        Calculates the difference between the interfaces that are currently
        being monitored and the new list of interfaces enabled for discovery.

        Starts services for any new interfaces, and stops services for any
        deleted interface.

        Updates `self._monitored` with the current set of interfaces being
        monitored.
        """
        if interfaces is None:
            # This is a no-op if we don't have any interfaces to monitor yet.
            # (An empty dictionary tells us not to monitor any interfaces.)
            return
        # Don't bother calling the region if the interface dictionary
        # hasn't yet been populated, or was intentionally set to nothing.
        if len(interfaces) > 0:
            monitoring_state = yield maybeDeferred(
                self.getDiscoveryState)
        else:
            monitoring_state = {}
        # If the monitoring state has changed, we need to potentially start
        # or stop some services.
        if self._monitoring_state != monitoring_state:
            log.msg("New interface monitoring state: %r" % monitoring_state)
            self._configureNeighbourDiscovery(interfaces, monitoring_state)
            self._configureMDNS(monitoring_state)
            self._monitoring_state = monitoring_state

    def _configureMDNS(self, monitoring_state):
        should_monitor_mdns = self._shouldMonitorMDNS(monitoring_state)
        if not self._monitoring_mdns and should_monitor_mdns:
            # We weren't currently monitoring any interfaces, but we have been
            # requested to monitor at least one.
            self._startMDNSDiscoveryService()
            self._monitoring_mdns = True
        elif self._monitoring_mdns and not should_monitor_mdns:
            # We are currently monitoring at least one interface, but we have
            # been requested to stop monitoring them all.
            self._stopMDNSDiscoveryService()
            self._monitoring_mdns = False
        else:
            # No state change. We either still AREN'T monitoring any
            # interfaces, or we still ARE monitoring them. (Either way, it
            # doesn't matter for mDNS discovery purposes.)
            pass

    def _configureNeighbourDiscovery(self, interfaces, monitoring_state):
        monitored_interfaces = self._getInterfacesForNeighbourDiscovery(
            interfaces, monitoring_state)
        # Calculate the difference between the sets. We need to know which
        # interfaces were added and deleted (with respect to the interfaces we
        # were already monitoring).
        new_interfaces = monitored_interfaces.difference(self._monitored)
        deleted_interfaces = self._monitored.difference(monitored_interfaces)
        if len(new_interfaces) > 0:
            log.msg("Starting neighbour discovery for interfaces: %r" % (
                new_interfaces))
            self._startNeighbourDiscoveryServices(new_interfaces)
        if len(deleted_interfaces) > 0:
            log.msg(
                "Stopping neighbour discovery for interfaces: %r" % (
                    deleted_interfaces))
            self._stopNeighbourDiscoveryServices(deleted_interfaces)
        self._monitored = monitored_interfaces

    def _interfacesRecorded(self, interfaces):
        """The given `interfaces` were recorded successfully."""
        self._recorded = interfaces
        if self.enable_monitoring is True:
            self._configureNetworkDiscovery(interfaces)
