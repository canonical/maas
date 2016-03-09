# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.service_monitor`."""

__all__ = []

import logging
import random
from textwrap import dedent

from fixtures import FakeLogger
from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from mock import Mock
from provisioningserver.utils import service_monitor as service_monitor_module
from provisioningserver.utils.service_monitor import (
    Service,
    SERVICE_STATE,
    ServiceActionError,
    ServiceMonitor,
    ServiceNotOnError,
    ServiceParsingError,
    ServiceState,
    ServiceUnknownError,
)
from testtools import ExpectedException
from testtools.matchers import Equals
from twisted.internet.defer import (
    DeferredLock,
    fail,
    inlineCallbacks,
    succeed,
)
from twisted.internet.threads import deferToThread


class TestServiceMonitor(MAASTestCase):
    """Tests for `ServiceMonitor`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def make_fake_service(self, expected_state=None):
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

            def get_expected_state(self):
                return succeed(expected_state)

        return FakeService()

    def make_service_monitor(self, fake_services=None):
        if fake_services is None:
            fake_services = [
                self.make_fake_service()
                for _ in range(3)
            ]
        return ServiceMonitor(*fake_services)

    @inlineCallbacks
    def test___getServiceLock_returns_lock_for_service(self):
        service_monitor = self.make_service_monitor()
        name = factory.make_name("service")
        lock = yield service_monitor._getServiceLock(name)
        self.assertIsInstance(lock, DeferredLock)

    @inlineCallbacks
    def test___getServiceLock_uses_shared_lock(self):
        service_monitor = self.make_service_monitor()
        service_shared_lock = self.patch(service_monitor, "_lock")
        service_shared_lock.acquire.return_value = succeed(
            service_shared_lock)
        name = factory.make_name("service")
        yield service_monitor._getServiceLock(name)
        self.assertThat(
            service_shared_lock.acquire, MockCalledOnceWith())
        self.assertThat(
            service_shared_lock.release, MockCalledOnceWith())

    def test__getServiceByName_returns_service(self):
        fake_service = self.make_fake_service()
        service_monitor = self.make_service_monitor([fake_service])
        self.assertEquals(
            fake_service,
            service_monitor.getServiceByName(fake_service.name))

    def test__getServiceByName_raises_ServiceUnknownError(self):
        service_monitor = self.make_service_monitor()
        self.assertRaises(
            ServiceUnknownError,
            service_monitor.getServiceByName, factory.make_name("service"))

    @inlineCallbacks
    def test__updateServiceState_updates_stored_service_state(self):
        service_monitor = self.make_service_monitor()
        name = factory.make_name("service")
        active_state = factory.pick_enum(SERVICE_STATE)
        process_state = random.choice(["running", "dead"])
        observered_state = yield service_monitor._updateServiceState(
            name, active_state, process_state)
        state = service_monitor._serviceStates[name]
        self.assertEquals(
            (active_state, process_state),
            (state.active_state, state.process_state))
        self.assertEquals(state, observered_state)

    @inlineCallbacks
    def test__updateServiceState_holds_service_lock(self):
        service_monitor = self.make_service_monitor()
        service_lock = Mock()
        service_lock.acquire.return_value = succeed(service_lock)
        self.patch(
            service_monitor,
            "_getServiceLock").return_value = succeed(service_lock)
        name = factory.make_name("service")
        active_state = factory.pick_enum(SERVICE_STATE)
        process_state = random.choice(["running", "dead"])
        yield service_monitor._updateServiceState(
            name, active_state, process_state)
        self.assertThat(
            service_lock.acquire, MockCalledOnceWith())
        self.assertThat(
            service_lock.release, MockCalledOnceWith())

    @inlineCallbacks
    def test__getServiceState_with_now_True(self):
        fake_service = self.make_fake_service()
        service_monitor = self.make_service_monitor([fake_service])
        active_state = factory.pick_enum(SERVICE_STATE)
        process_state = random.choice(["running", "dead"])
        mock_loadServiceState = self.patch(
            service_monitor, "_loadServiceState")
        mock_loadServiceState.return_value = succeed(
            (active_state, process_state))
        observered_state = yield service_monitor.getServiceState(
            fake_service.name, now=True)
        state = service_monitor._serviceStates[fake_service.name]
        self.assertEquals(
            (active_state, process_state),
            (state.active_state, state.process_state))
        self.assertEquals(state, observered_state)
        self.assertThat(
            mock_loadServiceState, MockCalledOnceWith(fake_service))

    @inlineCallbacks
    def test__getServiceState_with_now_False(self):
        fake_service = self.make_fake_service()
        service_monitor = self.make_service_monitor([fake_service])
        mock_loadServiceState = self.patch(
            service_monitor, "_loadServiceState")
        observered_state = yield service_monitor.getServiceState(
            fake_service.name, now=False)
        state = service_monitor._serviceStates[fake_service.name]
        self.assertEquals(
            (SERVICE_STATE.UNKNOWN, None),
            (state.active_state, state.process_state))
        self.assertEquals(state, observered_state)
        self.assertThat(
            mock_loadServiceState, MockNotCalled())

    @inlineCallbacks
    def test__ensureServices_returns_dict_for_states(self):
        fake_services = [
            self.make_fake_service()
            for _ in range(3)
        ]
        expected_states = {}
        for service in fake_services:
            active_state = factory.pick_enum(SERVICE_STATE)
            process_state = random.choice(["running", "dead"])
            expected_states[service.name] = ServiceState(
                active_state, process_state)
        service_monitor = self.make_service_monitor(fake_services)
        self.patch(service_monitor, "ensureService").side_effect = (
            lambda name: succeed(expected_states[name]))
        observered = yield service_monitor.ensureServices()
        self.assertEquals(expected_states, observered)

    @inlineCallbacks
    def test__ensureServices_handles_errors(self):
        fake_service = self.make_fake_service()
        service_monitor = self.make_service_monitor([fake_service])
        active_state = factory.pick_enum(SERVICE_STATE)
        process_state = random.choice(["running", "dead"])
        service_state = ServiceState(active_state, process_state)
        service_monitor._serviceStates[fake_service.name] = service_state
        self.patch(service_monitor, "ensureService").return_value = fail(
            ServiceActionError())
        observered = yield service_monitor.ensureServices()
        self.assertEquals({
            fake_service.name: service_state,
        }, observered)

    @inlineCallbacks
    def test__ensureService_calls__ensureService(self):
        fake_service = self.make_fake_service()
        service_monitor = self.make_service_monitor([fake_service])
        active_state = factory.pick_enum(SERVICE_STATE)
        process_state = random.choice(["running", "dead"])
        service_state = ServiceState(active_state, process_state)
        mock_ensureService = self.patch(service_monitor, "_ensureService")
        mock_ensureService.return_value = succeed(service_state)
        observered = yield service_monitor.ensureService(fake_service.name)
        self.assertEquals(service_state, observered)
        self.assertThat(mock_ensureService, MockCalledOnceWith(fake_service))

    @inlineCallbacks
    def test__restartService_raises_ServiceNotOnError(self):
        fake_service = self.make_fake_service(SERVICE_STATE.OFF)
        service_monitor = self.make_service_monitor([fake_service])
        with ExpectedException(ServiceNotOnError):
            yield service_monitor.restartService(fake_service.name)

    @inlineCallbacks
    def test__restartService_performs_restart(self):
        fake_service = self.make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([fake_service])
        mock_performServiceAction = self.patch(
            service_monitor, "_performServiceAction")
        mock_performServiceAction.return_value = succeed(None)
        service_state = ServiceState(SERVICE_STATE.ON, "running")
        mock_getServiceState = self.patch(service_monitor, "getServiceState")
        mock_getServiceState.return_value = succeed(service_state)
        observered = yield service_monitor.restartService(fake_service.name)
        self.assertEquals(service_state, observered)
        self.assertThat(
            mock_getServiceState,
            MockCalledOnceWith(fake_service.name, now=True))
        self.assertThat(
            mock_performServiceAction,
            MockCalledOnceWith(fake_service, "restart"))

    @inlineCallbacks
    def test__restartService_raises_ServiceActionError_if_not_on(self):
        fake_service = self.make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([fake_service])
        mock_performServiceAction = self.patch(
            service_monitor, "_performServiceAction")
        mock_performServiceAction.return_value = succeed(None)
        active_state = factory.pick_enum(
            SERVICE_STATE, but_not=[SERVICE_STATE.ON])
        service_state = ServiceState(active_state, "dead")
        mock_getServiceState = self.patch(service_monitor, "getServiceState")
        mock_getServiceState.return_value = succeed(service_state)
        with ExpectedException(ServiceActionError):
            yield service_monitor.restartService(fake_service.name)

    @inlineCallbacks
    def test___execServiceAction_calls_systemctl_with_action_and_name(self):
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        action = factory.make_name("action")
        mock_popen = self.patch(service_monitor_module, "Popen")
        mock_popen.return_value.communicate.return_value = (b"", b"")
        yield deferToThread(
            service_monitor._execServiceAction, service_name, action)
        self.assertEqual(
            ["sudo", "systemctl", action, service_name],
            mock_popen.call_args[0][0])

    @inlineCallbacks
    def test___execServiceAction_calls_service_with_LC_ALL_in_env(self):
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        action = factory.make_name("action")
        mock_popen = self.patch(service_monitor_module, "Popen")
        mock_popen.return_value.communicate.return_value = (b"", b"")
        yield deferToThread(
            service_monitor._execServiceAction, service_name, action)
        self.assertEqual(
            "C.UTF-8",
            mock_popen.call_args[1]['env']['LC_ALL'])

    @inlineCallbacks
    def test___execServiceAction_decodes_stdout(self):
        # From https://www.cl.cam.ac.uk/~mgk25/ucs/examples/UTF-8-demo.txt.
        example_text = (
            '\u16bb\u16d6 \u16b3\u16b9\u16ab\u16a6 \u16a6\u16ab\u16cf '
            '\u16bb\u16d6 \u16d2\u16a2\u16de\u16d6 \u16a9\u16be \u16a6'
            '\u16ab\u16d7 \u16da\u16aa\u16be\u16de\u16d6 \u16be\u16a9'
            '\u16b1\u16a6\u16b9\u16d6\u16aa\u16b1\u16de\u16a2\u16d7 '
            '\u16b9\u16c1\u16a6 \u16a6\u16aa \u16b9\u16d6\u16e5\u16ab'
        )
        service_monitor = self.make_service_monitor()
        service_name = factory.make_name("service")
        action = factory.make_name("action")
        mock_popen = self.patch(service_monitor_module, "Popen")
        mock_popen.return_value.communicate.return_value = (
            example_text.encode("utf-8"), b"")
        _, output = yield deferToThread(
            service_monitor._execServiceAction, service_name, action)
        self.assertThat(output, Equals(example_text))

    @inlineCallbacks
    def test___performServiceAction_holds_lock_calls__execServiceAction(self):
        service = self.make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor()
        service_lock = Mock()
        service_lock.acquire.return_value = succeed(service_lock)
        self.patch(
            service_monitor,
            "_getServiceLock").return_value = succeed(service_lock)
        mock_execServiceAction = self.patch(
            service_monitor, "_execServiceAction")
        mock_execServiceAction.return_value = (0, "")
        action = factory.make_name("action")
        yield service_monitor._performServiceAction(service, action)
        self.assertThat(
            service_lock.acquire, MockCalledOnceWith())
        self.assertThat(
            service_lock.release, MockCalledOnceWith())
        self.assertThat(
            mock_execServiceAction,
            MockCalledOnceWith(service.service_name, action))

    @inlineCallbacks
    def test___performServiceAction_raises_ServiceActionError_if_fails(self):
        service = self.make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor()
        mock_execServiceAction = self.patch(
            service_monitor, "_execServiceAction")
        mock_execServiceAction.return_value = (1, "")
        action = factory.make_name("action")
        with ExpectedException(ServiceActionError):
            yield service_monitor._performServiceAction(service, action)

    @inlineCallbacks
    def test___performServiceAction_logs_error_if_action_fails(self):
        service = self.make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor()
        mock_execServiceAction = self.patch(
            service_monitor, "_execServiceAction")
        error_output = factory.make_name("error")
        mock_execServiceAction.return_value = (1, error_output)
        action = factory.make_name("action")
        with FakeLogger(
                "maas.service_monitor", level=logging.ERROR) as maaslog:
            with ExpectedException(ServiceActionError):
                yield service_monitor._performServiceAction(service, action)

        self.assertDocTestMatches(
            "Service '%s' failed to %s: %s" % (
                service.service_name, action, error_output),
            maaslog.output)

    @inlineCallbacks
    def test___loadServiceState_status_calls___execServiceAction(self):
        service = self.make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        mock_execServiceAction = self.patch(
            service_monitor, "_execServiceAction")
        mock_execServiceAction.side_effect = factory.make_exception()
        try:
            yield service_monitor._loadServiceState(service)
        except:
            pass
        self.assertThat(
            mock_execServiceAction,
            MockCalledOnceWith(service.service_name, "status"))

    @inlineCallbacks
    def test___loadServiceState_status_raises_ServiceUnknownError(self):
        service = self.make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor()
        systemd_status_output = dedent("""\
            %s.service
                Loaded: not-found (Reason: No such file or directory)
                Active: inactive (dead)
            """) % service.service_name

        mock_execServiceAction = self.patch(
            service_monitor, "_execServiceAction")
        mock_execServiceAction.return_value = (3, systemd_status_output)
        with ExpectedException(ServiceUnknownError):
            yield service_monitor._loadServiceState(service)

    @inlineCallbacks
    def test___loadServiceState_status_returns_off_and_dead(self):
        service = self.make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        systemd_status_output = dedent("""\
            %s.service - LSB: iscsi target daemon
                Loaded: loaded (/lib/systemd/system/%s.service)
                Active: inactive (dead)
                Docs: man:systemd-sysv-generator(8)
            """) % (service.service_name, service.service_name)

        mock_execServiceAction = self.patch(
            service_monitor, "_execServiceAction")
        mock_execServiceAction.return_value = (3, systemd_status_output)
        active_state, process_state = yield (
            service_monitor._loadServiceState(service))
        self.assertEqual(SERVICE_STATE.OFF, active_state)
        self.assertEqual("dead", process_state)

    @inlineCallbacks
    def test___loadServiceState_status_returns_dead_for_failed(self):
        service = self.make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        systemd_status_output = dedent("""\
            %s.service - Fake service
                Loaded: loaded (/lib/systemd/system/%s.service; ...
                Active: failed (Result: exit-code) since Wed 2016-01-20...
                Docs: man:dhcpd(8)
            """) % (service.service_name, service.service_name)

        mock_execServiceAction = self.patch(
            service_monitor, "_execServiceAction")
        mock_execServiceAction.return_value = (3, systemd_status_output)
        active_state, process_state = yield (
            service_monitor._loadServiceState(service))
        self.assertEqual(SERVICE_STATE.DEAD, active_state)

    @inlineCallbacks
    def test___loadServiceState_status_returns_on_and_running(self):
        service = self.make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        systemd_status_output = dedent("""\
            %s.service - Fake Service
                Loaded: loaded (/lib/systemd/system/%s.service)
                Active: active (running) since Fri 2015-05-15 15:08:26 UTC;
                Docs: man:systemd-sysv-generator(8)
            """) % (service.service_name, service.service_name)

        mock_execServiceAction = self.patch(
            service_monitor, "_execServiceAction")
        mock_execServiceAction.return_value = (0, systemd_status_output)
        active_state, process_state = yield (
            service_monitor._loadServiceState(service))
        self.assertEqual(SERVICE_STATE.ON, active_state)
        self.assertEqual("running", process_state)

    @inlineCallbacks
    def test___loadServiceState_status_ignores_sudo_output(self):
        service = self.make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        systemd_status_output = dedent("""\
            sudo: unable to resolve host sub-etha-sens-o-matic
            %s.service - Fake service
                Loaded: loaded (/lib/systemd/system/%s.service)
                Active: active (running) since Fri 2015-05-15 15:08:26 UTC;
                Docs: man:systemd-sysv-generator(8)
            """) % (service.service_name, service.service_name)

        mock_execServiceAction = self.patch(
            service_monitor, "_execServiceAction")
        mock_execServiceAction.return_value = (0, systemd_status_output)
        active_state, process_state = yield (
            service_monitor._loadServiceState(service))
        self.assertEqual(SERVICE_STATE.ON, active_state)
        self.assertEqual("running", process_state)

    @inlineCallbacks
    def test___loadServiceState_status_raise_error_for_invalid_active(self):
        service = self.make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        systemd_status_output = dedent("""\
            %s.service - Fake service
                Loaded: loaded (/lib/systemd/system/%s.service)
                Active: unknown (running) since Fri 2015-05-15 15:08:26 UTC;
                Docs: man:systemd-sysv-generator(8)
            """) % (service.service_name, service.service_name)

        service_monitor = self.make_service_monitor()
        mock_execServiceAction = self.patch(
            service_monitor, "_execServiceAction")
        mock_execServiceAction.return_value = (0, systemd_status_output)

        with ExpectedException(ServiceParsingError):
            yield service_monitor._loadServiceState(service)

    @inlineCallbacks
    def test___loadServiceState_status_raise_error_for_invalid_output(self):
        service = self.make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])
        mock_execServiceAction = self.patch(
            service_monitor, "_execServiceAction")
        mock_execServiceAction.return_value = (
            3, factory.make_name("invalid"))

        with ExpectedException(ServiceParsingError):
            yield service_monitor._loadServiceState(service)

    @inlineCallbacks
    def test___ensureService_logs_warning_in_mismatch_process_state(self):
        service = self.make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])

        invalid_process_state = factory.make_name("invalid_state")
        mock_getServiceState = self.patch(
            service_monitor, "getServiceState")
        mock_getServiceState.return_value = succeed(
            ServiceState(SERVICE_STATE.ON, invalid_process_state))

        with FakeLogger(
                "maas.service_monitor", level=logging.WARNING) as maaslog:
            yield service_monitor._ensureService(service)
        self.assertDocTestMatches(
            "Service '%s' is %s but not in the expected state of "
            "'%s', its current state is '%s'." % (
                service.service_name, SERVICE_STATE.ON,
                service_monitor.SYSTEMD_PROCESS_STATE[SERVICE_STATE.ON],
                invalid_process_state),
            maaslog.output)

    @inlineCallbacks
    def test___ensureService_logs_debug_in_expected_states(self):
        state = SERVICE_STATE.ON
        service = self.make_fake_service(state)
        service_monitor = self.make_service_monitor([service])

        expected_process_state = service_monitor.SYSTEMD_PROCESS_STATE[state]
        mock_getServiceState = self.patch(
            service_monitor, "getServiceState")
        mock_getServiceState.return_value = succeed(
            ServiceState(SERVICE_STATE.ON, expected_process_state))

        with FakeLogger(
                "maas.service_monitor", level=logging.DEBUG) as maaslog:
            yield service_monitor._ensureService(service)
        self.assertDocTestMatches(
            "Service '%s' is %s and '%s'." % (
                service.service_name, state, expected_process_state),
            maaslog.output)

    @inlineCallbacks
    def test___ensureService_performs_start_for_off_service(self):
        service = self.make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])

        mock_getServiceState = self.patch(
            service_monitor, "getServiceState")
        mock_getServiceState.side_effect = [
            succeed(ServiceState(SERVICE_STATE.OFF, "waiting")),
            succeed(ServiceState(SERVICE_STATE.ON, "running")),
            ]
        mock_performServiceAction = self.patch(
            service_monitor, "_performServiceAction")
        mock_performServiceAction.return_value = succeed(None)

        with FakeLogger(
                "maas.service_monitor", level=logging.INFO) as maaslog:
            yield service_monitor._ensureService(service)
        self.assertThat(
            mock_performServiceAction, MockCalledOnceWith(service, "start"))
        self.assertDocTestMatches(
            """\
            Service '%s' is not on, it will be started.
            Service '%s' has been started and is 'running'.
            """ % (service.service_name, service.service_name),
            maaslog.output)

    @inlineCallbacks
    def test__ensureService_performs_stop_for_on_service(self):
        service = self.make_fake_service(SERVICE_STATE.OFF)
        service_monitor = self.make_service_monitor([service])

        mock_getServiceState = self.patch(
            service_monitor, "getServiceState")
        mock_getServiceState.side_effect = [
            succeed(ServiceState(SERVICE_STATE.ON, "running")),
            succeed(ServiceState(SERVICE_STATE.OFF, "waiting")),
            ]
        mock_performServiceAction = self.patch(
            service_monitor, "_performServiceAction")
        mock_performServiceAction.return_value = succeed(None)

        with FakeLogger(
                "maas.service_monitor", level=logging.INFO) as maaslog:
            yield service_monitor._ensureService(service)
        self.assertThat(
            mock_performServiceAction, MockCalledOnceWith(service, "stop"))
        self.assertDocTestMatches(
            """\
            Service '%s' is not off, it will be stopped.
            Service '%s' has been stopped and is 'waiting'.
            """ % (service.service_name, service.service_name),
            maaslog.output)

    @inlineCallbacks
    def test__ensureService_performs_raises_ServiceActionError(self):
        service = self.make_fake_service(SERVICE_STATE.ON)
        service_monitor = self.make_service_monitor([service])

        mock_getServiceState = self.patch(
            service_monitor, "getServiceState")
        mock_getServiceState.side_effect = [
            succeed(ServiceState(SERVICE_STATE.OFF, "waiting")),
            succeed(ServiceState(SERVICE_STATE.OFF, "waiting")),
            ]
        mock_performServiceAction = self.patch(
            service_monitor, "_performServiceAction")
        mock_performServiceAction.return_value = succeed(None)

        with ExpectedException(ServiceActionError):
            with FakeLogger(
                    "maas.service_monitor", level=logging.INFO) as maaslog:
                yield service_monitor._ensureService(service)
        lint_sucks = (
            service.service_name,
            service.service_name,
            SERVICE_STATE.OFF,
            "waiting",
        )
        self.assertDocTestMatches("""\
            Service '%s' is not on, it will be started.
            Service '%s' failed to start. Its current state is '%s' and '%s'.
            """ % lint_sucks, maaslog.output)
