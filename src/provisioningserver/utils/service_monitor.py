# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Services monitor ensures services are in their expected state."""

__all__ = [
    "AlwaysOnService",
    "Service",
    "SERVICE_STATE",
    "ServiceActionError",
    "ServiceMonitor",
    "ServiceNotOnError",
    "ServiceParsingError",
    "ServiceUnknownError",
]

from abc import (
    ABCMeta,
    abstractmethod,
    abstractproperty,
)
from collections import (
    defaultdict,
    namedtuple,
)

from provisioningserver.logger.log import get_maas_logger
from provisioningserver.utils.shell import select_c_utf8_bytes_locale
from provisioningserver.utils.twisted import asynchronous
from twisted.internet.defer import (
    DeferredList,
    DeferredLock,
    inlineCallbacks,
    maybeDeferred,
    returnValue,
)
from twisted.internet.utils import getProcessOutputAndValue


maaslog = get_maas_logger("service_monitor")


class SERVICE_STATE:
    """The vocabulary of a service expected state."""
    #: Service is unknown
    UNKNOWN = 'unknown'
    #: Service is on
    ON = 'on'
    #: Service is off
    OFF = 'off'
    #: Service is dead
    DEAD = 'dead'


ServiceStateBase = namedtuple(
    "ServiceStateBase", ["active_state", "process_state"])


class ServiceState(ServiceStateBase):
    """Holds the current state of a service."""

    __slots__ = ()

    def __new__(cls, active_state=None, process_state=None):
        if active_state is None:
            active_state = SERVICE_STATE.UNKNOWN
        return ServiceStateBase.__new__(
            cls, active_state=active_state, process_state=process_state)

    @asynchronous
    @inlineCallbacks
    def get_status_and_status_info_for(self, service):
        """Return the status and status_info for the state of `service`."""
        status = "off"
        status_info = ""
        expected_state, service_status_info = yield maybeDeferred(
            service.get_expected_state)
        if self.active_state == SERVICE_STATE.UNKNOWN:
            status = "unknown"
        elif self.active_state == SERVICE_STATE.ON:
            status = "running"
        elif expected_state == SERVICE_STATE.ON:
            status = "dead"
            if self.active_state == SERVICE_STATE.OFF:
                status_info = "%s is currently stopped." % (
                    service.service_name)
            else:
                status_info = (
                    "%s failed to start, process result: (%s)" % (
                        service.service_name, self.process_state))
        returnValue((
            status,
            service_status_info if service_status_info else status_info))


class Service(metaclass=ABCMeta):
    """Skeleton for a monitored service."""

    @abstractproperty
    def name(self):
        """Nice name of the service."""

    @abstractproperty
    def service_name(self):
        """Name of the service for upstart or systemd."""

    @abstractmethod
    def get_expected_state(self):
        """Returns (expected state, status_info) for the service."""


class AlwaysOnService(Service):
    """Service that should always be on."""

    def get_expected_state(self):
        """AlwaysOnService should always be on."""
        return (SERVICE_STATE.ON, None)


class ServiceUnknownError(Exception):
    """Raised when a check is called for a service the `ServiceMonitor` does
    not know about."""


class ServiceActionError(Exception):
    """Raised when a service has failed to perform an action successfully."""


class ServiceParsingError(Exception):
    """Raised when the `ServiceMonitor` is unable to parse the status of a
    service."""


class ServiceNotOnError(Exception):
    """Raised when a service is not expected to be on, but a restart is
    performed."""


