# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Services monitor ensures services are in their expected state."""


from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "service_monitor",
]

from collections import defaultdict
import os
from subprocess import (
    PIPE,
    Popen,
    STDOUT,
)
from threading import Lock

from provisioningserver.drivers.service import (
    SERVICE_STATE,
    ServiceRegistry,
)
from provisioningserver.logger.log import get_maas_logger
from provisioningserver.utils import get_init_system
from provisioningserver.utils.twisted import (
    asynchronous,
    synchronous,
)
from twisted.internet.threads import deferToThread


maaslog = get_maas_logger("service_monitor")


class UnknownServiceError(Exception):
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
    """Monitors all services from the `ServiceRegistry` to make sure they
    remain in their expected state. Actions are performed on the services to
    keep the services in their desired state."""

    # Used to convert the upstart state to the `SERVICE_STATE` enum.
    UPSTART_TO_STATE = {
        "start": SERVICE_STATE.ON,
        "stop": SERVICE_STATE.OFF,
    }

    # Used to log when the process state is not expected for the active state.
    UPSTART_PROCESS_STATE = {
        SERVICE_STATE.ON: "running",
        SERVICE_STATE.OFF: "waiting",
    }

    # Used to convert the systemd state to the `SERVICE_STATE` enum.
    SYSTEMD_TO_STATE = {
        "active": SERVICE_STATE.ON,
        "inactive": SERVICE_STATE.OFF,
    }

    # Used to log when the process state is not expected for the active state.
    SYSTEMD_PROCESS_STATE = {
        SERVICE_STATE.ON: "running",
        SERVICE_STATE.OFF: "dead",
    }

    def __init__(self, init_system=None):
        if init_system is None:
            init_system = get_init_system()
        self.init_system = init_system
        self.service_locks = defaultdict(Lock)
        # A shared lock for critical sections.
        self._lock = Lock()

    def _get_service_lock(self, service):
        """Return the lock for service."""
        with self._lock:
            return self.service_locks[service]

    def _get_service_by_name(self, name):
        """Return service from its name in the `ServiceRegistry`."""
        service = ServiceRegistry.get_item(name)
        if service is None:
            raise UnknownServiceError(
                "Service '%s' is not registered." % name)
        return service

    @synchronous
    def get_service_state(self, name):
        service = ServiceRegistry.get_item(name)
        if service is None:
            raise UnknownServiceError(
                "Service '%s' is not registered." % name)
        return self._get_service_status(service)[0]

    @synchronous
    def ensure_all_services(self):
        """Ensures that all services from the `ServiceRegistry` are in their
        desired state."""
        for name, service in sorted(ServiceRegistry):
            try:
                self.ensure_service(name)
            except ServiceActionError:
                # ensure_service method already logs this error. Just catch
                # it here and ignore it.
                pass
            except Exception as e:
                maaslog.error(
                    "While monitoring service '%s' an error was "
                    "encountered: %s", service.service_name, e)

    @synchronous
    def ensure_service(self, name):
        """Ensures that a service is in its desired state."""
        service = self._get_service_by_name(name)
        with self._get_service_lock(name):
            self._ensure_service(service)

    @asynchronous
    def async_ensure_service(self, name):
        """Asynchronously ensures that a service is in its desired state."""
        return deferToThread(self.ensure_service, name)

    @synchronous
    def restart_service(self, name):
        """Restart service.

        Service will only be restarted if its expected state is ON.
        `ServiceNotOnError` will be raised if restart is called and the
        services expected state is not ON.
        """
        service = self._get_service_by_name(name)
        if service.get_expected_state() != SERVICE_STATE.ON:
            raise ServiceNotOnError(
                "Service '%s' is not on, unable to restart." % (
                    service.service_name))
        with self._get_service_lock(name):
            self._service_action(service, "restart")
            active_state, process_state = self._get_service_status(service)
            if active_state != SERVICE_STATE.ON:
                error_msg = (
                    "Service '%s' failed to restart. Its current state "
                    "is '%s' and '%s'." % (
                        service.service_name, active_state, process_state))
                maaslog.error(error_msg)
                raise ServiceActionError(error_msg)
            else:
                maaslog.info(
                    "Service '%s' has been restarted. Its current state "
                    "is '%s' and '%s'." % (
                        service.service_name, active_state, process_state))

    @asynchronous
    def async_restart_service(self, name):
        """Asynchronously restart the service."""
        return deferToThread(self.restart_service, name)

    def _exec_service_action(self, service_name, action):
        """Perform the action with the service command.

        :return: tuple (exit code, output)
        """
        # Force systemd to output in UTF-8 by selecting the C.UTF-8 locale.
        # This doesn't have any effect on upstart.
        env = os.environ.copy()
        env["LANG"] = "C.UTF-8"
        env["LC_ALL"] = "C.UTF-8"
        process = Popen(
            ["sudo", "service", service_name, action],
            stdin=PIPE, stdout=PIPE,
            stderr=STDOUT, close_fds=True, env=env)
        output, _ = process.communicate()
        return process.wait(), output.decode("utf-8").strip()

    def _service_action(self, service, action):
        """Start or stop the service."""
        exit_code, output = self._exec_service_action(
            service.service_name, action)
        if exit_code != 0:
            error_msg = (
                "Service '%s' failed to %s: %s" % (
                    service.service_name, action, output))
            maaslog.error(error_msg)
            raise ServiceActionError(error_msg)

    def _get_service_status(self, service):
        """Return service status based on the init system."""
        if self.init_system == "systemd":
            return self._get_systemd_service_status(
                service.service_name)
        elif self.init_system == "upstart":
            return self._get_upstart_service_status(
                service.service_name)

    def _get_systemd_service_status(self, service_name):
        exit_code, output = self._exec_service_action(service_name, "status")
        # Ignore the exit_code because systemd will return none 0 for anything
        # other than a active service.

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
        # output for unknown service looks like:
        #   missing.service
        #    Loaded: not-found (Reason: No such file or directory)
        #    Active: inactive (dead)
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Loaded"):
                load_status = line.split()[1]
                if load_status != "loaded":
                    raise UnknownServiceError("'%s' is unknown to systemd." % (
                        service_name))
            if line.startswith("Active"):
                active_split = line.split()
                active_state, process_state = (
                    active_split[1], active_split[2].lstrip('(').rstrip(')'))
                active_state_enum = self.SYSTEMD_TO_STATE.get(active_state)
                if active_state_enum is None:
                    raise ServiceParsingError(
                        "Unable to parse the active state from systemd for "
                        "service '%s', active state reported as '%s'." % (
                            service_name, active_state))
                return active_state_enum, process_state
        raise ServiceParsingError(
            "Unable to parse the output from systemd for service '%s'." % (
                service_name))

    def _get_upstart_service_status(self, service_name):
        exit_code, output = self._exec_service_action(service_name, "status")
        if exit_code != 0:
            raise UnknownServiceError("'%s' is unknown to upstart." % (
                service_name))
        for line in output.splitlines():
            if not line.startswith('sudo:'):
                active_state, process_state = self._parse_upstart_status_line(
                    line, service_name)
                break
        active_state_enum = self.UPSTART_TO_STATE.get(active_state)
        if active_state_enum is None:
            raise ServiceParsingError(
                "Unable to parse the active state from upstart for "
                "service '%s', active state reported as '%s'." % (
                    service_name, active_state))
        return active_state_enum, process_state

    def _parse_upstart_status_line(self, output, service_name):
        # output looks like:
        #    tgt start/running, process 29993
        # split to get the active_state/process_state
        try:
            output_split = output.split(",")[0].split()[1].split("/")
            active_state, process_state = output_split[0], output_split[1]
        except IndexError:
            raise ServiceParsingError(
                "Unable to parse the output from upstart for service '%s'." % (
                    service_name))
        return active_state, process_state

    def _get_expected_process_state(self, active_state):
        """Return the expected process state for the `active_state` based
        on the init system being used."""
        if self.init_system == "systemd":
            return self.SYSTEMD_PROCESS_STATE[active_state]
        elif self.init_system == "upstart":
            return self.UPSTART_PROCESS_STATE[active_state]

    def _ensure_service(self, service):
        """Ensure that the service is set to the correct state.

        We only ensure that the service is at its expected state. The
        current init system will control its process state and it should
        reach its expected process state based on the service's current
        active state.
        """
        expected_state = service.get_expected_state()
        active_state, process_state = self._get_service_status(service)
        if active_state == expected_state:
            expected_process_state = self._get_expected_process_state(
                active_state)
            if process_state != expected_process_state:
                maaslog.warn(
                    "Service '%s' is %s but not in the expected state of "
                    "'%s', its current state is '%s'.",
                    service.service_name, active_state,
                    expected_process_state, process_state)
            else:
                maaslog.debug(
                    "Service '%s' is %s and '%s'.",
                    service.service_name, active_state, process_state)
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
            self._service_action(service, action)

            # Check that the service has remained at its target state.
            active_state, process_state = self._get_service_status(service)
            if active_state != expected_state:
                error_msg = (
                    "Service '%s' failed to %s. Its current state "
                    "is '%s' and '%s'." % (
                        service.service_name, action, active_state,
                        process_state))
                maaslog.error(error_msg)
                raise ServiceActionError(error_msg)
            else:
                maaslog.info(
                    "Service '%s' has been %s and is '%s'." % (
                        service.service_name, log_action, process_state))


# Global service monitor.
service_monitor = ServiceMonitor()
