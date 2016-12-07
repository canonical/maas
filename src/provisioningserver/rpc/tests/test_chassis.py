# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~provisioningserver.rpc.chassis`."""

__all__ = []

import random
import re
from unittest.mock import MagicMock

from maastesting.factory import factory
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from provisioningserver.drivers.chassis import (
    ChassisDriverRegistry,
    DiscoveredChassis,
    DiscoveredChassisHints,
)
from provisioningserver.rpc import (
    chassis,
    exceptions,
)
from testtools import ExpectedException
from twisted.internet.defer import (
    fail,
    inlineCallbacks,
    succeed,
)


class TestDiscoverChassis(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    @inlineCallbacks
    def test_unknown_chassis_raises_UnknownChassisType(self):
        unknown_type = factory.make_name("unknown")
        with ExpectedException(exceptions.UnknownChassisType):
            yield chassis.discover_chassis(unknown_type, {})

    @inlineCallbacks
    def test_handles_driver_not_returning_Deferred(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("chassis")
        fake_driver.discover.return_value = None
        self.patch(
            ChassisDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
                exceptions.ChassisActionFail,
                re.escape("bad chassis driver; did not return Deferred.")):
            yield chassis.discover_chassis(fake_driver.name, {})

    @inlineCallbacks
    def test_handles_driver_resolving_to_None(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("chassis")
        fake_driver.discover.return_value = succeed(None)
        self.patch(
            ChassisDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
                exceptions.ChassisActionFail,
                re.escape("unable to discover chassis information.")):
            yield chassis.discover_chassis(fake_driver.name, {})

    @inlineCallbacks
    def test_handles_driver_not_resolving_to_DiscoveredChassis(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("chassis")
        fake_driver.discover.return_value = succeed({})
        self.patch(
            ChassisDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
                exceptions.ChassisActionFail,
                re.escape("bad chassis driver; invalid result.")):
            yield chassis.discover_chassis(fake_driver.name, {})

    @inlineCallbacks
    def test_handles_driver_resolving_to_DiscoveredChassis(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("chassis")
        discovered_chassis = DiscoveredChassis(
            cores=random.randint(1, 8),
            cpu_speed=random.randint(1000, 3000),
            memory=random.randint(1024, 8192),
            local_storage=0,
            hints=DiscoveredChassisHints(
                cores=random.randint(1, 8),
                cpu_speed=random.randint(1000, 2000),
                memory=random.randint(1024, 8192), local_storage=0),
            machines=[])
        fake_driver.discover.return_value = succeed(discovered_chassis)
        self.patch(
            ChassisDriverRegistry, "get_item").return_value = fake_driver
        result = yield chassis.discover_chassis(fake_driver.name, {})
        self.assertEquals({
            "chassis": discovered_chassis,
        }, result)

    @inlineCallbacks
    def test_handles_driver_raising_NotImplementedError(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("chassis")
        fake_driver.discover.return_value = fail(NotImplementedError())
        self.patch(
            ChassisDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(NotImplementedError):
            yield chassis.discover_chassis(fake_driver.name, {})

    @inlineCallbacks
    def test_handles_driver_raising_any_Exception(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("chassis")
        fake_exception_type = factory.make_exception_type()
        fake_exception_msg = factory.make_name("error")
        fake_exception = fake_exception_type(fake_exception_msg)
        fake_driver.discover.return_value = fail(fake_exception)
        self.patch(
            ChassisDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
                exceptions.ChassisActionFail,
                re.escape("Failed talking to chassis: " + fake_exception_msg)):
            yield chassis.discover_chassis(fake_driver.name, {})
