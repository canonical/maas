# Copyright 2016-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~provisioningserver.rpc.pod`."""

__all__ = []

import random
import re
from unittest.mock import MagicMock

from maastesting.factory import factory
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from provisioningserver.drivers.pod import (
    DiscoveredPod,
    DiscoveredPodHints,
)
from provisioningserver.drivers.pod.registry import PodDriverRegistry
from provisioningserver.rpc import (
    exceptions,
    pods,
)
from testtools import ExpectedException
from twisted.internet.defer import (
    fail,
    inlineCallbacks,
    succeed,
)


class TestDiscoverPod(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    @inlineCallbacks
    def test_unknown_pod_raises_UnknownPodType(self):
        unknown_type = factory.make_name("unknown")
        with ExpectedException(exceptions.UnknownPodType):
            yield pods.discover_pod(unknown_type, {})

    @inlineCallbacks
    def test_handles_driver_not_returning_Deferred(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_driver.discover.return_value = None
        self.patch(
            PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
                exceptions.PodActionFail,
                re.escape("bad pod driver; did not return Deferred.")):
            yield pods.discover_pod(fake_driver.name, {})

    @inlineCallbacks
    def test_handles_driver_resolving_to_None(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_driver.discover.return_value = succeed(None)
        self.patch(
            PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
                exceptions.PodActionFail,
                re.escape("unable to discover pod information.")):
            yield pods.discover_pod(fake_driver.name, {})

    @inlineCallbacks
    def test_handles_driver_not_resolving_to_DiscoveredPod(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_driver.discover.return_value = succeed({})
        self.patch(
            PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
                exceptions.PodActionFail,
                re.escape("bad pod driver; invalid result.")):
            yield pods.discover_pod(fake_driver.name, {})

    @inlineCallbacks
    def test_handles_driver_resolving_to_DiscoveredPod(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        discovered_pod = DiscoveredPod(
            architectures=['amd64/generic'],
            cores=random.randint(1, 8),
            cpu_speed=random.randint(1000, 3000),
            memory=random.randint(1024, 8192),
            local_storage=0,
            hints=DiscoveredPodHints(
                cores=random.randint(1, 8),
                cpu_speed=random.randint(1000, 2000),
                memory=random.randint(1024, 8192), local_storage=0),
            machines=[])
        fake_driver.discover.return_value = succeed(discovered_pod)
        self.patch(
            PodDriverRegistry, "get_item").return_value = fake_driver
        result = yield pods.discover_pod(fake_driver.name, {})
        self.assertEquals({
            "pod": discovered_pod,
        }, result)

    @inlineCallbacks
    def test_handles_driver_raising_NotImplementedError(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_driver.discover.return_value = fail(NotImplementedError())
        self.patch(
            PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(NotImplementedError):
            yield pods.discover_pod(fake_driver.name, {})

    @inlineCallbacks
    def test_handles_driver_raising_any_Exception(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_exception_type = factory.make_exception_type()
        fake_exception_msg = factory.make_name("error")
        fake_exception = fake_exception_type(fake_exception_msg)
        fake_driver.discover.return_value = fail(fake_exception)
        self.patch(
            PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
                exceptions.PodActionFail,
                re.escape("Failed talking to pod: " + fake_exception_msg)):
            yield pods.discover_pod(fake_driver.name, {})