class ServiceMonitor:
    """Monitors all services given services to make sure they
    remain in their expected state. Actions are performed on the services to
    keep the services in their desired state."""

    # Used to convert the systemd state to the `SERVICE_STATE` enum.
    SYSTEMD_TO_STATE = {
        "active": SERVICE_STATE.ON,
        "inactive": SERVICE_STATE.OFF,
        "failed": SERVICE_STATE.DEAD,
    }

    # Used to log when the process state is not expected for the active state.
    SYSTEMD_PROCESS_STATE = {
        SERVICE_STATE.ON: "running",
        SERVICE_STATE.OFF: "dead",
        SERVICE_STATE.DEAD: "Result: exit-code",
    }

    def __init__(self, *services):
        for service in services:
            assert isinstance(service, Service)
        self._services = {
            service.name: service
            for service in services
        }
        self._serviceStates = defaultdict(ServiceState)
        self._serviceLocks = defaultdict(DeferredLock)

    def _getServiceLock(self, name):
        """Return the lock for the named service."""
        return self._serviceLocks[name]

    @asynchronous
    def getServiceByName(self, name):
        """Return service from its name."""
        service = self._services.get(name)
        if service is None:
            raise ServiceUnknownError(
                "Service '%s' is not registered." % name)
        return service

    def _updateServiceState(self, name, active_state, process_state):
        """Update the internally held state of a service."""
        state = ServiceState(active_state, process_state)
        self._serviceStates[name] = state
        return state

    @asynchronous
    @inlineCallbacks
    def getServiceState(self, name, now=False):
        """Get the current service state.

        :param now: True will query systemd before returning the result.
        """
        service = self.getServiceByName(name)
        if now:
            active_state, process_state = yield self._loadServiceState(service)
            state = self._updateServiceState(name, active_state, process_state)
        else:
            state = self._serviceStates[name]
        returnValue(state)

    @asynchronous
    def ensureServices(self):
        """Ensures that services are in their desired state.

        :return: A mapping of service names to their current known state.
        """

        def eb_ensureService(failure, service_name):
            # Only log if it's not the ServiceActionError;
            # ServiceActionError is already logged.
            if failure.check(ServiceActionError) is None:
                maaslog.error(
                    "While monitoring service '%s' an error was "
                    "encountered: %s", service_name, failure.value)
            # Return the current service state.
            return self._serviceStates[service_name]

        def cb_ensureService(state, service_name):
            return service_name, state

        def ensureService(service_name):
            # Wraps self.ensureService in error handling. Returns a Deferred.
            # Errors are logged and consumed; the Deferred always fires with a
            # (service-name, state) tuple.
            d = self.ensureService(service_name)
            d.addErrback(eb_ensureService, service_name)
            d.addCallback(cb_ensureService, service_name)
            return d

        def cb_buildResult(results):
            return dict(result for _, result in results)

        d = DeferredList(map(ensureService, self._services))
        d.addCallback(cb_buildResult)
        return d

    @asynchronous
    def ensureService(self, name):
        """Ensures that a service is in its desired state."""
        service = self.getServiceByName(name)
        return self._ensureService(service)

    @asynchronous
    @inlineCallbacks
    def restartService(self, name):
        """Restart service.

        Service will only be restarted if its expected state is ON.
        `ServiceNotOnError` will be raised if restart is called and the
        services expected state is not ON.
        """
        service = self.getServiceByName(name)
        expected_state, _ = yield maybeDeferred(service.get_expected_state)
        if expected_state != SERVICE_STATE.ON:
            raise ServiceNotOnError(
                "Service '%s' is not expected to be on, unable to restart." % (
                    service.service_name))
        yield self._performServiceAction(service, "restart")

        state = yield self.getServiceState(name, now=True)
        if state.active_state != SERVICE_STATE.ON:
            error_msg = (
                "Service '%s' failed to restart. Its current state "
                "is '%s' and '%s'." % (
                    service.service_name,
                    state.active_state,
                    state.process_state))
            maaslog.error(error_msg)
            raise ServiceActionError(error_msg)
        else:
            maaslog.info(
                "Service '%s' has been restarted. Its current state "
                "is '%s' and '%s'." % (
                    service.service_name,
                    state.active_state,
                    state.process_state))
            returnValue(state)

    @asynchronous
    @inlineCallbacks
    def reloadService(self, name, if_on=False):
        """Reload service.

        Service will only be reloaded if its expected state is ON.
        `ServiceNotOnError` will be raised if reload is called and the
        services expected state is not ON.
        """
        service = self.getServiceByName(name)
        expected_state, _ = yield maybeDeferred(service.get_expected_state)
        if expected_state != SERVICE_STATE.ON:
            if if_on is True:
                return
            raise ServiceNotOnError(
                "Service '%s' is not expected to be on, unable to reload." % (
                    service.service_name))
        state = yield self.ensureService(name)
        if state.active_state != SERVICE_STATE.ON:
            error_msg = (
                "Service '%s' is not running and could not be started to "
                "perfom the reload. Its current state is '%s' and '%s'." % (
                    service.service_name,
                    state.active_state,
                    state.process_state))
            maaslog.error(error_msg)
            raise ServiceActionError(error_msg)
        yield self._performServiceAction(service, "reload")

    @asynchronous
    def _execServiceAction(self, service_name, action):
        """Perform the action with the service command.

        :return: tuple (exit code, std-output, std-error)
        """
        env = select_c_utf8_bytes_locale()
        cmd = "sudo", "--non-interactive", "systemctl", action, service_name

        def decode(result):
            out, err, code = result
            return code, out.decode("utf-8"), err.decode("utf-8")

        d = getProcessOutputAndValue(cmd[0], cmd[1:], env=env)
        return d.addCallback(decode)

    @inlineCallbacks
    def _performServiceAction(self, service, action):
        """Start or stop the service."""
        lock = self._getServiceLock(service.name)
        exit_code, output, error = yield lock.run(
            self._execServiceAction, service.service_name, action)
        if exit_code != 0:
            error_msg = (
                "Service '%s' failed to %s: %s" % (
                    service.service_name, action, error))
            maaslog.error(error_msg)
            raise ServiceActionError(error_msg)

    @inlineCallbacks
    def _loadServiceState(self, service):
        """Return service status from systemd."""
        # Ignore the exit_code because systemd will return 0 for anything
        # other than a active service.
        exit_code, output, error = (
            yield self._execServiceAction(service.service_name, "status"))

        # Parse the output of the command to determine the active status and
        # the current state of the service.
        #
        # output for running service looks like:
        #   tgt.service - LSB: iscsi target daemon
        #    Loaded: loaded (/etc/init.d/tgt)
        #    Active: active (running) since Fri 2015-05-15 15:08:26 UTC; 7s ago
        #    Docs: man:systemd-sysv-generator(8)
        #
        # output for stopped service looks like:
        #   tgt.service - LSB: iscsi target daemon
        #    Loaded: loaded (/etc/init.d/tgt)
        #    Active: inactive (dead)
        #    Docs: man:systemd-sysv-generator(8)
        #
        # output for failed service looks like:
        #   maas-dhcpd.service - MAAS instance of ISC DHCP server for IPv4
        #    Loaded: loaded (/lib/systemd/system/maas-dhcpd.service; enabled;
        # ... vendor preset: enabled)
        #    Active: failed (Result: exit-code) since Wed 2016-01-20 10:35:43
        # ... EST; 26min ago
        #    Docs: man:dhcpd(8)
        #
        # output for unknown service looks like:
        #   missing.service
        #    Loaded: not-found (Reason: No such file or directory)
        #    Active: inactive (dead)
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Loaded"):
                load_status = line.split()[1]
                if load_status != "loaded":
                    raise ServiceUnknownError("'%s' is unknown to systemd." % (
                        service.service_name))
            if line.startswith("Active"):
                active_split = line.split(' ', 2)
                active_state, process_state = (
                    active_split[1], active_split[2].lstrip('(').split(')')[0])
                active_state_enum = self.SYSTEMD_TO_STATE.get(active_state)
                if active_state_enum is None:
                    raise ServiceParsingError(
                        "Unable to parse the active state from systemd for "
                        "service '%s', active state reported as '%s'." % (
                            service.service_name, active_state))
                returnValue((active_state_enum, process_state))
        raise ServiceParsingError(
            "Unable to parse the output from systemd for service '%s'." % (
                service.service_name))

    @inlineCallbacks
    def _ensureService(self, service):
        """Ensure that the service is set to the correct state.

        We only ensure that the service is at its expected state. The
        current init system will control its process state and it should
        reach its expected process state based on the service's current
        active state.
        """
        expected_state, _ = yield maybeDeferred(service.get_expected_state)
        if expected_state == SERVICE_STATE.OFF:
            # Service that should be off can also be dead.
            expected_states = [SERVICE_STATE.OFF, SERVICE_STATE.DEAD]
        else:
            expected_states = [expected_state]

        state = yield self.getServiceState(service.name, now=True)
        if state.active_state in expected_states:
            expected_process_state = (
                self.SYSTEMD_PROCESS_STATE[state.active_state])
            if state.process_state != expected_process_state:
                maaslog.warning(
                    "Service '%s' is %s but not in the expected state of "
                    "'%s', its current state is '%s'.",
                    service.service_name, state.active_state,
                    expected_process_state, state.process_state)
            else:
                maaslog.debug(
                    "Service '%s' is %s and '%s'.",
                    service.service_name,
                    state.active_state, state.process_state)
        else:
            # Service is not at its expected active state. Log the action that
            # will be taken to place the service in its correct state.
            if expected_state == SERVICE_STATE.ON:
                action, log_action = ("start", "started")
            elif expected_state == SERVICE_STATE.OFF:
                action, log_action = ("stop", "stopped")
            maaslog.info(
                "Service '%s' is not %s, it will be %s.",
                service.service_name, expected_state, log_action)

            # Perform the required action to get the service to reach
            # its target state.
            yield self._performServiceAction(service, action)

            # Check that the service has remained at its target state.
            state = yield self.getServiceState(service.name, now=True)
            if state.active_state not in expected_states:
                error_msg = (
                    "Service '%s' failed to %s. Its current state "
                    "is '%s' and '%s'." % (
                        service.service_name, action, state.active_state,
                        state.process_state))
                maaslog.error(error_msg)
                raise ServiceActionError(error_msg)
            else:
                maaslog.info(
                    "Service '%s' has been %s and is '%s'." % (
                        service.service_name, log_action, state.process_state))
        returnValue(state)
