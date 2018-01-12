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
import enum
import os

from provisioningserver.logger import get_maas_logger
from provisioningserver.utils import (
    snappy,
    typed,
)
from provisioningserver.utils.shell import get_env_with_bytes_locale
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


@enum.unique
class SERVICE_STATE(enum.Enum):
    """The vocabulary of a service state."""

    #: Service is on
    ON = 'on'

    #: Service is off
    OFF = 'off'

    #: Service is dead
    DEAD = 'dead'

    #: Service is unknown. This is only relevant as an observed state, not as
    # an expected state.
    UNKNOWN = 'unknown'

    #: Don't care about the service state. This is only relevant as an
    # expected state, not as an observed state.
    ANY = 'any'


def _check_service_state_observed(state):
    if state not in {
            SERVICE_STATE.ON, SERVICE_STATE.OFF, SERVICE_STATE.DEAD,
            SERVICE_STATE.UNKNOWN}:
        raise AssertionError("Observed state should not be %r." % (state,))


def _check_service_state_expected(state):
    if state not in {
            SERVICE_STATE.ON, SERVICE_STATE.OFF, SERVICE_STATE.DEAD,
            SERVICE_STATE.ANY}:
        raise AssertionError("Expected state should not be %r." % (state,))


ServiceStateBase = namedtuple(
    "ServiceStateBase", ["active_state", "process_state"])


class ServiceState(ServiceStateBase):
    """Holds the current state of a service."""

    __slots__ = ()

    @typed
    def __new__(cls, active_state: SERVICE_STATE=None, process_state=None):
        if active_state is None:
            active_state = SERVICE_STATE.UNKNOWN
        _check_service_state_observed(active_state)
        return ServiceStateBase.__new__(
            cls, active_state=active_state, process_state=process_state)

    @asynchronous
    def getStatusInfo(self, service):
        """Return human-readable strings describing the service's status.

        :return: A 2-tuple. The first element is a string describing the
            status of the service, one of "off", "unknown", "running" or
            "dead". This is NOT directly comparable with the `SERVICE_STATE`
            enum. The second element is a human-readable description of the
            status.
        """
        def deriveStatusInfo(expected_state_and_info, service):
            expected_state, status_info = expected_state_and_info
            _check_service_state_expected(expected_state)
            if status_info is None:
                status_info = ""
            if self.active_state == SERVICE_STATE.UNKNOWN:
                return "unknown", status_info
            elif self.active_state == SERVICE_STATE.ON:
                return "running", status_info
            elif expected_state == SERVICE_STATE.ON:
                if self.active_state == SERVICE_STATE.OFF:
                    return (
                        "dead", "%s is currently stopped."
                        % (service.service_name,))
                else:
                    return (
                        "dead", "%s failed to start, process result: (%s)"
                        % (service.service_name, self.process_state))
            else:
                return "off", status_info

        d = maybeDeferred(service.getExpectedState)
        d.addCallback(deriveStatusInfo, service)
        return d


class Service(metaclass=ABCMeta):
    """Skeleton for a monitored service."""

    @abstractproperty
    def name(self):
        """Nice name of the service."""

    @abstractproperty
    def service_name(self):
        """Name of the service for systemd."""

    @abstractproperty
    def snap_service_name(self):
        """Name of the service when inside snap."""

    @abstractmethod
    def getExpectedState(self):
        """Returns (expected state, status_info) for the service."""


