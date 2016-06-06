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
from twisted.internet.defer import (
    inlineCallbacks,
    succeed,
)
from twisted.internet.task import Clock
from twisted.python import threadable


class StubNetworksMonitoringService(NetworksMonitoringService):
    """Concrete subclass for testing."""

    def __init__(self):
        super().__init__(Clock())
        self.interfaces = []

    def recordInterfaces(self, interfaces):
        self.interfaces.append(interfaces)


class TestNetworksMonitoringService(MAASTestCase):
    """Tests of `NetworksMonitoringService`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_init(self):
        service = StubNetworksMonitoringService()
        self.assertThat(service, IsInstance(TimerService))
        self.assertThat(service.step, Equals(service.interval))
        self.assertThat(service.call, Equals(
            (service.updateInterfaces, (), {})))

    @inlineCallbacks
    def test_get_all_interfaces_definition_is_called_in_thread(self):
        service = StubNetworksMonitoringService()
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
        service = StubNetworksMonitoringService()
        getInterfaces = self.patch(service, "getInterfaces")
        getInterfaces.return_value = succeed(sentinel.config)
        yield service.updateInterfaces()
        self.assertThat(service.interfaces, Equals([sentinel.config]))

    @inlineCallbacks
    def test_logs_errors(self):
        service = StubNetworksMonitoringService()
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

        service = StubNetworksMonitoringService()
        self.assertThat(service.interfaces, Equals([]))
        yield service.updateInterfaces()
        self.assertThat(service.interfaces, Equals([sentinel.config]))

        self.assertThat(get_interfaces, MockCalledOnceWith())

    @inlineCallbacks
    def test_recordInterfaces_called_when_interfaces_changed(self):
        get_interfaces = self.patch(services, "get_all_interfaces_definition")
        # Configuration changes between the first and second call.
        get_interfaces.side_effect = [sentinel.config1, sentinel.config2]

        service = StubNetworksMonitoringService()
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

        service = StubNetworksMonitoringService()
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

        service = StubNetworksMonitoringService()
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
