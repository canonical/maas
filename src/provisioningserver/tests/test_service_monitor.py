# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.service_monitor`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import logging
from textwrap import dedent

from fixtures import FakeLogger
from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
)
from maastesting.testcase import MAASTestCase
from mock import (
    ANY,
    call,
    sentinel,
)
from provisioningserver import service_monitor as service_monitor_module
from provisioningserver.drivers.service import (
    Service,
    SERVICE_STATE,
    ServiceRegistry,
)
from provisioningserver.service_monitor import (
    ServiceActionError,
    ServiceMonitor,
    ServiceNotOnError,
    ServiceParsingError,
    UnknownServiceError,
)
from provisioningserver.utils.testing import RegistryFixture
from testtools import ExpectedException


class TestServiceMonitor(MAASTestCase):
    """Tests for `ServiceMonitor`."""

    def setUp(self):
        super(TestServiceMonitor, self).setUp()
        # Ensure the global registry is empty for each test run.
        self.useFixture(RegistryFixture())

    def make_service_driver(self, expected_state=None):
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
                return expected_state

        service = FakeService()
        ServiceRegistry.register_item(service.name, service)
        return service

    def test_init_determines_init_system(self):
        mock_has_cmd = self.patch(
            service_monitor_module, "get_init_system")
        mock_has_cmd.return_value = sentinel.init_system
        service_monitor = ServiceMonitor()
        self.assertEquals(sentinel.init_system, service_monitor.init_system)

    def test__get_service_lock_adds_lock_to_service_locks(self):
        service_monitor = ServiceMonitor()
        service_name = factory.make_name("service")
        service_lock = service_monitor._get_service_lock(service_name)
        self.assertIs(
            service_lock, service_monitor.service_locks[service_name])

    def test__get_service_lock_uses_shared_lock(self):
        service_monitor = ServiceMonitor()
        service_shared_lock = self.patch(service_monitor, "_lock")
        service_name = factory.make_name("service")
        service_monitor._get_service_lock(service_name)
        self.assertThat(
            service_shared_lock.__enter__, MockCalledOnceWith())
        self.assertThat(
            service_shared_lock.__exit__, MockCalledOnceWith(None, None, None))

    def test__lock_service_acquires_lock_for_service(self):
        service_monitor = ServiceMonitor()
        service_name = factory.make_name("service")
        service_lock = service_monitor._get_service_lock(service_name)
        with service_lock:
            self.assertTrue(
                service_lock.locked(), "Service lock was not acquired.")
        self.assertFalse(
            service_lock.locked(), "Service lock was not released.")

    def test_get_service_state_raises_UnknownServiceError(self):
        service_monitor = ServiceMonitor()
        with ExpectedException(UnknownServiceError):
            service_monitor.get_service_state(factory.make_name("service"))

    def test_get_service_state_returns_state_from__get_service_status(self):
        service = self.make_service_driver()
        service_monitor = ServiceMonitor()
        mock_get_service_status = self.patch(
            service_monitor, "_get_service_status")
        mock_get_service_status.return_value = (
            sentinel.state, sentinel.process_state)
        self.assertEquals(
            sentinel.state, service_monitor.get_service_state(service.name))

    def test_ensure_all_services_calls_ensure_service_for_all_services(self):
        service_names = sorted([
            self.make_service_driver().name
            for _ in range(3)
            ])
        service_calls = [
            call(name)
            for name in service_names
            ]
        service_monitor = ServiceMonitor()
        mock_ensure_service = self.patch(service_monitor, "ensure_service")
        service_monitor.ensure_all_services()
        self.assertThat(mock_ensure_service, MockCallsMatch(*service_calls))

    def test_ensure_all_services_log_unknown_errors(self):
        service = self.make_service_driver()
        service_monitor = ServiceMonitor()
        raised_exception = factory.make_exception()
        mock_ensure_service = self.patch(service_monitor, "ensure_service")
        mock_ensure_service.side_effect = raised_exception
        with FakeLogger(
                "maas.service_monitor", level=logging.ERROR) as maaslog:
            service_monitor.ensure_all_services()

        self.assertDocTestMatches(
            "While monitoring service '%s' an error was encountered: %s" % (
                service.service_name, raised_exception),
            maaslog.output)

    def test_ensure_service_raises_UnknownServiceError(self):
        service_monitor = ServiceMonitor()
        with ExpectedException(UnknownServiceError):
            service_monitor.ensure_service(factory.make_name("service"))

    def test_ensure_service_calls_lock_and_unlock_even_with_exception(self):
        service = self.make_service_driver()
        service_monitor = ServiceMonitor()
        exception_type = factory.make_exception_type()
        mock_ensure_service = self.patch(service_monitor, "_ensure_service")
        mock_ensure_service.side_effect = exception_type
        get_service_lock = self.patch(service_monitor, "_get_service_lock")

        self.assertRaises(
            exception_type, service_monitor.ensure_service, service.name)

        self.expectThat(get_service_lock, MockCalledOnceWith(service.name))
        lock = get_service_lock.return_value
        self.expectThat(
            lock.__enter__, MockCalledOnceWith())
        self.expectThat(
            lock.__exit__, MockCalledOnceWith(exception_type, ANY, ANY))

    def test_async_ensure_service_defers_to_a_thread(self):
        service_monitor = ServiceMonitor()
        mock_deferToThread = self.patch(
            service_monitor_module, "deferToThread")
        mock_deferToThread.return_value = sentinel.defer
        service_name = factory.make_name("service")
        self.assertEquals(
            sentinel.defer,
            service_monitor.async_ensure_service(service_name))
        self.assertThat(
            mock_deferToThread,
            MockCalledOnceWith(service_monitor.ensure_service, service_name))

    def test_restart_service_raises_UnknownServiceError(self):
        service_monitor = ServiceMonitor()
        with ExpectedException(UnknownServiceError):
            service_monitor.restart_service(factory.make_name("service"))

    def test_restart_service_raises_ServiceNotOnError(self):
        service = self.make_service_driver(SERVICE_STATE.OFF)
        service_monitor = ServiceMonitor()
        with ExpectedException(ServiceNotOnError):
            service_monitor.restart_service(service.name)

    def test_restart_service_calls_lock_and_unlock_even_with_exception(self):
        service = self.make_service_driver(SERVICE_STATE.ON)
        service_monitor = ServiceMonitor()
        exception_type = factory.make_exception_type()
        mock_service_action = self.patch(service_monitor, "_service_action")
        mock_service_action.side_effect = exception_type
        get_service_lock = self.patch(service_monitor, "_get_service_lock")

        self.assertRaises(
            exception_type, service_monitor.restart_service, service.name)

        self.expectThat(get_service_lock, MockCalledOnceWith(service.name))
        lock = get_service_lock.return_value
        self.expectThat(
            lock.__enter__, MockCalledOnceWith())
        self.expectThat(
            lock.__exit__, MockCalledOnceWith(exception_type, ANY, ANY))

    def test_restart_service_calls__service_action_with_restart(self):
        service = self.make_service_driver(SERVICE_STATE.ON)
        service_monitor = ServiceMonitor()
        mock_service_action = self.patch(service_monitor, "_service_action")
        mock_service_action.side_effect = factory.make_exception()
        try:
            service_monitor.restart_service(service.name)
        except:
            pass
        self.assertThat(
            mock_service_action, MockCalledOnceWith(service, "restart"))

    def test_restart_service_raised_ServiceActionError_if_service_off(self):
        service = self.make_service_driver(SERVICE_STATE.ON)
        service_monitor = ServiceMonitor()
        self.patch(service_monitor, "_service_action")
        mock_get_service_status = self.patch(
            service_monitor, "_get_service_status")
        mock_get_service_status.return_value = (
            SERVICE_STATE.OFF, "dead")
        with ExpectedException(ServiceActionError):
            service_monitor.restart_service(service.name)

    def test_restart_service_logs_error_if_service_off(self):
        service = self.make_service_driver(SERVICE_STATE.ON)
        service_monitor = ServiceMonitor()
        self.patch(service_monitor, "_service_action")
        mock_get_service_status = self.patch(
            service_monitor, "_get_service_status")
        mock_get_service_status.return_value = (
            SERVICE_STATE.OFF, "dead")
        with FakeLogger(
                "maas.service_monitor", level=logging.ERROR) as maaslog:
            with ExpectedException(ServiceActionError):
                service_monitor.restart_service(service.name)

        self.assertDocTestMatches(
            "Service '%s' failed to restart. Its current state "
            "is 'off' and 'dead'." % service.service_name,
            maaslog.output)

    def test_restart_service_logs_info_if_service_on(self):
        service = self.make_service_driver(SERVICE_STATE.ON)
        service_monitor = ServiceMonitor()
        self.patch(service_monitor, "_service_action")
        mock_get_service_status = self.patch(
            service_monitor, "_get_service_status")
        mock_get_service_status.return_value = (
            SERVICE_STATE.ON, "running")
        with FakeLogger(
                "maas.service_monitor", level=logging.INFO) as maaslog:
            service_monitor.restart_service(service.name)

        self.assertDocTestMatches(
            "Service '%s' has been restarted. Its current state "
            "is 'on' and 'running'." % service.service_name,
            maaslog.output)

    def test_async_restart_service_defers_to_a_thread(self):
        service_monitor = ServiceMonitor()
        mock_deferToThread = self.patch(
            service_monitor_module, "deferToThread")
        mock_deferToThread.return_value = sentinel.defer
        service_name = factory.make_name("service")
        self.assertEquals(
            sentinel.defer,
            service_monitor.async_restart_service(service_name))
        self.assertThat(
            mock_deferToThread,
            MockCalledOnceWith(
                service_monitor.restart_service, service_name))

    def test__exec_service_action_calls_service_with_name_and_action(self):
        service_monitor = ServiceMonitor()
        service_name = factory.make_name("service")
        action = factory.make_name("action")
        mock_popen = self.patch(service_monitor_module, "Popen")
        mock_popen.return_value.communicate.return_value = ("", "")
        service_monitor._exec_service_action(service_name, action)
        self.assertEquals(
            ["sudo", "service", service_name, action],
            mock_popen.call_args[0][0])

    def test__exec_service_action_calls_service_with_LC_CTYPE_in_env(self):
        service_monitor = ServiceMonitor()
        service_name = factory.make_name("service")
        action = factory.make_name("action")
        mock_popen = self.patch(service_monitor_module, "Popen")
        mock_popen.return_value.communicate.return_value = ("", "")
        service_monitor._exec_service_action(service_name, action)
        self.assertEquals(
            "C",
            mock_popen.call_args[1]['env']['LC_CTYPE'])

    def test__service_action_calls__exec_service_action(self):
        service = self.make_service_driver(SERVICE_STATE.ON)
        service_monitor = ServiceMonitor()
        mock_exec_service_action = self.patch(
            service_monitor, "_exec_service_action")
        mock_exec_service_action.return_value = (0, "")
        action = factory.make_name("action")
        service_monitor._service_action(service, action)
        self.assertThat(
            mock_exec_service_action,
            MockCalledOnceWith(service.service_name, action))

    def test__service_action_raises_ServiceActionError_if_action_fails(self):
        service = self.make_service_driver(SERVICE_STATE.ON)
        service_monitor = ServiceMonitor()
        mock_exec_service_action = self.patch(
            service_monitor, "_exec_service_action")
        mock_exec_service_action.return_value = (1, "")
        action = factory.make_name("action")
        with ExpectedException(ServiceActionError):
            service_monitor._service_action(service, action)

    def test__service_action_logs_error_if_action_fails(self):
        service = self.make_service_driver(SERVICE_STATE.ON)
        service_monitor = ServiceMonitor()
        mock_exec_service_action = self.patch(
            service_monitor, "_exec_service_action")
        error_output = factory.make_name("error")
        mock_exec_service_action.return_value = (1, error_output)
        action = factory.make_name("action")
        with FakeLogger(
                "maas.service_monitor", level=logging.ERROR) as maaslog:
            with ExpectedException(ServiceActionError):
                service_monitor._service_action(service, action)

        self.assertDocTestMatches(
            "Service '%s' failed to %s: %s" % (
                service.service_name, action, error_output),
            maaslog.output)

    def test__get_service_status_uses__get_systemd_service_status(self):
        service = self.make_service_driver(SERVICE_STATE.ON)
        service_monitor = ServiceMonitor()
        service_monitor.init_system = "systemd"
        mock_get_systemd_service_status = self.patch(
            service_monitor, "_get_systemd_service_status")
        service_monitor._get_service_status(service)
        self.assertThat(
            mock_get_systemd_service_status,
            MockCalledOnceWith(service.service_name))

    def test__get_service_status_uses__get_upstart_service_status(self):
        service = self.make_service_driver(SERVICE_STATE.ON)
        service_monitor = ServiceMonitor()
        service_monitor.init_system = "upstart"
        mock_get_upstart_service_status = self.patch(
            service_monitor, "_get_upstart_service_status")
        service_monitor._get_service_status(service)
        self.assertThat(
            mock_get_upstart_service_status,
            MockCalledOnceWith(service.service_name))

    def test__get_systemd_service_status_calls__exec_service_action(self):
        service_monitor = ServiceMonitor()
        service_name = factory.make_name("service")
        mock_exec_service_action = self.patch(
            service_monitor, "_exec_service_action")
        mock_exec_service_action.side_effect = factory.make_exception()
        try:
            service_monitor._get_systemd_service_status(service_name)
        except:
            pass
        self.assertThat(
            mock_exec_service_action,
            MockCalledOnceWith(service_name, "status"))

    def test__get_systemd_service_status_raises_UnknownServiceError(self):
        systemd_status_output = dedent("""\
            missing.service
                Loaded: not-found (Reason: No such file or directory)
                Active: inactive (dead)
            """)

        service_monitor = ServiceMonitor()
        mock_exec_service_action = self.patch(
            service_monitor, "_exec_service_action")
        mock_exec_service_action.return_value = (3, systemd_status_output)

        with ExpectedException(UnknownServiceError):
            service_monitor._get_systemd_service_status("missing")

    def test__get_systemd_service_status_returns_off_and_dead(self):
        systemd_status_output = dedent("""\
            tgt.service - LSB: iscsi target daemon
                Loaded: loaded (/etc/init.d/tgt)
                Active: inactive (dead)
                Docs: man:systemd-sysv-generator(8)
            """)

        service_monitor = ServiceMonitor()
        mock_exec_service_action = self.patch(
            service_monitor, "_exec_service_action")
        mock_exec_service_action.return_value = (3, systemd_status_output)
        active_state, process_state = (
            service_monitor._get_systemd_service_status("tgt"))
        self.assertEquals(SERVICE_STATE.OFF, active_state)
        self.assertEquals("dead", process_state)

    def test__get_systemd_service_status_returns_on_and_running(self):
        systemd_status_output = dedent("""\
            tgt.service - LSB: iscsi target daemon
                Loaded: loaded (/etc/init.d/tgt)
                Active: active (running) since Fri 2015-05-15 15:08:26 UTC;
                Docs: man:systemd-sysv-generator(8)
            """)

        service_monitor = ServiceMonitor()
        mock_exec_service_action = self.patch(
            service_monitor, "_exec_service_action")
        mock_exec_service_action.return_value = (0, systemd_status_output)
        active_state, process_state = (
            service_monitor._get_systemd_service_status("tgt"))
        self.assertEquals(SERVICE_STATE.ON, active_state)
        self.assertEquals("running", process_state)

    def test__get_systemd_service_status_raise_error_for_invalid_active(self):
        systemd_status_output = dedent("""\
            tgt.service - LSB: iscsi target daemon
                Loaded: loaded (/etc/init.d/tgt)
                Active: unknown (running) since Fri 2015-05-15 15:08:26 UTC;
                Docs: man:systemd-sysv-generator(8)
            """)

        service_monitor = ServiceMonitor()
        mock_exec_service_action = self.patch(
            service_monitor, "_exec_service_action")
        mock_exec_service_action.return_value = (0, systemd_status_output)

        with ExpectedException(ServiceParsingError):
            service_monitor._get_systemd_service_status("tgt")

    def test__get_systemd_service_status_raise_error_for_invalid_output(self):
        service_monitor = ServiceMonitor()
        mock_exec_service_action = self.patch(
            service_monitor, "_exec_service_action")
        mock_exec_service_action.return_value = (
            3, factory.make_name("invalid"))

        with ExpectedException(ServiceParsingError):
            service_monitor._get_systemd_service_status("tgt")

    def test__get_upstart_service_status_raises_UnknownServiceError(self):
        service_monitor = ServiceMonitor()
        mock_exec_service_action = self.patch(
            service_monitor, "_exec_service_action")
        mock_exec_service_action.return_value = (
            1, "missing: unrecognized service")

        with ExpectedException(UnknownServiceError):
            service_monitor._get_upstart_service_status("missing")

    def test__get_upstart_service_status_returns_off_and_waiting(self):
        service_monitor = ServiceMonitor()
        mock_exec_service_action = self.patch(
            service_monitor, "_exec_service_action")
        mock_exec_service_action.return_value = (
            0, "tgt stop/waiting")
        active_state, process_state = (
            service_monitor._get_upstart_service_status("tgt"))
        self.assertEquals(SERVICE_STATE.OFF, active_state)
        self.assertEquals("waiting", process_state)

    def test__get_upstart_service_status_returns_on_and_running(self):
        service_monitor = ServiceMonitor()
        mock_exec_service_action = self.patch(
            service_monitor, "_exec_service_action")
        mock_exec_service_action.return_value = (
            0, "tgt start/running, process 23239")
        active_state, process_state = (
            service_monitor._get_upstart_service_status("tgt"))
        self.assertEquals(SERVICE_STATE.ON, active_state)
        self.assertEquals("running", process_state)

    def test__get_upstart_service_status_raise_error_for_invalid_active(self):
        service_monitor = ServiceMonitor()
        mock_exec_service_action = self.patch(
            service_monitor, "_exec_service_action")
        mock_exec_service_action.return_value = (
            0, "tgt unknown/running, process 23239")

        with ExpectedException(ServiceParsingError):
            service_monitor._get_upstart_service_status("tgt")

    def test__get_upstart_service_status_raise_error_for_invalid_output(self):
        service_monitor = ServiceMonitor()
        mock_exec_service_action = self.patch(
            service_monitor, "_exec_service_action")
        mock_exec_service_action.return_value = (
            0, factory.make_name("invalid"))

        with ExpectedException(ServiceParsingError):
            service_monitor._get_upstart_service_status("tgt")

    def test__get_expected_process_state_returns_upstart_running_for_on(self):
        service_monitor = ServiceMonitor()
        service_monitor.init_system = "upstart"
        self.assertEquals(
            "running",
            service_monitor._get_expected_process_state(SERVICE_STATE.ON))

    def test__get_expected_process_state_returns_upstart_waiting_for_off(self):
        service_monitor = ServiceMonitor()
        service_monitor.init_system = "upstart"
        self.assertEquals(
            "waiting",
            service_monitor._get_expected_process_state(SERVICE_STATE.OFF))

    def test__get_expected_process_state_returns_systemd_running_for_on(self):
        service_monitor = ServiceMonitor()
        service_monitor.init_system = "systemd"
        self.assertEquals(
            "running",
            service_monitor._get_expected_process_state(SERVICE_STATE.ON))

    def test__get_expected_process_state_returns_systemd_dead_for_off(self):
        service_monitor = ServiceMonitor()
        service_monitor.init_system = "systemd"
        self.assertEquals(
            "dead",
            service_monitor._get_expected_process_state(SERVICE_STATE.OFF))

    def test__ensure_service_logs_warning_in_mismatch_process_state(self):
        service = self.make_service_driver(SERVICE_STATE.ON)
        service_monitor = ServiceMonitor()

        expected_state = service.get_expected_state()
        invalid_process_state = factory.make_name("invalid_state")
        mock_get_service_status = self.patch(
            service_monitor, "_get_service_status")
        mock_get_service_status.return_value = (
            expected_state, invalid_process_state)

        with FakeLogger(
                "maas.service_monitor", level=logging.WARNING) as maaslog:
            service_monitor._ensure_service(service)
        self.assertDocTestMatches(
            "Service '%s' is %s but not in the expected state of "
            "'%s', its current state is '%s'." % (
                service.service_name, expected_state,
                service_monitor._get_expected_process_state(expected_state),
                invalid_process_state),
            maaslog.output)

    def test__ensure_service_logs_debug_in_expected_states(self):
        service = self.make_service_driver()
        service_monitor = ServiceMonitor()

        expected_state = service.get_expected_state()
        expected_process_state = service_monitor._get_expected_process_state(
            expected_state)
        mock_get_service_status = self.patch(
            service_monitor, "_get_service_status")
        mock_get_service_status.return_value = (
            expected_state, expected_process_state)

        with FakeLogger(
                "maas.service_monitor", level=logging.DEBUG) as maaslog:
            service_monitor._ensure_service(service)
        self.assertDocTestMatches(
            "Service '%s' is %s and '%s'." % (
                service.service_name, expected_state, expected_process_state),
            maaslog.output)

    def test__ensure_service_performs_start_for_off_service(self):
        service = self.make_service_driver(SERVICE_STATE.ON)
        service_monitor = ServiceMonitor()

        mock_get_service_status = self.patch(
            service_monitor, "_get_service_status")
        mock_get_service_status.side_effect = [
            (SERVICE_STATE.OFF, "waiting"),
            (SERVICE_STATE.ON, "running"),
            ]
        mock_service_action = self.patch(service_monitor, "_service_action")

        with FakeLogger(
                "maas.service_monitor", level=logging.INFO) as maaslog:
            service_monitor._ensure_service(service)
        self.assertThat(
            mock_service_action, MockCalledOnceWith(service, "start"))
        self.assertDocTestMatches(
            """\
            Service '%s' is not on, it will be started.
            Service '%s' has been started and is 'running'.
            """ % (service.service_name, service.service_name),
            maaslog.output)

    def test__ensure_service_performs_stop_for_on_service(self):
        service = self.make_service_driver(SERVICE_STATE.OFF)
        service_monitor = ServiceMonitor()

        mock_get_service_status = self.patch(
            service_monitor, "_get_service_status")
        mock_get_service_status.side_effect = [
            (SERVICE_STATE.ON, "running"),
            (SERVICE_STATE.OFF, "waiting"),
            ]
        mock_service_action = self.patch(service_monitor, "_service_action")

        with FakeLogger(
                "maas.service_monitor", level=logging.INFO) as maaslog:
            service_monitor._ensure_service(service)
        self.assertThat(
            mock_service_action, MockCalledOnceWith(service, "stop"))
        self.assertDocTestMatches(
            """\
            Service '%s' is not off, it will be stopped.
            Service '%s' has been stopped and is 'waiting'.
            """ % (service.service_name, service.service_name),
            maaslog.output)

    def test__ensure_service_performs_raises_ServiceActionError(self):
        service = self.make_service_driver(SERVICE_STATE.ON)
        service_monitor = ServiceMonitor()

        mock_get_service_status = self.patch(
            service_monitor, "_get_service_status")
        mock_get_service_status.side_effect = [
            (SERVICE_STATE.OFF, "waiting"),
            (SERVICE_STATE.OFF, "waiting"),
            ]
        self.patch(service_monitor, "_service_action")

        with ExpectedException(ServiceActionError):
            with FakeLogger(
                    "maas.service_monitor", level=logging.INFO) as maaslog:
                service_monitor._ensure_service(service)
        self.assertDocTestMatches(
            """\
            Service '%s' is not on, it will be started.
            Service '%s' failed to start. Its current state is '%s' and '%s'.
            """ % (
            service.service_name, service.service_name,
            SERVICE_STATE.OFF, "waiting"),
            maaslog.output)
