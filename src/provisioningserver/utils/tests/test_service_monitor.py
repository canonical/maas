# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.service_monitor`."""


import logging
import os
import random
from textwrap import dedent
from unittest.mock import call, Mock, sentinel

from fixtures import FakeLogger
from testscenarios import multiply_scenarios
from testtools import ExpectedException
from twisted.internet import reactor
from twisted.internet.defer import (
    CancelledError,
    DeferredLock,
    fail,
    inlineCallbacks,
    succeed,
)
from twisted.internet.task import deferLater

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.runtest import MAASTwistedRunTest
from maastesting.testcase import MAASTestCase
from maastesting.twisted import always_fail_with
from provisioningserver.utils import service_monitor as service_monitor_module
from provisioningserver.utils import snap
from provisioningserver.utils.service_monitor import (
    Service,
    SERVICE_STATE,
    ServiceActionError,
    ServiceMonitor,
    ServiceNotOnError,
    ServiceParsingError,
    ServiceState,
    ServiceUnknownError,
    ToggleableService,
)
from provisioningserver.utils.shell import get_env_with_bytes_locale
from provisioningserver.utils.snap import SnapPaths
from provisioningserver.utils.twisted import pause

TIMEOUT = get_testing_timeout()

EMPTY_SET = frozenset()


def pick_observed_state(*, but_not=EMPTY_SET):
    return factory.pick_enum(
        SERVICE_STATE, but_not={SERVICE_STATE.ANY, *but_not}
    )


def pick_expected_state(*, but_not=EMPTY_SET):
    return factory.pick_enum(
        SERVICE_STATE, but_not={SERVICE_STATE.UNKNOWN, *but_not}
    )


def make_fake_service(expected_state=None, status_info=None):
    fake_name = factory.make_name("name")
    fake_service_name = factory.make_name("service")
    if expected_state is None:
        if factory.pick_bool():
            expected_state = SERVICE_STATE.ON
        else:
            expected_state = SERVICE_STATE.OFF

    class FakeService(Service):
        name = fake_name
        service_name = fake_service_name
        snap_service_name = fake_service_name

        def getExpectedState(self):
            return succeed((expected_state, status_info))

    return FakeService()


