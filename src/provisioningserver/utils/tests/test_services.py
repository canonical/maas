# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for services."""

__all__ = []

import threading
from unittest.mock import (
    call,
    sentinel,
)

from maastesting.factory import factory
from maastesting.matchers import (
    HasLength,
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from provisioningserver.utils import services
from provisioningserver.utils.services import NetworksMonitoringService
from testtools.matchers import (
    Equals,
    IsInstance,
    Not,
)
from twisted.application.internet import TimerService
from twisted.internet import reactor
from twisted.internet.defer import (
    DeferredQueue,
    inlineCallbacks,
    succeed,
)
from twisted.python import threadable


class StubNetworksMonitoringService(NetworksMonitoringService):
    """Concrete subclass for testing."""

    def __init__(self):
        super().__init__(reactor)
        self.iterations = DeferredQueue()
        self.interfaces = []

    def updateInterfaces(self):
        d = super().updateInterfaces()
        d.addBoth(self.iterations.put)
        return d

    def recordInterfaces(self, interfaces):
        self.interfaces.append(interfaces)


class TestNetworksMonitoringService(MAASTestCase):
    """Tests of `NetworksMonitoringService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def makeService(self):
        service = StubNetworksMonitoringService()
        self.addCleanup(service._releaseSoleResponsibility)
        return service

    def test_init(self):
        service = self.makeService()
        self.assertThat(service, IsInstance(TimerService))
        self.assertThat(service.step, Equals(service.interval))
        self.assertThat(service.call, Equals(
            (service.updateInterfaces, (), {})))

    @inlineCallbacks
    def test_get_all_interfaces_definition_is_called_in_thread(self):
        service = self.makeService()
        self.patch(
            services, "get_all_interfaces_definition",
            threading.current_thread)
        yield service.updateInterfaces()
        self.assertThat(service.interfaces, HasLength(1))
        [thread] = service.interfaces
        self.assertThat(thread, IsInstance(threading.Thread))
        self.assertThat(thread, Not(Equals(threadable.ioThread)))

    @inlineCallbacks
    def test_getInterfaces_called_to_get_configuration(self):
        service = self.makeService()
        getInterfaces = self.patch(service, "getInterfaces")
        getInterfaces.return_value = succeed(sentinel.config)
        yield service.updateInterfaces()
        self.assertThat(service.interfaces, Equals([sentinel.config]))

    @inlineCallbacks
    def test_logs_errors(self):
        service = self.makeService()
        maaslog = self.patch(services, 'maaslog')
        error_message = factory.make_string()
        get_interfaces = self.patch(services, "get_all_interfaces_definition")
        get_interfaces.side_effect = Exception(error_message)
        yield service.updateInterfaces()
        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "Failed to update and/or record network interface "
                "configuration: %s", error_message))

    @inlineCallbacks
    def test_recordInterfaces_called_when_nothing_previously_recorded(self):
        get_interfaces = self.patch(services, "get_all_interfaces_definition")
        get_interfaces.side_effect = [sentinel.config]

        service = self.makeService()
        self.assertThat(service.interfaces, Equals([]))
        yield service.updateInterfaces()
        self.assertThat(service.interfaces, Equals([sentinel.config]))

        self.assertThat(get_interfaces, MockCalledOnceWith())

    @inlineCallbacks
    def test_recordInterfaces_called_when_interfaces_changed(self):
        get_interfaces = self.patch(services, "get_all_interfaces_definition")
        # Configuration changes between the first and second call.
        get_interfaces.side_effect = [sentinel.config1, sentinel.config2]

        service = self.makeService()
        self.assertThat(service.interfaces, HasLength(0))
        yield service.updateInterfaces()
        self.assertThat(service.interfaces, Equals([sentinel.config1]))
        yield service.updateInterfaces()
        self.assertThat(service.interfaces, Equals(
            [sentinel.config1, sentinel.config2]))

        self.assertThat(get_interfaces, MockCallsMatch(call(), call()))

    @inlineCallbacks
    def test_recordInterfaces_not_called_when_interfaces_not_changed(self):
        get_interfaces = self.patch(services, "get_all_interfaces_definition")
        # Configuration does NOT change between the first and second call.
        get_interfaces.side_effect = [sentinel.config1, sentinel.config1]

        service = self.makeService()
        self.assertThat(service.interfaces, HasLength(0))
        yield service.updateInterfaces()
        self.assertThat(service.interfaces, Equals([sentinel.config1]))
        yield service.updateInterfaces()
        self.assertThat(service.interfaces, Equals([sentinel.config1]))

        self.assertThat(get_interfaces, MockCallsMatch(call(), call()))

    @inlineCallbacks
    def test_recordInterfaces_called_after_failure(self):
        get_interfaces = self.patch(services, "get_all_interfaces_definition")
        get_interfaces.return_value = sentinel.config

        service = self.makeService()
        recordInterfaces = self.patch(service, "recordInterfaces")
        recordInterfaces.side_effect = [Exception, None]

        # recordInterfaces is called the first time, as expected.
        recordInterfaces.reset_mock()
        yield service.updateInterfaces()
        self.assertThat(recordInterfaces, MockCalledOnceWith(sentinel.config))

        # recordInterfaces is called the second time too; the service noted
        # that it crashed last time and knew to run it again.
        recordInterfaces.reset_mock()
        yield service.updateInterfaces()
        self.assertThat(recordInterfaces, MockCalledOnceWith(sentinel.config))

        # recordInterfaces is NOT called the third time; the service noted
        # that the configuration had not changed.
        recordInterfaces.reset_mock()
        yield service.updateInterfaces()
        self.assertThat(recordInterfaces, MockNotCalled())

    @inlineCallbacks
    def test_assumes_sole_responsibility_before_updating(self):
        # A filesystem lock is used to prevent multiple network monitors from
        # running on each host machine.
        lock = NetworksMonitoringService._lock

        # Not locked before creating the service.
        self.assertFalse(lock.is_locked())

        # Still not locked after instantiating the service.
        service = self.makeService()
        self.assertFalse(lock.is_locked())

        # It's locked when the service is started and has begun iterating.
        service.startService()
        try:
            # It's locked once the first iteration is done.
            yield service.iterations.get()
            self.assertTrue(lock.is_locked())

            # It remains locked as the service iterates.
            yield service.updateInterfaces()
            self.assertTrue(lock.is_locked())

        finally:
            yield service.stopService()

        # It's unlocked now that the service is stopped.
        self.assertFalse(lock.is_locked())

        # Interfaces were recorded.
        self.assertThat(service.interfaces, Not(Equals([])))

    @inlineCallbacks
    def test_does_not_update_if_cannot_assume_sole_responsibility(self):
        # A filesystem lock is used to prevent multiple network monitors from
        # running on each host machine.
        lock = NetworksMonitoringService._lock

        with lock:
            service = self.makeService()
            # Iterate a few times.
            yield service.updateInterfaces()
            yield service.updateInterfaces()
            yield service.updateInterfaces()

        # Interfaces were NOT recorded.
        self.assertThat(service.interfaces, Equals([]))

    @inlineCallbacks
    def test_attempts_to_assume_sole_responsibility_on_each_iteration(self):
        # A filesystem lock is used to prevent multiple network monitors from
        # running on each host machine.
        lock = NetworksMonitoringService._lock

        with lock:
            service = self.makeService()
            # Iterate one time.
            yield service.updateInterfaces()

        # Interfaces have not been recorded yet.
        self.assertThat(service.interfaces, Equals([]))
        # Iterate once more and ...
        yield service.updateInterfaces()
        # ... interfaces ARE recorded.
        self.assertThat(service.interfaces, Not(Equals([])))
