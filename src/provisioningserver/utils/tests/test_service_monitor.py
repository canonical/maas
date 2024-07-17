# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.service_monitor`."""
import json
from json import JSONDecodeError
import logging
import os
import random
from textwrap import dedent
from unittest.mock import MagicMock, Mock, sentinel

from fixtures import FakeLogger
from testscenarios import multiply_scenarios
from twisted.internet import reactor
from twisted.internet.defer import (
    CancelledError,
    DeferredLock,
    fail,
    inlineCallbacks,
    succeed,
)
from twisted.internet.interfaces import IConsumer
from twisted.internet.task import deferLater
from twisted.web._newclient import Response
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from zope.interface import implementer

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
        # Snap always uses pebble
        self.patch(
            service_monitor_module, "_running_under_pebble"
        ).return_value = True
        self.patch(os, "environ", {"PEBBLE": "/snap/data/pebble"})

    def make_service_monitor(self, fake_services=None, pebble_agent=None):
        if fake_services is None:
            fake_services = [make_fake_service() for _ in range(3)]
        return ServiceMonitor(*fake_services, pebble_agent=pebble_agent)

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
        self.patch(service_monitor, "ensureService").side_effect = (
            lambda name: succeed(expected_states[name])
        )
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
        with self.assertRaisesRegex(
            ServiceNotOnError,
            rf"Service '{fake_service.service_name}' is not expected to be on, unable to restart\.",
        ):
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
        with self.assertRaisesRegex(
            ServiceActionError,
            rf"Service '{fake_service.service_name}' failed to restart",
        ):
            yield service_monitor.restartService(fake_service.name)

    @inlineCallbacks
    def test_reloadService_raises_ServiceNotOnError(self):
        fake_service = make_fake_service(SERVICE_STATE.OFF)
        service_monitor = self.make_service_monitor([fake_service])
        with self.assertRaisesRegex(
            ServiceNotOnError,
            rf"Service '{fake_service.service_name}' is not expected to be on, unable to reload\.",
        ):
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
        with self.assertRaisesRegex(
            ServiceActionError,
            rf"Service '{fake_service.service_name}' is not running and could not be started to perform the reload",
        ):
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
        with self.assertRaisesRegex(
            ServiceActionError,
            rf"Service '{fake_service.service_name}' is not running and could not be started to perform the reload",
        ):
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
        with self.assertRaisesRegex(
            ServiceActionError, "^Service monitor timed out after"
        ):
            yield monitor._execCmd(
                ["sleep", "0.01"], {}, timeout=0.001, retries=1
            )
        # Pause long enough for the reactor to cleanup the process.
        yield pause(0.03)

    @inlineCallbacks
    def test_execCmd_retries(self):
        monitor = ServiceMonitor(make_fake_service())
        mock_deferWithTimeout = self.patch(
            service_monitor_module, "deferWithTimeout"
        )
        mock_deferWithTimeout.side_effect = always_fail_with(CancelledError())
        with self.assertRaisesRegex(
            ServiceActionError, "^Service monitor timed out after"
        ):
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
    def test_execPebbleServiceAction_calls_pebble_api(self):
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        action = "start"
        mock_pebble_request = self.patch(service_monitor, "_pebble_request")
        mock_pebble_request.return_value = succeed({})
        result = yield service_monitor._execPebbleServiceAction(
            service_name, action
        )
        mock_pebble_request.assert_called_once_with(
            # The environment contains LC_ALL and LANG too.
            "POST",
            "/v1/services",
            payload={"action": action, "services": [service_name]},
        )
        self.assertEqual((0, None, None), result)

    @inlineCallbacks
    def test_execPebbleServiceAction_turns_kill_to_stop(self):
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        mock_pebble_request = self.patch(service_monitor, "_pebble_request")

        mock_pebble_request.return_value = succeed({})
        yield service_monitor._execPebbleServiceAction(service_name, "kill")
        mock_pebble_request.assert_called_once_with(
            # The environment contains LC_ALL and LANG too.
            "POST",
            "/v1/services",
            payload={"action": "stop", "services": [service_name]},
        )

    @inlineCallbacks
    def test_execPebbleServiceAction_raises_on_unsupported_action(self):
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        action = factory.make_name("action")
        with self.assertRaisesRegex(
            ValueError, f"^Unknown pebble action '{action}'$"
        ):
            yield service_monitor._execPebbleServiceAction(
                service_name, action
            )

    @inlineCallbacks
    def test_execPebbleServiceAction_service_performs_valid_get_request(self):
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        mock_pebble_request = self.patch(service_monitor, "_pebble_request")

        mock_pebble_request.return_value = succeed(
            {"result": {"name": service_name, "current": "active"}}
        )
        yield service_monitor._execPebbleServiceAction(
            service_name, "services"
        )
        mock_pebble_request.assert_called_once_with(
            "GET",
            f"/v1/services?names={service_name}",
            payload={},
        )

    @inlineCallbacks
    def test_execPebbleServiceAction_reload_sends_sighup(self):
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        mock_pebble_request = self.patch(service_monitor, "_pebble_request")

        mock_pebble_request.return_value = succeed({})
        yield service_monitor._execPebbleServiceAction(service_name, "reload")
        mock_pebble_request.assert_called_once_with(
            "POST",
            "/v1/signals",
            payload={"signal": "SIGHUP", "services": [service_name]},
        )

    @inlineCallbacks
    def test_execPebbleServiceAction_signal_sends_signal(self):
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        mock_pebble_request = self.patch(service_monitor, "_pebble_request")

        mock_pebble_request.return_value = succeed({})
        signal = "SIGWHATEVER"
        yield service_monitor._execPebbleServiceAction(
            service_name, "signal", extra_opts=[signal]
        )
        mock_pebble_request.assert_called_once_with(
            "POST",
            "/v1/signals",
            payload={"signal": signal, "services": [service_name]},
        )

    @inlineCallbacks
    def test_execPebbleServiceAction_signal_raises_on_multiple_signals(self):
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        mock_pebble_request = self.patch(service_monitor, "_pebble_request")

        mock_pebble_request.return_value = succeed({})
        with self.assertRaisesRegex(
            ValueError, "^Multiple signal names provided$"
        ):
            yield service_monitor._execPebbleServiceAction(
                service_name,
                "signal",
                extra_opts=["SIGWHATEVER", "SIGANYTHING"],
            )

    @inlineCallbacks
    def test_execPebbleServiceAction_signal_raises_when_no_extra_opts_provided(
        self,
    ):
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        mock_pebble_request = self.patch(service_monitor, "_pebble_request")

        mock_pebble_request.return_value = succeed({})
        with self.assertRaisesRegex(
            ValueError,
            r"^Provide signal name in 'SIG\.\*' format in extra_opts$",
        ):
            yield service_monitor._execPebbleServiceAction(
                service_name, "signal"
            )
        mock_pebble_request.assert_not_called()

    @inlineCallbacks
    def test_execPebbleServiceAction_signal_raises_when_no_signals_found_in_extra_opts(
        self,
    ):
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        mock_pebble_request = self.patch(service_monitor, "_pebble_request")

        mock_pebble_request.return_value = succeed({})
        with self.assertRaisesRegex(
            ValueError,
            r"^Provide signal name in 'SIG\.\*' format in extra_opts$",
        ):
            yield service_monitor._execPebbleServiceAction(
                service_name, "signal", extra_opts=["AAAA", "BBBB"]
            )
        mock_pebble_request.assert_not_called()

    @inlineCallbacks
    def test_execPebbleServiceAction_waits_for_change_to_be_ready(self):
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        mock_pebble_request = self.patch(service_monitor, "_pebble_request")

        def pebble_request_side_effect(method, endpoint, payload=None):
            if method == "GET" and endpoint.startswith("/v1/changes"):
                return succeed({"result": {"status": "Done", "ready": True}})
            elif (
                method == "POST"
                and endpoint.startswith("/v1/services")
                and payload
                and payload["action"] == "start"
            ):
                return succeed({"type": "async", "change": 42})
            else:
                raise AssertionError(
                    f"Unexpected request: {method} {endpoint} {payload}"
                )

        mock_pebble_request.side_effect = pebble_request_side_effect
        yield service_monitor._execPebbleServiceAction(service_name, "start")
        self.assertEqual(2, len(mock_pebble_request.mock_calls))

    @inlineCallbacks
    def test_execPebbleServiceAction_raises_errors_predictably(self):
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        mock_pebble_request = self.patch(service_monitor, "_pebble_request")

        error = "TEST"
        mock_pebble_request.side_effect = [fail(ValueError(error))]
        result = yield service_monitor._execPebbleServiceAction(
            service_name, "start"
        )
        self.assertEqual((1, None, error), result)

    @inlineCallbacks
    def test_execPebbleServiceAction_wait_on_change_raises_when_no_change_id_present(
        self,
    ):
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        action = "start"
        mock_pebble_request = self.patch(service_monitor, "_pebble_request")
        mock_pebble_request.return_value = succeed({"type": "async"})
        code, output, error = yield service_monitor._execPebbleServiceAction(
            service_name, action
        )
        self.assertEqual(1, code)
        self.assertIsNone(output)
        self.assertEqual(
            "Expected to have change id in async request response", error
        )

    @inlineCallbacks
    def test_execPebbleServiceAction_extract_service_status_raises_when_no_results(
        self,
    ):
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        action = "services"
        mock_pebble_request = self.patch(service_monitor, "_pebble_request")
        mock_pebble_request.return_value = succeed({"result": []})
        code, output, error = yield service_monitor._execPebbleServiceAction(
            service_name, action
        )
        self.assertEqual(1, code)
        self.assertIsNone(output)
        self.assertEqual(
            "Expected at least one result in services request response", error
        )

    @inlineCallbacks
    def test_pebble_request_generates_valid_post_requests(self):
        mock_agent = MagicMock(Agent)
        service_monitor = self.make_service_monitor(pebble_agent=mock_agent)
        mock_response = MagicMock(Response)
        mock_response.code = 200
        mock_response.phrase = "OK"
        mock_agent.request.return_value = succeed(mock_response)
        mock_read_body = self.patch(service_monitor_module, "readBody")
        mock_read_body.return_value = succeed(b"{}")

        method = "POST"
        endpoint = "/endpoint"
        body = {"payload": "is_present", "boolean": False}

        yield service_monitor._pebble_request(method, endpoint, body)
        mock_agent.request.assert_called()
        call_args = mock_agent.mock_calls[0].args
        self.assertEqual(b"POST", call_args[0])
        self.assertEqual(b"unix://localhost/endpoint", call_args[1])
        self.assertEqual(
            Headers({"Content-Type": ["application/json"]}), call_args[2]
        )

        consumed = b""

        @implementer(IConsumer)
        class Consumer:
            def write(self, d):
                nonlocal consumed
                consumed += d

        yield call_args[3].startProducing(Consumer())
        self.assertEqual(body, json.loads(consumed.decode("utf-8")))

    @inlineCallbacks
    def test_pebble_request_generates_valid_get_requests(self):
        mock_agent = MagicMock(Agent)
        service_monitor = self.make_service_monitor(pebble_agent=mock_agent)
        mock_response = MagicMock(Response)
        mock_response.code = 200
        mock_response.phrase = "OK"
        mock_agent.request.return_value = succeed(mock_response)
        mock_read_body = self.patch(service_monitor_module, "readBody")
        mock_read_body.return_value = succeed(b"{}")

        yield service_monitor._pebble_request("GET", "/")
        mock_agent.request.assert_called()
        call_args = mock_agent.mock_calls[0].args
        self.assertEqual(b"GET", call_args[0])
        self.assertEqual(b"unix://localhost/", call_args[1])
        self.assertIsNone(call_args[2])
        self.assertIsNone(call_args[3])

    @inlineCallbacks
    def test_pebble_request_raises_for_endpoint_not_starting_with_slash(self):
        mock_agent = MagicMock(Agent)
        service_monitor = self.make_service_monitor(pebble_agent=mock_agent)

        with self.assertRaisesRegex(
            ValueError, "Pebble endpoint does not start with '/'"
        ):
            yield service_monitor._pebble_request("GET", "endpoint")
        mock_agent.request.assert_not_called()

    @inlineCallbacks
    def test_pebble_request_raises_on_non_2xx_code(self):
        mock_agent = MagicMock(Agent)
        mock_response = MagicMock(Response)
        mock_response.code = 400
        mock_response.phrase = "Bad Request"
        mock_response.body = b"{}"
        mock_agent.request.return_value = succeed(mock_response)
        service_monitor = self.make_service_monitor(pebble_agent=mock_agent)

        with self.assertRaisesRegex(
            ValueError, "Unexpected pebble response code"
        ):
            yield service_monitor._pebble_request("GET", "/400")

    @inlineCallbacks
    def test_pebble_request_deserializes_json(self):
        mock_agent = MagicMock(Agent)
        mock_response = MagicMock(Response)
        mock_response.code = 200
        mock_agent.request.return_value = succeed(mock_response)
        mock_read_body = self.patch(service_monitor_module, "readBody")
        mock_read_body.return_value = succeed(b'{"what": "ever"}')
        service_monitor = self.make_service_monitor(pebble_agent=mock_agent)

        result = yield service_monitor._pebble_request("GET", "/json")
        self.assertEqual({"what": "ever"}, result)

    @inlineCallbacks
    def test_pebble_request_raises_on_non_json_deserialisable_responses(self):
        mock_agent = MagicMock(Agent)
        mock_response = MagicMock(Response)
        mock_response.code = 200
        mock_agent.request.return_value = succeed(mock_response)
        mock_read_body = self.patch(service_monitor_module, "readBody")
        mock_read_body.return_value = succeed(b"OK!")
        service_monitor = self.make_service_monitor(pebble_agent=mock_agent)

        with self.assertRaisesRegex(
            JSONDecodeError, r"^Expecting value: line 1 column 1 \(char 0\)$"
        ):
            yield service_monitor._pebble_request("GET", "/")

    def test_service_monitor_creates_agent_if_not_provided(self):
        service_monitor = self.make_service_monitor()
        self.assertIsNotNone(service_monitor._agent)

    def test_pebble_create_agent_creates_correct_snap_agent(self):
        """Checks whether snap paths are used by _pebble_create_agents in snap env"""
        self.run_under_snap()
        paths = SnapPaths(
            snap="/snap/base", data="/snap/data", common="/snap/common"
        )
        self.patch(snap.SnapPaths, "from_environ").return_value = paths
        service_monitor = self.make_service_monitor()
        agent = service_monitor._pebble_create_agent()

        self.assertIsInstance(
            agent._endpointFactory,
            service_monitor_module.UnixClientEndpointFactory,
        )
        self.assertEqual(
            os.path.join(paths.data, "pebble", ".pebble.socket"),
            agent._endpointFactory._socket_path,
        )

    def test_pebble_create_agent_creates_correct_agent_from_pebble_env_vars(
        self,
    ):
        """Checks whether $PEBBLE is used by _pebble_create_agents in non-snap env"""
        env = {
            "PEBBLE": "/var/run/pebble",
        }
        self.patch(os, "environ", env)
        service_monitor = self.make_service_monitor()
        agent = service_monitor._pebble_create_agent()

        self.assertIsInstance(
            agent._endpointFactory,
            service_monitor_module.UnixClientEndpointFactory,
        )
        self.assertEqual(
            os.path.join(env["PEBBLE"], ".pebble.socket"),
            agent._endpointFactory._socket_path,
        )

    def test_pebble_create_agent_prioritises_pebble_socket_envvar_over_pebble(
        self,
    ):
        """Checks whether $PEBBLE_SOCKET has priority over $PEBBLE in _pebble_create_agents in non-snap env"""
        env = {
            "PEBBLE": "/var/run/pebble",
            "PEBBLE_SOCKET": "/any/other/path/to/pebble/.socket",
        }
        self.patch(os, "environ", env)
        service_monitor = self.make_service_monitor()
        agent = service_monitor._pebble_create_agent()

        self.assertIsInstance(
            agent._endpointFactory,
            service_monitor_module.UnixClientEndpointFactory,
        )
        self.assertEqual(
            env["PEBBLE_SOCKET"], agent._endpointFactory._socket_path
        )

    @inlineCallbacks
    def test_pebble_wait_on_change_monitors_changes(self):
        service_monitor = self.make_service_monitor()
        mock_pebble_request = self.patch(service_monitor, "_pebble_request")

        change_id = 42
        request_count = 0

        def pebble_request_side_effect(
            method, endpoint, payload=None, agent=None
        ):
            nonlocal request_count
            if method == "GET" and endpoint == f"/v1/changes/{change_id}":
                request_count += 1
                if request_count == 1:
                    return succeed(
                        {"result": {"status": "Doing", "ready": False}}
                    )
                else:
                    return succeed(
                        {"result": {"status": "Done", "ready": True}}
                    )
            else:
                raise AssertionError(
                    f"Unexpected request: {method} {endpoint} {payload}"
                )

        mock_pebble_request.side_effect = pebble_request_side_effect
        yield service_monitor._pebble_wait_on_change(change_id, backoff=0)
        self.assertEqual(2, len(mock_pebble_request.mock_calls))

    @inlineCallbacks
    def test_pebble_wait_on_change_handles_error_status(self):
        service_monitor = self.make_service_monitor()
        mock_pebble_request = self.patch(service_monitor, "_pebble_request")
        change_id = 42
        error = "Test"
        mock_pebble_request.return_value = succeed(
            {"result": {"status": "Error", "ready": True, "err": error}}
        )
        with self.assertRaisesRegex(
            ValueError,
            f"Pebble change {change_id} failed with an error: {error}",
        ):
            yield service_monitor._pebble_wait_on_change(change_id, backoff=0)

    @inlineCallbacks
    def test_pebble_wait_on_change_handles_hold_status(self):
        service_monitor = self.make_service_monitor()
        mock_pebble_request = self.patch(service_monitor, "_pebble_request")
        change_id = 42
        mock_pebble_request.return_value = succeed(
            {"result": {"status": "Hold", "ready": True}}
        )
        with self.assertRaisesRegex(
            ValueError, f"Pebble change {change_id} is on hold"
        ):
            yield service_monitor._pebble_wait_on_change(change_id, backoff=0)

    @inlineCallbacks
    def test_pebble_wait_on_change_handles_undone_status(self):
        service_monitor = self.make_service_monitor()
        mock_pebble_request = self.patch(service_monitor, "_pebble_request")
        change_id = 42
        mock_pebble_request.return_value = succeed(
            {"result": {"status": "Undone", "ready": True}}
        )
        with self.assertRaisesRegex(
            ValueError, f"Pebble change {change_id} is undone"
        ):
            yield service_monitor._pebble_wait_on_change(change_id, backoff=0)

    @inlineCallbacks
    def test_pebble_wait_on_change_handles_unknown_error_status(self):
        service_monitor = self.make_service_monitor()
        mock_pebble_request = self.patch(service_monitor, "_pebble_request")
        change_id = 42
        error = "Test"
        status = "ImNotPebble"
        mock_pebble_request.return_value = succeed(
            {"result": {"status": status, "ready": True, "err": error}}
        )
        with self.assertRaisesRegex(
            ValueError,
            f"Pebble change {change_id} finished with unknown error status `{status}`: {error}",
        ):
            yield service_monitor._pebble_wait_on_change(change_id, backoff=0)

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
    def test_performServiceAction_holds_lock_perform_pebble_action(self):
        self.run_under_snap()
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor()
        service_locks = service_monitor._serviceLocks
        service_lock = service_locks[service.name]
        service_lock = service_locks[service.name] = Mock(wraps=service_lock)
        mock_execPebbleServiceAction = self.patch(
            service_monitor, "_execPebbleServiceAction"
        )
        mock_execPebbleServiceAction.return_value = (0, "", "")
        action = "start"
        extra_opts = ("--option", factory.make_name("option"))
        setattr(service, "%s_extra_opts" % action, extra_opts)
        yield service_monitor._performServiceAction(service, action)
        service_lock.run.assert_called_once_with(
            service_monitor._execPebbleServiceAction,
            service.service_name,
            action,
            extra_opts=extra_opts,
        )
        mock_execPebbleServiceAction.assert_called_once_with(
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
        with self.assertRaisesRegex(
            ServiceActionError,
            f"^Service '{service.name}' failed to {action}: $",
        ):
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
            with self.assertRaisesRegex(
                ServiceActionError,
                f"^Service '{service.name}' failed to {action}: {error_output}$",
            ):
                yield service_monitor._performServiceAction(service, action)

        self.assertEqual(
            f"Service '{service.name}' failed to {action}: {error_output}\n",
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

    @inlineCallbacks
    def test_loadServiceState_uses_pebble(self):
        self.patch(
            service_monitor_module, "_running_under_pebble"
        ).return_value = True
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        mock_loadPebbleServiceState = self.patch(
            service_monitor, "_loadPebbleServiceState"
        )
        mock_loadPebbleServiceState.return_value = sentinel.result
        result = yield service_monitor._loadServiceState(service)
        self.assertEqual(sentinel.result, result)

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
        with self.assertRaisesRegex(
            ServiceUnknownError,
            rf"^'{service.service_name}' is unknown to systemd\.$",
        ):
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

        with self.assertRaisesRegex(
            ServiceParsingError,
            rf"^Unable to parse the active state from systemd for service '{service.service_name}', active state reported as 'unknown'\.$",
        ):
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

        with self.assertRaisesRegex(
            ServiceParsingError,
            rf"^Unable to parse the output from systemd for service '{service.service_name}'\.$",
        ):
            yield service_monitor._loadSystemDServiceState(service)

    @inlineCallbacks
    def test_loadPebbleServiceState_status_calls_pebble_socket(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        mock_execPebbleServiceAction = self.patch(
            service_monitor, "_execPebbleServiceAction"
        )
        mock_execPebbleServiceAction.side_effect = factory.make_exception()
        try:
            yield service_monitor._loadPebbleServiceState(service)
        except Exception:
            pass
        mock_execPebbleServiceAction.assert_called_once_with(
            service.service_name, "services"
        )

    @inlineCallbacks
    def test_loadPebbleServiceState_service_name_doesnt_match(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor()
        mock_execPebbleServiceAction = self.patch(
            service_monitor, "_execPebbleServiceAction"
        )
        mock_execPebbleServiceAction.return_value = (
            0,
            "any_service active",
            "",
        )
        with self.assertRaisesRegex(
            ServiceParsingError,
            f"Pebble returned status for 'any_service' instead of '{service.service_name}'$",
        ):
            yield service_monitor._loadPebbleServiceState(service)

    @inlineCallbacks
    def test_loadPebbleServiceState_unknown_status(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor()
        mock_execPebbleServiceAction = self.patch(
            service_monitor, "_execPebbleServiceAction"
        )
        mock_execPebbleServiceAction.return_value = (
            0,
            f"{service.snap_service_name} unknown_status_for_maas",
            "",
        )
        with self.assertRaisesRegex(
            ServiceParsingError,
            "Pebble returned status as 'unknown_status_for_maas'",
        ):
            yield service_monitor._loadPebbleServiceState(service)

    @inlineCallbacks
    def test_loadPebbleServiceState_active_returns_on(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])

        mock_execPebbleServiceAction = self.patch(
            service_monitor, "_execPebbleServiceAction"
        )
        mock_execPebbleServiceAction.return_value = (
            0,
            f"{service.snap_service_name} active",
            "",
        )
        active_state, process_state = yield (
            service_monitor._loadPebbleServiceState(service)
        )
        self.assertEqual(SERVICE_STATE.ON, active_state)
        self.assertEqual("running", process_state)

    @inlineCallbacks
    def test_loadPebbleServiceState_inactive_returns_off(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])

        mock_execPebbleServiceAction = self.patch(
            service_monitor, "_execPebbleServiceAction"
        )
        mock_execPebbleServiceAction.return_value = (
            0,
            f"{service.snap_service_name} inactive",
            "",
        )
        active_state, process_state = yield (
            service_monitor._loadPebbleServiceState(service)
        )
        self.assertEqual(SERVICE_STATE.OFF, active_state)
        self.assertEqual("dead", process_state)

    @inlineCallbacks
    def test_loadPebbleServiceState_backoff_returns_dead(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])

        mock_execPebbleServiceAction = self.patch(
            service_monitor, "_execPebbleServiceAction"
        )
        mock_execPebbleServiceAction.return_value = (
            0,
            f"{service.snap_service_name} backoff",
            "",
        )
        active_state, process_state = yield (
            service_monitor._loadPebbleServiceState(service)
        )
        self.assertEqual(SERVICE_STATE.DEAD, active_state)
        self.assertEqual("Result: exit-code", process_state)

    @inlineCallbacks
    def test_loadPebbleServiceState_error_returns_dead(self):
        service = make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])

        mock_execPebbleServiceAction = self.patch(
            service_monitor, "_execPebbleServiceAction"
        )
        mock_execPebbleServiceAction.return_value = (
            0,
            f"{service.snap_service_name} error",
            "",
        )
        active_state, process_state = yield (
            service_monitor._loadPebbleServiceState(service)
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
        self.assertEqual(
            f"Service '{service.service_name}' is on but not in the expected state of 'running', "
            f"its current state is '{invalid_process_state}'.\n",
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
        self.assertEqual(
            f"Service '{service.service_name}' is dead but not in the expected state of 'Result: exit-code', "
            f"its current state is '{invalid_process_state}'.\n",
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
        self.assertEqual(
            (
                f"Service '{service.service_name}' is not on, it will be started.\n"
                f"Service '{service.service_name}' has been started and is 'running'.\n"
            ),
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
        self.assertEqual(
            (
                f"Service '{service.service_name}' is not off, it will be stopped.\n"
                f"Service '{service.service_name}' has been stopped and is 'waiting'.\n"
            ),
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

        with self.assertRaisesRegex(
            ServiceActionError,
            rf"^Service '{service.service_name}' failed to start\.",
        ):
            with FakeLogger(
                "maas.service_monitor", level=logging.INFO
            ) as maaslog:
                yield service_monitor._ensureService(service)
        self.assertIn(
            f"Service '{service.service_name}' is not on, it will be started.",
            maaslog.output,
        )
        self.assertIn(
            f"Service '{service.service_name}' failed to start. Its current state is 'off' and 'waiting'.",
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