class TestServiceState(MAASTestCase):
    """Tests for `ServiceState`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    scenarios_observed = tuple(
        ("observed=%s" % state.name, dict(state_observed=state))
        for state in SERVICE_STATE
        if state != SERVICE_STATE.ANY
    )

    scenarios_expected = tuple(
        ("expected=%s" % state.name, dict(state_expected=state))
        for state in SERVICE_STATE
        if state != SERVICE_STATE.UNKNOWN
    )

    scenarios = multiply_scenarios(scenarios_observed, scenarios_expected)

    expected_status_strings = {
        # (state-observed, state-expected): status-string
        (SERVICE_STATE.ON, SERVICE_STATE.ON): "running",
        (SERVICE_STATE.ON, SERVICE_STATE.OFF): "running",
        (SERVICE_STATE.ON, SERVICE_STATE.DEAD): "running",
        (SERVICE_STATE.ON, SERVICE_STATE.ANY): "running",
        (SERVICE_STATE.OFF, SERVICE_STATE.ON): "dead",
        (SERVICE_STATE.OFF, SERVICE_STATE.OFF): "off",
        (SERVICE_STATE.OFF, SERVICE_STATE.DEAD): "off",
        (SERVICE_STATE.OFF, SERVICE_STATE.ANY): "off",
        (SERVICE_STATE.DEAD, SERVICE_STATE.ON): "dead",
        (SERVICE_STATE.DEAD, SERVICE_STATE.OFF): "off",
        (SERVICE_STATE.DEAD, SERVICE_STATE.DEAD): "off",
        (SERVICE_STATE.DEAD, SERVICE_STATE.ANY): "off",
        (SERVICE_STATE.UNKNOWN, SERVICE_STATE.ON): "unknown",
        (SERVICE_STATE.UNKNOWN, SERVICE_STATE.OFF): "unknown",
        (SERVICE_STATE.UNKNOWN, SERVICE_STATE.DEAD): "unknown",
        (SERVICE_STATE.UNKNOWN, SERVICE_STATE.ANY): "unknown",
    }

    @inlineCallbacks
    def test_returns_service_status_string(self):
        # Make sure the short status string makes sense.
        service = make_fake_service(self.state_expected)
        state = ServiceState(self.state_observed, None)
        status_string, status_message = yield state.getStatusInfo(service)

        self.assertEqual(
            status_string,
            self.expected_status_strings[
                self.state_observed, self.state_expected
            ],
        )

    @inlineCallbacks
    def test_returns_service_info_message(self):
        # Make sure any message given by a service gets passed through, except
        # when the service is dead or off and expected to be on, in which case
        # a message is manufactured.
        example_message = factory.make_string(60, spaces=True)
        example_process_state = factory.make_name("process-state")
        service = make_fake_service(self.state_expected, example_message)
        state = ServiceState(self.state_observed, example_process_state)
        status_string, status_message = yield state.getStatusInfo(service)

        if self.state_expected == SERVICE_STATE.ON:
            if self.state_observed == SERVICE_STATE.OFF:
                self.assertEqual(
                    status_message,
                    service.service_name + " is currently stopped.",
                )
            elif self.state_observed == SERVICE_STATE.DEAD:
                self.assertEqual(
                    status_message,
                    service.service_name
                    + " failed to start, process result: ("
                    + example_process_state
                    + ")",
                )
            else:
                self.assertEqual(status_message, example_message)
        else:
            self.assertEqual(status_message, example_message)


class TestServiceMonitor(MAASTestCase):
    """Tests for `ServiceMonitor`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def run_under_snap(self):
        self.patch(snap, "running_in_snap").return_value = True

    def make_service_monitor(self, fake_services=None):
        if fake_services is None:
            fake_services = [make_fake_service() for _ in range(3)]
        return ServiceMonitor(*fake_services)

    @inlineCallbacks
    def test_getServiceLock_returns_lock_for_service(self):
        service_monitor = self.make_service_monitor()
        name = factory.make_name("service")
        lock = yield service_monitor._getServiceLock(name)
        self.assertIsInstance(lock, DeferredLock)

    def test_getServiceByName_returns_service(self):
        fake_service = make_fake_service()
        service_monitor = self.make_service_monitor([fake_service])
        self.assertEqual(
            fake_service, service_monitor.getServiceByName(fake_service.name)
        )

    def test_getServiceByName_raises_ServiceUnknownError(self):
        service_monitor = self.make_service_monitor()
        self.assertRaises(
            ServiceUnknownError,
            service_monitor.getServiceByName,
            factory.make_name("service"),
        )

    @inlineCallbacks
    def test_updateServiceState_updates_stored_service_state(self):
        service_monitor = self.make_service_monitor()
        name = factory.make_name("service")
        active_state = pick_observed_state()
        process_state = random.choice(["running", "dead"])
        observed_state = yield service_monitor._updateServiceState(
            name, active_state, process_state
        )
        state = service_monitor._serviceStates[name]
        self.assertEqual(
            (active_state, process_state),
            (state.active_state, state.process_state),
        )
        self.assertEqual(state, observed_state)

    @inlineCallbacks
    def test_updateServiceState_does_not_hold_service_lock(self):
        service_monitor = self.make_service_monitor()
        service_lock = self.patch(service_monitor, "_getServiceLock")
        name = factory.make_name("service")
        active_state = pick_observed_state()
        process_state = random.choice(["running", "dead"])
        yield service_monitor._updateServiceState(
            name, active_state, process_state
        )
        service_lock.acquire.assert_not_called()
        service_lock.release.assert_not_called()

    @inlineCallbacks
    def test_getServiceState_with_now_True(self):
        fake_service = make_fake_service()
        service_monitor = self.make_service_monitor([fake_service])
        active_state = pick_observed_state()
        process_state = random.choice(["running", "dead"])
        mock_loadSystemDServiceState = self.patch(
            service_monitor, "_loadSystemDServiceState"
        )
        mock_loadSystemDServiceState.return_value = succeed(
            (active_state, process_state)
        )
        observed_state = yield service_monitor.getServiceState(
            fake_service.name, now=True
        )
        state = service_monitor._serviceStates[fake_service.name]
        self.assertEqual(
            (active_state, process_state),
            (state.active_state, state.process_state),
        )
        self.assertEqual(state, observed_state)

        mock_loadSystemDServiceState.assert_called_once_with(fake_service)

    @inlineCallbacks
    def test_getServiceState_with_now_False(self):
        fake_service = make_fake_service()
        service_monitor = self.make_service_monitor([fake_service])
        mock_loadSystemDServiceState = self.patch(
            service_monitor, "_loadSystemDServiceState"
        )
        observed_state = yield service_monitor.getServiceState(
            fake_service.name, now=False
        )
        state = service_monitor._serviceStates[fake_service.name]
        self.assertEqual(
            (SERVICE_STATE.UNKNOWN, None),
            (state.active_state, state.process_state),
        )
        self.assertEqual(state, observed_state)
        mock_loadSystemDServiceState.assert_not_called()

    @inlineCallbacks
    def test_ensureServices_returns_dict_for_states(self):
        fake_services = [make_fake_service() for _ in range(3)]
        expected_states = {}
        for service in fake_services:
            active_state = pick_observed_state()
            process_state = random.choice(["running", "dead"])
            expected_states[service.name] = ServiceState(
                active_state, process_state
            )
        service_monitor = self.make_service_monitor(fake_services)
        self.patch(
            service_monitor, "ensureService"
        ).side_effect = lambda name: succeed(expected_states[name])
        observed = yield service_monitor.ensureServices()
        self.assertEqual(expected_states, observed)

    @inlineCallbacks
    def test_ensureServices_handles_errors(self):
        services = make_fake_service(), make_fake_service()
        service_monitor = self.make_service_monitor(services)
        # Plant some states into the monitor's memory.
        service_states = {
            service.name: ServiceState(
                pick_observed_state(), random.choice(["running", "dead"])
            )
            for service in services
        }
        service_monitor._serviceStates.update(service_states)

        # Make both service monitor checks fail with a distinct error.
        self.patch(service_monitor, "ensureService")

        def raise_exception(service_name):
            raise factory.make_exception(service_name + " broke")

        def raise_exception_later(service_name):
            # We use deferLater() to ensure that `raise_exception` is called
            # asynchronously; this helps to ensure that ensureServices() has
            # not closed over mutating local state, e.g. a loop variable.
            return deferLater(reactor, 0, raise_exception, service_name)

        service_monitor.ensureService.side_effect = raise_exception_later

        # Capture logs when calling ensureServices().
        with FakeLogger("maas.service_monitor") as logger:
            observed = yield service_monitor.ensureServices()
        # The errors mean we were returned the states planted earlier.
        self.assertEqual(observed, service_states)
        # The errors were logged with the service name and message.
        for service in services:
            self.assertIn(
                f"While monitoring service '{service.name}' an error was encountered: {service.name} broke",
                logger.output,
            )

    @inlineCallbacks
    def test_ensureServices_calls__ensureService(self):
        fake_service = make_fake_service()
        service_monitor = self.make_service_monitor([fake_service])
        active_state = pick_observed_state()
        process_state = random.choice(["running", "dead"])
        service_state = ServiceState(active_state, process_state)
        mock_ensureService = self.patch(service_monitor, "_ensureService")
        mock_ensureService.return_value = succeed(service_state)
        observed = yield service_monitor.ensureService(fake_service.name)
        self.assertEqual(service_state, observed)
        mock_ensureService.assert_called_once_with(fake_service)

    @inlineCallbacks
    def test_restartService_raises_ServiceNotOnError(self):
        fake_service = make_fake_service(SERVICE_STATE.OFF)
        service_monitor = self.make_service_monitor([fake_service])
        with ExpectedException(ServiceNotOnError):
            yield service_monitor.restartService(fake_service.name)

    @inlineCallbacks
    def test_restartService_performs_restart(self):
        fake_service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([fake_service])
        mock_performServiceAction = self.patch(
            service_monitor, "_performServiceAction"
        )
        mock_performServiceAction.return_value = succeed(None)
        service_state = ServiceState(SERVICE_STATE.ON, "running")
        mock_getServiceState = self.patch(service_monitor, "getServiceState")
        mock_getServiceState.return_value = succeed(service_state)
        observed = yield service_monitor.restartService(fake_service.name)
        self.assertEqual(service_state, observed)
        mock_getServiceState.assert_called_once_with(
            fake_service.name, now=True
        ),
        mock_performServiceAction.assert_called_once_with(
            fake_service, "restart"
        )

    @inlineCallbacks
    def test_restartService_raises_ServiceActionError_if_not_on(self):
        fake_service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([fake_service])
        mock_performServiceAction = self.patch(
            service_monitor, "_performServiceAction"
        )
        mock_performServiceAction.return_value = succeed(None)
        active_state = pick_observed_state(but_not={SERVICE_STATE.ON})
        service_state = ServiceState(active_state, "dead")
        mock_getServiceState = self.patch(service_monitor, "getServiceState")
        mock_getServiceState.return_value = succeed(service_state)
        with ExpectedException(ServiceActionError):
            yield service_monitor.restartService(fake_service.name)

    @inlineCallbacks
    def test_reloadService_raises_ServiceNotOnError(self):
        fake_service = make_fake_service(SERVICE_STATE.OFF)
        service_monitor = self.make_service_monitor([fake_service])
        with ExpectedException(ServiceNotOnError):
            yield service_monitor.reloadService(fake_service.name)

    @inlineCallbacks
    def test_reloadService_returns_when_if_on(self):
        fake_service = make_fake_service(SERVICE_STATE.OFF)
        service_monitor = self.make_service_monitor([fake_service])
        yield service_monitor.restartService(fake_service.name, if_on=True)
        # No exception expected.

    @inlineCallbacks
    def test_reloadService_calls_ensureService_then_reloads(self):
        fake_service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([fake_service])
        mock_performServiceAction = self.patch(
            service_monitor, "_performServiceAction"
        )
        mock_performServiceAction.return_value = succeed(None)
        mock_ensureService = self.patch(service_monitor, "ensureService")
        mock_ensureService.return_value = succeed(
            ServiceState(SERVICE_STATE.ON, "running")
        )
        yield service_monitor.reloadService(fake_service.name)
        mock_ensureService.assert_called_once_with(fake_service.name)
        mock_performServiceAction.assert_called_once_with(
            fake_service, "reload"
        )

    @inlineCallbacks
    def test_reloadService_raises_error_if_fails_to_start(self):
        fake_service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([fake_service])
        mock_ensureService = self.patch(service_monitor, "ensureService")
        mock_ensureService.return_value = succeed(
            ServiceState(SERVICE_STATE.OFF, "dead")
        )
        with ExpectedException(ServiceActionError):
            yield service_monitor.reloadService(fake_service.name)

    @inlineCallbacks
    def test_reloadService_returns_when_if_on_equals_false(self):
        fake_service = make_fake_service(SERVICE_STATE.OFF)
        service_monitor = self.make_service_monitor([fake_service])
        yield service_monitor.reloadService(fake_service.name, if_on=True)
        # No exception expected.

    @inlineCallbacks
    def test_reloadService_always_calls_ensureService_then_reloads(self):
        fake_service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([fake_service])
        mock_performServiceAction = self.patch(
            service_monitor, "_performServiceAction"
        )
        mock_performServiceAction.return_value = succeed(None)
        mock_ensureService = self.patch(service_monitor, "ensureService")
        mock_ensureService.return_value = succeed(
            ServiceState(SERVICE_STATE.ON, "running")
        )
        yield service_monitor.reloadService(fake_service.name, if_on=True)
        mock_ensureService.assert_called_once_with(fake_service.name)
        mock_performServiceAction.assert_called_once_with(
            fake_service, "reload"
        )

    @inlineCallbacks
    def test_reloadService_always_raises_error_if_fails_to_start(self):
        fake_service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([fake_service])
        mock_ensureService = self.patch(service_monitor, "ensureService")
        mock_ensureService.return_value = succeed(
            ServiceState(SERVICE_STATE.OFF, "dead")
        )
        with ExpectedException(ServiceActionError):
            yield service_monitor.reloadService(fake_service.name, if_on=True)

    @inlineCallbacks
    def test_killService_performs_kill_then_ensureService(self):
        fake_service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([fake_service])
        mock_performServiceAction = self.patch(
            service_monitor, "_performServiceAction"
        )
        mock_performServiceAction.return_value = succeed(None)
        mock_ensureService = self.patch(service_monitor, "ensureService")
        mock_ensureService.return_value = succeed(
            ServiceState(SERVICE_STATE.ON, "running")
        )
        yield service_monitor.killService(fake_service.name)
        mock_ensureService.assert_called_once_with(fake_service.name)
        mock_performServiceAction.assert_called_once_with(fake_service, "kill")

    @inlineCallbacks
    def test_killService_doesnt_fail_on_ServiceActionError(self):
        fake_service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([fake_service])
        mock_performServiceAction = self.patch(
            service_monitor, "_performServiceAction"
        )
        mock_performServiceAction.return_value = fail(ServiceActionError())
        mock_ensureService = self.patch(service_monitor, "ensureService")
        mock_ensureService.return_value = succeed(
            ServiceState(SERVICE_STATE.ON, "running")
        )
        yield service_monitor.killService(fake_service.name)
        mock_ensureService.assert_called_once_with(fake_service.name)
        mock_performServiceAction.assert_called_once_with(fake_service, "kill")

    @inlineCallbacks
    def test_execCmd_times_out(self):
        monitor = ServiceMonitor(make_fake_service())
        with ExpectedException(ServiceActionError):
            yield monitor._execCmd(
                ["sleep", "0.3"], {}, timeout=0.1, retries=1
            )
        # Pause long enough for the reactor to cleanup the process.
        yield pause(0.5)

    @inlineCallbacks
    def test_execCmd_retries(self):
        monitor = ServiceMonitor(make_fake_service())
        mock_deferWithTimeout = self.patch(
            service_monitor_module, "deferWithTimeout"
        )
        mock_deferWithTimeout.side_effect = always_fail_with(CancelledError())
        with ExpectedException(ServiceActionError):
            yield monitor._execCmd(["echo", "Hello"], {}, retries=3)
        self.assertEqual(3, mock_deferWithTimeout.call_count)

    @inlineCallbacks
    def test_execSystemDServiceAction_calls_systemctl(self):
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        action = factory.make_name("action")
        mock_getProcessOutputAndValue = self.patch(
            service_monitor_module, "getProcessOutputAndValue"
        )
        mock_getProcessOutputAndValue.return_value = succeed((b"", b"", 0))
        yield service_monitor._execSystemDServiceAction(service_name, action)
        cmd = ["sudo", "--non-interactive", "systemctl", action, service_name]
        mock_getProcessOutputAndValue.assert_called_once_with(
            # The environment contains LC_ALL and LANG too.
            cmd[0],
            cmd[1:],
            env=get_env_with_bytes_locale(),
        )

    @inlineCallbacks
    def test_execSystemDServiceAction_calls_systemctl_with_options(self):
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        mock_getProcessOutputAndValue = self.patch(
            service_monitor_module, "getProcessOutputAndValue"
        )
        mock_getProcessOutputAndValue.return_value = succeed((b"", b"", 0))
        yield service_monitor._execSystemDServiceAction(
            service_name, "kill", extra_opts=["-s", "SIGKILL"]
        )
        cmd = [
            "sudo",
            "--non-interactive",
            "systemctl",
            "kill",
            "-s",
            "SIGKILL",
            service_name,
        ]
        mock_getProcessOutputAndValue.assert_called_once_with(
            # The environment contains LC_ALL and LANG too.
            cmd[0],
            cmd[1:],
            env=get_env_with_bytes_locale(),
        )

    @inlineCallbacks
    def test_execSystemDServiceAction_decodes_stdout_and_stderr(self):
        # From https://www.cl.cam.ac.uk/~mgk25/ucs/examples/UTF-8-demo.txt.
        example_text = (
            "\u16bb\u16d6 \u16b3\u16b9\u16ab\u16a6 \u16a6\u16ab\u16cf "
            "\u16bb\u16d6 \u16d2\u16a2\u16de\u16d6 \u16a9\u16be \u16a6"
            "\u16ab\u16d7 \u16da\u16aa\u16be\u16de\u16d6 \u16be\u16a9"
            "\u16b1\u16a6\u16b9\u16d6\u16aa\u16b1\u16de\u16a2\u16d7 "
            "\u16b9\u16c1\u16a6 \u16a6\u16aa \u16b9\u16d6\u16e5\u16ab"
        )
        example_stdout = example_text[: len(example_text) // 2]
        example_stderr = example_text[len(example_text) // 2 :]
        service_monitor = self.make_service_monitor()
        mock_getProcessOutputAndValue = self.patch(
            service_monitor_module, "getProcessOutputAndValue"
        )
        mock_getProcessOutputAndValue.return_value = succeed(
            (example_stdout.encode("utf-8"), example_stderr.encode("utf-8"), 0)
        )
        _, stdout, stderr = yield service_monitor._execSystemDServiceAction(
            factory.make_name("service"), factory.make_name("action")
        )
        self.assertEqual(stdout, example_stdout)
        self.assertEqual(stderr, example_stderr)

    @inlineCallbacks
    def test_execSupervisorServiceAction_calls_supervisorctl(self):
        snap_path = factory.make_name("path")
        self.patch(snap.SnapPaths, "from_environ").return_value = SnapPaths(
            snap=snap_path
        )
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        action = factory.make_name("action")
        mock_getProcessOutputAndValue = self.patch(
            service_monitor_module, "getProcessOutputAndValue"
        )
        mock_getProcessOutputAndValue.return_value = succeed((b"", b"", 0))
        extra_opts = ("--extra", factory.make_name("extra"))
        yield service_monitor._execSupervisorServiceAction(
            service_name, action, extra_opts=extra_opts
        )
        cmd = os.path.join(snap_path, "bin", "run-supervisorctl")
        cmd = (cmd, action) + extra_opts + (service_name,)
        mock_getProcessOutputAndValue.assert_called_once_with(
            # The environment contains LC_ALL and LANG too.
            cmd[0],
            cmd[1:],
            env=get_env_with_bytes_locale(),
        )

    @inlineCallbacks
    def test_execSupervisorServiceAction_emulates_kill(self):
        snap_path = factory.make_name("path")
        self.patch(snap.SnapPaths, "from_environ").return_value = SnapPaths(
            snap=snap_path
        )
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        fake_pid = random.randint(1, 100)
        mock_getProcessOutputAndValue = self.patch(
            service_monitor_module, "getProcessOutputAndValue"
        )
        mock_getProcessOutputAndValue.side_effect = [
            succeed((("%s" % fake_pid).encode("utf-8"), b"", 0)),
            succeed((b"", b"", 0)),
        ]
        extra_opts = ("-s", factory.make_name("SIGKILL"))
        yield service_monitor._execSupervisorServiceAction(
            service_name, "kill", extra_opts=extra_opts
        )
        cmd = os.path.join(snap_path, "bin", "run-supervisorctl")
        mock_getProcessOutputAndValue.assert_has_calls(
            [
                call(
                    cmd, ("pid", service_name), env=get_env_with_bytes_locale()
                ),
                call(
                    "kill",
                    extra_opts + ("%s" % fake_pid,),
                    env=get_env_with_bytes_locale(),
                ),
            ],
        )

    @inlineCallbacks
    def test_execSupervisorServiceAction_decodes_stdout_and_stderr(self):
        # From https://www.cl.cam.ac.uk/~mgk25/ucs/examples/UTF-8-demo.txt.
        example_text = (
            "\u16bb\u16d6 \u16b3\u16b9\u16ab\u16a6 \u16a6\u16ab\u16cf "
            "\u16bb\u16d6 \u16d2\u16a2\u16de\u16d6 \u16a9\u16be \u16a6"
            "\u16ab\u16d7 \u16da\u16aa\u16be\u16de\u16d6 \u16be\u16a9"
            "\u16b1\u16a6\u16b9\u16d6\u16aa\u16b1\u16de\u16a2\u16d7 "
            "\u16b9\u16c1\u16a6 \u16a6\u16aa \u16b9\u16d6\u16e5\u16ab"
        )
        example_stdout = example_text[: len(example_text) // 2]
        example_stderr = example_text[len(example_text) // 2 :]
        snap_path = factory.make_name("path")
        self.patch(snap.SnapPaths, "from_environ").return_value = SnapPaths(
            snap=snap_path
        )
        service_monitor = self.make_service_monitor()
        mock_getProcessOutputAndValue = self.patch(
            service_monitor_module, "getProcessOutputAndValue"
        )
        mock_getProcessOutputAndValue.return_value = succeed(
            (example_stdout.encode("utf-8"), example_stderr.encode("utf-8"), 0)
        )
        _, stdout, stderr = yield service_monitor._execSupervisorServiceAction(
            factory.make_name("service"), factory.make_name("action")
        )
        self.assertEqual(stdout, example_stdout)
        self.assertEqual(stderr, example_stderr)

    @inlineCallbacks
    def test_performServiceAction_holds_lock_performs_systemd_action(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor()
        service_locks = service_monitor._serviceLocks
        service_lock = service_locks[service.name]
        service_lock = service_locks[service.name] = Mock(wraps=service_lock)
        mock_execSystemDServiceAction = self.patch(
            service_monitor, "_execSystemDServiceAction"
        )
        mock_execSystemDServiceAction.return_value = (0, "", "")
        action = factory.make_name("action")
        extra_opts = ("--option", factory.make_name("option"))
        setattr(service, "%s_extra_opts" % action, extra_opts)
        yield service_monitor._performServiceAction(service, action)
        service_lock.run.assert_called_once_with(
            service_monitor._execSystemDServiceAction,
            service.service_name,
            action,
            extra_opts=extra_opts,
        )
        mock_execSystemDServiceAction.assert_called_once_with(
            service.service_name, action, extra_opts=extra_opts
        )

    @inlineCallbacks
    def test_performServiceAction_holds_lock_perform_supervisor_action(self):
        self.run_under_snap()
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor()
        service_locks = service_monitor._serviceLocks
        service_lock = service_locks[service.name]
        service_lock = service_locks[service.name] = Mock(wraps=service_lock)
        mock_execSupervisorServiceAction = self.patch(
            service_monitor, "_execSupervisorServiceAction"
        )
        mock_execSupervisorServiceAction.return_value = (0, "", "")
        action = factory.make_name("action")
        extra_opts = ("--option", factory.make_name("option"))
        setattr(service, "%s_extra_opts" % action, extra_opts)
        yield service_monitor._performServiceAction(service, action)
        service_lock.run.assert_called_once_with(
            service_monitor._execSupervisorServiceAction,
            service.service_name,
            action,
            extra_opts=extra_opts,
        )
        mock_execSupervisorServiceAction.assert_called_once_with(
            service.service_name, action, extra_opts=extra_opts
        )

    @inlineCallbacks
    def test_performServiceAction_raises_ServiceActionError_if_fails(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor()
        mock_execSystemDServiceAction = self.patch(
            service_monitor, "_execSystemDServiceAction"
        )
        mock_execSystemDServiceAction.return_value = (1, "", "")
        action = factory.make_name("action")
        with ExpectedException(ServiceActionError):
            yield service_monitor._performServiceAction(service, action)

    @inlineCallbacks
    def test_performServiceAction_logs_error_if_action_fails(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor()
        mock_execSystemDServiceAction = self.patch(
            service_monitor, "_execSystemDServiceAction"
        )
        error_output = factory.make_name("error")
        mock_execSystemDServiceAction.return_value = (1, "", error_output)
        action = factory.make_name("action")
        with FakeLogger(
            "maas.service_monitor", level=logging.ERROR
        ) as maaslog:
            with ExpectedException(ServiceActionError):
                yield service_monitor._performServiceAction(service, action)

        self.assertDocTestMatches(
            "Service '%s' failed to %s: %s"
            % (service.name, action, error_output),
            maaslog.output,
        )

    def test_loadServiceState_uses_systemd(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        mock_loadSystemDServiceState = self.patch(
            service_monitor, "_loadSystemDServiceState"
        )
        mock_loadSystemDServiceState.return_value = sentinel.result
        self.assertEqual(
            sentinel.result, service_monitor._loadServiceState(service)
        )

    def test_loadServiceState_uses_supervisor(self):
        self.run_under_snap()
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        mock_loadSupervisorServiceState = self.patch(
            service_monitor, "_loadSupervisorServiceState"
        )
        mock_loadSupervisorServiceState.return_value = sentinel.result
        self.assertEqual(
            sentinel.result, service_monitor._loadServiceState(service)
        )

    @inlineCallbacks
    def test_loadSystemDServiceState_status_calls_systemctl(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        mock_execSystemDServiceAction = self.patch(
            service_monitor, "_execSystemDServiceAction"
        )
        mock_execSystemDServiceAction.side_effect = factory.make_exception()
        try:
            yield service_monitor._loadSystemDServiceState(service)
        except Exception:
            pass
        mock_execSystemDServiceAction.assert_called_once_with(
            service.service_name, "status"
        )

    @inlineCallbacks
    def test_loadSystemDServiceState_status_raises_ServiceUnknownError(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor()
        systemd_status_output = (
            dedent(
                """\
            %s.service
                Loaded: not-found (Reason: No such file or directory)
                Active: inactive (dead)
            """
            )
            % service.service_name
        )

        mock_execSystemDServiceAction = self.patch(
            service_monitor, "_execSystemDServiceAction"
        )
        mock_execSystemDServiceAction.return_value = (
            3,
            systemd_status_output,
            "",
        )
        with ExpectedException(ServiceUnknownError):
            yield service_monitor._loadSystemDServiceState(service)

    @inlineCallbacks
    def test_loadSystemDServiceState_status_returns_off_and_dead(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        systemd_status_output = (
            dedent(
                """\
            %s.service - LSB: iscsi target daemon
                Loaded: loaded (/lib/systemd/system/%s.service)
                Active: %s (dead)
                Docs: man:systemd-sysv-generator(8)
            """
            )
            % (
                service.service_name,
                service.service_name,
                random.choice(["inactive", "deactivating"]),
            )
        )

        mock_execSystemDServiceAction = self.patch(
            service_monitor, "_execSystemDServiceAction"
        )
        mock_execSystemDServiceAction.return_value = (
            3,
            systemd_status_output,
            "",
        )
        active_state, process_state = yield (
            service_monitor._loadSystemDServiceState(service)
        )
        self.assertEqual(SERVICE_STATE.OFF, active_state)
        self.assertEqual("dead", process_state)

    @inlineCallbacks
    def test_loadSystemDServiceState_status_returns_dead_for_failed(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        systemd_status_output = (
            dedent(
                """\
            %s.service - Fake service
                Loaded: loaded (/lib/systemd/system/%s.service; ...
                Active: %s (Result: exit-code) since Wed 2016-01-20...
                Docs: man:dhcpd(8)
            """
            )
            % (
                service.service_name,
                service.service_name,
                random.choice(["reloading", "failed", "activating"]),
            )
        )

        mock_execSystemDServiceAction = self.patch(
            service_monitor, "_execSystemDServiceAction"
        )
        mock_execSystemDServiceAction.return_value = (
            3,
            systemd_status_output,
            "",
        )
        active_state, process_state = yield (
            service_monitor._loadSystemDServiceState(service)
        )
        self.assertEqual(SERVICE_STATE.DEAD, active_state)

    @inlineCallbacks
    def test_loadSystemDServiceState_status_returns_on_and_running(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        systemd_status_output = (
            dedent(
                """\
            %s.service - Fake Service
                Loaded: loaded (/lib/systemd/system/%s.service)
                Active: active (running) since Fri 2015-05-15 15:08:26 UTC;
                Docs: man:systemd-sysv-generator(8)
            """
            )
            % (service.service_name, service.service_name)
        )

        mock_execSystemDServiceAction = self.patch(
            service_monitor, "_execSystemDServiceAction"
        )
        mock_execSystemDServiceAction.return_value = (
            0,
            systemd_status_output,
            "",
        )
        active_state, process_state = yield (
            service_monitor._loadSystemDServiceState(service)
        )
        self.assertEqual(SERVICE_STATE.ON, active_state)
        self.assertEqual("running", process_state)

    @inlineCallbacks
    def test_loadSystemDServiceState_status_ignores_sudo_output(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        systemd_status_output = (
            dedent(
                """\
            sudo: unable to resolve host sub-etha-sens-o-matic
            %s.service - Fake service
                Loaded: loaded (/lib/systemd/system/%s.service)
                Active: active (running) since Fri 2015-05-15 15:08:26 UTC;
                Docs: man:systemd-sysv-generator(8)
            """
            )
            % (service.service_name, service.service_name)
        )

        mock_execSystemDServiceAction = self.patch(
            service_monitor, "_execSystemDServiceAction"
        )
        mock_execSystemDServiceAction.return_value = (
            0,
            systemd_status_output,
            "",
        )
        active_state, process_state = yield (
            service_monitor._loadSystemDServiceState(service)
        )
        self.assertEqual(SERVICE_STATE.ON, active_state)
        self.assertEqual("running", process_state)

    @inlineCallbacks
    def test_loadSystemDServiceState_status_raise_error_for_bad_active(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        systemd_status_output = (
            dedent(
                """\
            %s.service - Fake service
                Loaded: loaded (/lib/systemd/system/%s.service)
                Active: unknown (running) since Fri 2015-05-15 15:08:26 UTC;
                Docs: man:systemd-sysv-generator(8)
            """
            )
            % (service.service_name, service.service_name)
        )

        service_monitor = self.make_service_monitor()
        mock_execSystemDServiceAction = self.patch(
            service_monitor, "_execSystemDServiceAction"
        )
        mock_execSystemDServiceAction.return_value = (
            0,
            systemd_status_output,
            "",
        )

        with ExpectedException(ServiceParsingError):
            yield service_monitor._loadSystemDServiceState(service)

    @inlineCallbacks
    def test_loadSystemDServiceState_status_raise_error_for_bad_output(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        mock_execSystemDServiceAction = self.patch(
            service_monitor, "_execSystemDServiceAction"
        )
        mock_execSystemDServiceAction.return_value = (
            3,
            factory.make_name("invalid"),
            "",
        )

        with ExpectedException(ServiceParsingError):
            yield service_monitor._loadSystemDServiceState(service)

    @inlineCallbacks
    def test_loadSupervisorServiceState_status_calls_supervisorctl(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        mock_execSupervisorServiceAction = self.patch(
            service_monitor, "_execSupervisorServiceAction"
        )
        mock_execSupervisorServiceAction.side_effect = factory.make_exception()
        try:
            yield service_monitor._loadSupervisorServiceState(service)
        except Exception:
            pass
        mock_execSupervisorServiceAction.assert_called_once_with(
            service.service_name, "status"
        )

    @inlineCallbacks
    def test_loadSupervisorServiceState_exit_code_greater_than_3(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor()
        mock_execSupervisorServiceAction = self.patch(
            service_monitor, "_execSupervisorServiceAction"
        )
        mock_execSupervisorServiceAction.return_value = (4, "", "")
        with ExpectedException(ServiceParsingError):
            yield service_monitor._loadSupervisorServiceState(service)

    @inlineCallbacks
    def test_loadSupervisorServiceState_service_name_doesnt_match(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor()
        supervisor_status_output = dedent(
            """\
            invalid              STARTING   pid 112588, uptime 11:11:11
            """
        )

        mock_execSupervisorServiceAction = self.patch(
            service_monitor, "_execSupervisorServiceAction"
        )
        mock_execSupervisorServiceAction.return_value = (
            1,
            supervisor_status_output,
            "",
        )
        with ExpectedException(ServiceParsingError):
            yield service_monitor._loadSupervisorServiceState(service)

    @inlineCallbacks
    def test_loadSupervisorServiceState_unknown_status(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor()
        supervisor_status_output = (
            dedent(
                """\
            %s              UNKNOWN   pid 112588, uptime 11:11:11
            """
            )
            % (service.snap_service_name)
        )

        mock_execSupervisorServiceAction = self.patch(
            service_monitor, "_execSupervisorServiceAction"
        )
        mock_execSupervisorServiceAction.return_value = (
            1,
            supervisor_status_output,
            "",
        )
        with ExpectedException(ServiceParsingError):
            yield service_monitor._loadSupervisorServiceState(service)

    @inlineCallbacks
    def test_loadSupervisorServiceState_starting_returns_on(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        supervisor_status_output = (
            dedent(
                """\
            %s              STARTING   pid 112588, uptime 11:11:11
            """
            )
            % (service.snap_service_name)
        )

        mock_execSupervisorServiceAction = self.patch(
            service_monitor, "_execSupervisorServiceAction"
        )
        mock_execSupervisorServiceAction.return_value = (
            0,
            supervisor_status_output,
            "",
        )
        active_state, process_state = yield (
            service_monitor._loadSupervisorServiceState(service)
        )
        self.assertEqual(SERVICE_STATE.ON, active_state)
        self.assertEqual("running", process_state)

    @inlineCallbacks
    def test_loadSupervisorServiceState_running_returns_on(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        supervisor_status_output = (
            dedent(
                """\
            %s              RUNNING   pid 112588, uptime 11:11:11
            """
            )
            % (service.snap_service_name)
        )

        mock_execSupervisorServiceAction = self.patch(
            service_monitor, "_execSupervisorServiceAction"
        )
        mock_execSupervisorServiceAction.return_value = (
            0,
            supervisor_status_output,
            "",
        )
        active_state, process_state = yield (
            service_monitor._loadSupervisorServiceState(service)
        )
        self.assertEqual(SERVICE_STATE.ON, active_state)
        self.assertEqual("running", process_state)

    @inlineCallbacks
    def test_loadSupervisorServiceState_stopped_returns_off(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        supervisor_status_output = (
            dedent(
                """\
            %s              STOPPED   Not started
            """
            )
            % (service.snap_service_name)
        )

        mock_execSupervisorServiceAction = self.patch(
            service_monitor, "_execSupervisorServiceAction"
        )
        mock_execSupervisorServiceAction.return_value = (
            1,
            supervisor_status_output,
            "",
        )
        active_state, process_state = yield (
            service_monitor._loadSupervisorServiceState(service)
        )
        self.assertEqual(SERVICE_STATE.OFF, active_state)
        self.assertEqual("dead", process_state)

    @inlineCallbacks
    def test_loadSupervisorServiceState_stopping_returns_off(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        supervisor_status_output = f"{service.snap_service_name}              STOPPING   pid 12345, uptime 1:02:03"

        mock_execSupervisorServiceAction = self.patch(
            service_monitor, "_execSupervisorServiceAction"
        )
        mock_execSupervisorServiceAction.return_value = (
            1,
            supervisor_status_output,
            "",
        )
        active_state, process_state = yield (
            service_monitor._loadSupervisorServiceState(service)
        )
        self.assertEqual(SERVICE_STATE.OFF, active_state)
        self.assertEqual("dead", process_state)

    @inlineCallbacks
    def test_loadSupervisorServiceState_fatal_returns_dead(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        supervisor_status_output = (
            dedent(
                """\
            %s              FATAL   Failed to start
            """
            )
            % (service.snap_service_name)
        )

        mock_execSupervisorServiceAction = self.patch(
            service_monitor, "_execSupervisorServiceAction"
        )
        mock_execSupervisorServiceAction.return_value = (
            1,
            supervisor_status_output,
            "",
        )
        active_state, process_state = yield (
            service_monitor._loadSupervisorServiceState(service)
        )
        self.assertEqual(SERVICE_STATE.DEAD, active_state)
        self.assertEqual("Result: exit-code", process_state)

    @inlineCallbacks
    def test_loadSupervisorServiceState_exited_returns_dead(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        supervisor_status_output = (
            dedent(
                """\
            %s              EXITED   Quit to early
            """
            )
            % (service.snap_service_name)
        )

        mock_execSupervisorServiceAction = self.patch(
            service_monitor, "_execSupervisorServiceAction"
        )
        mock_execSupervisorServiceAction.return_value = (
            2,
            supervisor_status_output,
            "",
        )
        active_state, process_state = yield (
            service_monitor._loadSupervisorServiceState(service)
        )
        self.assertEqual(SERVICE_STATE.DEAD, active_state)
        self.assertEqual("Result: exit-code", process_state)

    @inlineCallbacks
    def test_loadSupervisorServiceState_backoff_returns_dead(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        supervisor_status_output = (
            dedent(
                """\
            %s              BACKOFF   Respawning too fast
            """
            )
            % (service.snap_service_name)
        )

        mock_execSupervisorServiceAction = self.patch(
            service_monitor, "_execSupervisorServiceAction"
        )
        mock_execSupervisorServiceAction.return_value = (
            1,
            supervisor_status_output,
            "",
        )
        active_state, process_state = yield (
            service_monitor._loadSupervisorServiceState(service)
        )
        self.assertEqual(SERVICE_STATE.DEAD, active_state)
        self.assertEqual("Result: exit-code", process_state)

    @inlineCallbacks
    def test_ensureService_logs_warning_in_mismatch_process_state(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])

        invalid_process_state = factory.make_name("invalid_state")
        mock_getServiceState = self.patch(service_monitor, "getServiceState")
        mock_getServiceState.return_value = succeed(
            ServiceState(SERVICE_STATE.ON, invalid_process_state)
        )

        with FakeLogger(
            "maas.service_monitor", level=logging.WARNING
        ) as maaslog:
            yield service_monitor._ensureService(service)
        self.assertDocTestMatches(
            "Service '%s' is %s but not in the expected state of "
            "'%s', its current state is '%s'."
            % (
                service.service_name,
                SERVICE_STATE.ON.value,
                service_monitor.PROCESS_STATE[SERVICE_STATE.ON],
                invalid_process_state,
            ),
            maaslog.output,
        )

    @inlineCallbacks
    def test_ensureService_logs_debug_in_expected_states(self):
        state = SERVICE_STATE.ON
        service = make_fake_service(state)
        service_monitor = self.make_service_monitor([service])

        expected_process_state = service_monitor.PROCESS_STATE[state]
        mock_getServiceState = self.patch(service_monitor, "getServiceState")
        mock_getServiceState.return_value = succeed(
            ServiceState(SERVICE_STATE.ON, expected_process_state)
        )

        log = self.patch(service_monitor_module, "log")
        yield service_monitor._ensureService(service)
        log.debug.assert_called_once_with(
            "Service '{name}' is {state} and '{process}'.",
            name=service.service_name,
            state=state,
            process=expected_process_state,
        )

    @inlineCallbacks
    def test_ensureService_allows_dead_for_off_service(self):
        service = make_fake_service(SERVICE_STATE.OFF)
        service_monitor = self.make_service_monitor([service])

        mock_getServiceState = self.patch(service_monitor, "getServiceState")
        mock_getServiceState.return_value = succeed(
            ServiceState(SERVICE_STATE.DEAD, "Result: exit-code")
        )

        log = self.patch(service_monitor_module, "log")
        yield service_monitor._ensureService(service)
        log.debug.assert_called_once_with(
            "Service '{name}' is {state} and '{process}'.",
            name=service.service_name,
            state=SERVICE_STATE.DEAD,
            process="Result: exit-code",
        )

    @inlineCallbacks
    def test_ensureService_logs_mismatch_for_dead_process_state(self):
        service = make_fake_service(SERVICE_STATE.OFF)
        service_monitor = self.make_service_monitor([service])

        invalid_process_state = factory.make_name("invalid")
        mock_getServiceState = self.patch(service_monitor, "getServiceState")
        mock_getServiceState.return_value = succeed(
            ServiceState(SERVICE_STATE.DEAD, invalid_process_state)
        )

        with FakeLogger(
            "maas.service_monitor", level=logging.WARNING
        ) as maaslog:
            yield service_monitor._ensureService(service)
        self.assertDocTestMatches(
            "Service '%s' is %s but not in the expected state of "
            "'%s', its current state is '%s'."
            % (
                service.service_name,
                SERVICE_STATE.DEAD.value,
                service_monitor.PROCESS_STATE[SERVICE_STATE.DEAD],
                invalid_process_state,
            ),
            maaslog.output,
        )

    @inlineCallbacks
    def test_ensureService_performs_start_for_off_service(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])

        mock_getServiceState = self.patch(service_monitor, "getServiceState")
        mock_getServiceState.side_effect = [
            succeed(ServiceState(SERVICE_STATE.OFF, "waiting")),
            succeed(ServiceState(SERVICE_STATE.ON, "running")),
        ]
        mock_performServiceAction = self.patch(
            service_monitor, "_performServiceAction"
        )
        mock_performServiceAction.return_value = succeed(None)

        with FakeLogger("maas.service_monitor", level=logging.INFO) as maaslog:
            yield service_monitor._ensureService(service)
        mock_performServiceAction.assert_called_once_with(service, "start")
        self.assertDocTestMatches(
            """\
            Service '%s' is not on, it will be started.
            Service '%s' has been started and is 'running'.
            """
            % (service.service_name, service.service_name),
            maaslog.output,
        )

    @inlineCallbacks
    def test_ensureService_performs_stop_for_on_service(self):
        service = make_fake_service(SERVICE_STATE.OFF)
        service_monitor = self.make_service_monitor([service])

        mock_getServiceState = self.patch(service_monitor, "getServiceState")
        mock_getServiceState.side_effect = [
            succeed(ServiceState(SERVICE_STATE.ON, "running")),
            succeed(ServiceState(SERVICE_STATE.OFF, "waiting")),
        ]
        mock_performServiceAction = self.patch(
            service_monitor, "_performServiceAction"
        )
        mock_performServiceAction.return_value = succeed(None)

        with FakeLogger("maas.service_monitor", level=logging.INFO) as maaslog:
            yield service_monitor._ensureService(service)
        mock_performServiceAction.assert_called_once_with(service, "stop")
        self.assertDocTestMatches(
            """\
            Service '%s' is not off, it will be stopped.
            Service '%s' has been stopped and is 'waiting'.
            """
            % (service.service_name, service.service_name),
            maaslog.output,
        )

    @inlineCallbacks
    def test_ensureService_performs_raises_ServiceActionError(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])

        mock_getServiceState = self.patch(service_monitor, "getServiceState")
        mock_getServiceState.side_effect = [
            succeed(ServiceState(SERVICE_STATE.OFF, "waiting")),
            succeed(ServiceState(SERVICE_STATE.OFF, "waiting")),
        ]
        mock_performServiceAction = self.patch(
            service_monitor, "_performServiceAction"
        )
        mock_performServiceAction.return_value = succeed(None)

        with ExpectedException(ServiceActionError):
            with FakeLogger(
                "maas.service_monitor", level=logging.INFO
            ) as maaslog:
                yield service_monitor._ensureService(service)
        self.assertDocTestMatches(
            """\
            Service '%s' is not on, it will be started.
            Service '%s' failed to start. Its current state is '%s' and '%s'.
            """
            % (
                service.service_name,
                service.service_name,
                SERVICE_STATE.OFF.value,
                "waiting",
            ),
            maaslog.output,
        )

    @inlineCallbacks
    def test_ensureService_does_nothing_when_any_state_expected(self):
        service = make_fake_service(SERVICE_STATE.ANY)
        service_monitor = self.make_service_monitor([service])

        self.patch_autospec(service_monitor, "getServiceState")
        self.patch_autospec(service_monitor, "_performServiceAction")

        self.assertEqual(
            (yield service_monitor._ensureService(service)),
            ServiceState(SERVICE_STATE.UNKNOWN),
        )
        service_monitor.getServiceState.assert_not_called()
        service_monitor._performServiceAction.assert_not_called()


class TestToggleableService(MAASTestCase):
    def make_toggleable_service(self):
        class FakeToggleableService(ToggleableService):
            name = factory.make_name("name")
            service_name = factory.make_name("service")
            snap_service_name = factory.make_name("service")

        return FakeToggleableService()

    def test_expected_state_starts_off(self):
        service = self.make_toggleable_service()
        self.assertEqual(SERVICE_STATE.OFF, service.expected_state)

    def test_getExpectedState_returns_from_expected_state_and_reason(self):
        service = self.make_toggleable_service()
        service.expected_state = sentinel.state
        service.expected_state_reason = sentinel.reason
        self.assertEqual(
            (sentinel.state, sentinel.reason), service.getExpectedState()
        )

    def test_is_on_returns_True_when_expected_state_on(self):
        service = self.make_toggleable_service()
        service.expected_state = SERVICE_STATE.ON
        self.assertTrue(
            service.is_on(), "Did not return true when expected_state was on."
        )

    def test_is_on_returns_False_when_expected_state_off(self):
        service = self.make_toggleable_service()
        service.expected_state = SERVICE_STATE.OFF
        self.assertFalse(
            service.is_on(),
            "Did not return false when expected_state was off.",
        )

    def test_on_sets_expected_state_to_on(self):
        service = self.make_toggleable_service()
        service.expected_state = SERVICE_STATE.OFF
        service.on(sentinel.reason)
        self.assertEqual(SERVICE_STATE.ON, service.expected_state)
        self.assertEqual(sentinel.reason, service.expected_state_reason)

    def test_off_sets_expected_state_to_off(self):
        service = self.make_toggleable_service()
        service.expected_state = SERVICE_STATE.ON
        service.off(sentinel.reason)
        self.assertEqual(SERVICE_STATE.OFF, service.expected_state)
        self.assertEqual(sentinel.reason, service.expected_state_reason)