class AlwaysOnService(Service):
    """Service that should always be on."""

    def getExpectedState(self):
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

    # Used to convert the supervisor state to the `SERVICE_STATE` enum.
    SUPERVISOR_TO_STATE = {
        "STARTING": SERVICE_STATE.ON,
        "RUNNING": SERVICE_STATE.ON,
        "STOPPED": SERVICE_STATE.OFF,
        "FATAL": SERVICE_STATE.DEAD,
        "EXITED": SERVICE_STATE.DEAD,
    }

    # Used to log when the process state is not expected for the active state.
    PROCESS_STATE = {
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
            _check_service_state_observed(active_state)
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
    def restartService(self, name, if_on=False):
        """Restart service.

        Service will only be restarted if its expected state is ON.
        `ServiceNotOnError` will be raised if restart is called and the
        services expected state is not ON, except if if_on is True.
        """
        service = self.getServiceByName(name)
        expected_state, _ = yield maybeDeferred(service.getExpectedState)
        _check_service_state_expected(expected_state)
        if expected_state != SERVICE_STATE.ON:
            if if_on:
                return
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
                    state.active_state.value,
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
        expected_state, _ = yield maybeDeferred(service.getExpectedState)
        _check_service_state_expected(expected_state)
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
    def _execSystemDServiceAction(self, service_name, action, extra_opts=None):
        """Perform the action with the systemctl command.

        :return: tuple (exit code, std-output, std-error)
        """
        env = get_env_with_bytes_locale()
        cmd = ["sudo", "--non-interactive", "systemctl", action]
        if extra_opts is not None:
            cmd.extend(extra_opts)
        cmd.append(service_name)

        def decode(result):
            out, err, code = result
            return code, out.decode("utf-8"), err.decode("utf-8")

        d = getProcessOutputAndValue(cmd[0], cmd[1:], env=env)
        return d.addCallback(decode)

    @asynchronous
    def _execSupervisorServiceAction(self, service_name, action):
        """Perform the action with the run-supervisorctl command.

        :return: tuple (exit code, std-output, std-error)
        """
        env = get_env_with_bytes_locale()
        cmd = os.path.join(snappy.get_snap_path(), "bin", "run-supervisorctl")
        cmd = (cmd, action, service_name)

        def decode(result):
            out, err, code = result
            return code, out.decode("utf-8"), err.decode("utf-8")

        d = getProcessOutputAndValue(cmd[0], cmd[1:], env=env)
        return d.addCallback(decode)

    @inlineCallbacks
    def _performServiceAction(self, service, action):
        """Start or stop the service."""
        lock = self._getServiceLock(service.name)
        if snappy.running_in_snap():
            exec_action = self._execSupervisorServiceAction
            service_name = service.snap_service_name
        else:
            exec_action = self._execSystemDServiceAction
            service_name = service.service_name
        exit_code, output, error = yield lock.run(
            exec_action, service_name, action)
        if exit_code != 0:
            error_msg = (
                "Service '%s' failed to %s: %s" % (
                    service.name, action, error))
            maaslog.error(error_msg)
            raise ServiceActionError(error_msg)

    def _loadServiceState(self, service):
        """Return service status."""
        if snappy.running_in_snap():
            return self._loadSupervisorServiceState(service)
        else:
            return self._loadSystemDServiceState(service)

    @inlineCallbacks
    def _loadSystemDServiceState(self, service):
        """Return service status from systemd."""
        # Ignore the exit_code because systemd will return 0 for anything
        # other than a active service.
        exit_code, output, error = (
            yield self._execSystemDServiceAction(
                service.service_name, "status"))

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
    def _loadSupervisorServiceState(self, service):
        """Return service status from supervisor."""
        exit_code, output, error = (
            yield self._execSupervisorServiceAction(
                service.snap_service_name, "status"))
        # Anything above 3 is a bad error. The error codes below 3
        # do not provide a distinction between dead and fatal, so the parsed
        # string is used instead.
        if exit_code > 3:
            raise ServiceParsingError(
                "Unable to parse the output from supervisor for service '%s'; "
                "supervisorctl exited '%d': %s" % (
                    service.name, exit_code, output))
        output_split = output.split()
        name, status = output_split[0], output_split[1]
        if name != service.snap_service_name:
            raise ServiceParsingError(
                "Unable to parse the output from supervisor for service '%s'; "
                "supervisorctl returned status for '%s' instead of '%s'" % (
                    service.name, name, service.snap_service_name))
        active_state_enum = self.SUPERVISOR_TO_STATE.get(status)
        if active_state_enum is None:
            raise ServiceParsingError(
                "Unable to parse the output from supervisor for service '%s'; "
                "supervisorctl returned status as '%s'" % (
                    service.name, status))
        # Supervisor doesn't provide a process status, so make sure its correct
        # based on the active_state.
        returnValue((active_state_enum, self.PROCESS_STATE[active_state_enum]))

    @inlineCallbacks
    def _ensureService(self, service):
        """Ensure that the service is set to the correct state.

        We only ensure that the service is at its expected state. The
        current init system will control its process state and it should
        reach its expected process state based on the service's current
        active state.
        """
        expected_state, _ = yield maybeDeferred(service.getExpectedState)
        _check_service_state_expected(expected_state)
        if expected_state == SERVICE_STATE.OFF:
            # Service that should be off can also be dead.
            expected_states = [SERVICE_STATE.OFF, SERVICE_STATE.DEAD]
        elif expected_state == SERVICE_STATE.ANY:
            # This service is (temporarily) not being monitored.
            returnValue(ServiceState(SERVICE_STATE.UNKNOWN))
        else:
            expected_states = [expected_state]

        state = yield self.getServiceState(service.name, now=True)
        if state.active_state in expected_states:
            expected_process_state = (
                self.PROCESS_STATE[state.active_state])
            if state.process_state != expected_process_state:
                maaslog.warning(
                    "Service '%s' is %s but not in the expected state of "
                    "'%s', its current state is '%s'.",
                    service.service_name, state.active_state.value,
                    expected_process_state, state.process_state)
            else:
                maaslog.debug(
                    "Service '%s' is %s and '%s'.", service.service_name,
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
                service.service_name, expected_state.value, log_action)

            # Perform the required action to get the service to reach
            # its target state.
            yield self._performServiceAction(service, action)

            # Check that the service has remained at its target state.
            state = yield self.getServiceState(service.name, now=True)
            if state.active_state not in expected_states:
                error_msg = (
                    "Service '%s' failed to %s. Its current state "
                    "is '%s' and '%s'." % (
                        service.service_name, action,
                        state.active_state.value, state.process_state))
                maaslog.error(error_msg)
                raise ServiceActionError(error_msg)
            else:
                maaslog.info(
                    "Service '%s' has been %s and is '%s'.",
                    service.service_name, log_action, state.process_state)
        returnValue(state)
