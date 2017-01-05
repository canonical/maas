# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test for :py:mod:`maasserver.clusterrpc.power`."""

__all__ = []

import random
from unittest.mock import (
    Mock,
    sentinel,
)

from crochet import wait_for
from maasserver.clusterrpc import chassis as chassis_module
from maasserver.clusterrpc.chassis import (
    discover_chassis,
    get_best_discovered_result,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.chassis import (
    DiscoveredChassis,
    DiscoveredChassisHints,
)
from provisioningserver.rpc.exceptions import (
    ChassisActionFail,
    UnknownChassisType,
)
from testtools.matchers import (
    Equals,
    Is,
    IsInstance,
    MatchesAny,
    MatchesDict,
)
from twisted.internet import reactor
from twisted.internet.defer import (
    CancelledError,
    fail,
    inlineCallbacks,
    succeed,
)
from twisted.internet.task import deferLater


wait_for_reactor = wait_for(30)  # 30 seconds.


class TestDiscoverChassis(MAASTransactionServerTestCase):
    """Tests for `discover_chassis`."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_DiscoverChassis_on_all_clients(self):
        rack_ids = [
            factory.make_name("system_id")
            for _ in range(3)
        ]
        chassis = DiscoveredChassis(
            architecture='amd64/generic',
            cores=random.randint(1, 8),
            cpu_speed=random.randint(1000, 3000),
            memory=random.randint(1024, 4096),
            local_storage=random.randint(500, 1000),
            hints=DiscoveredChassisHints(
                cores=random.randint(1, 8),
                cpu_speed=random.randint(1000, 3000),
                memory=random.randint(1024, 4096),
                local_storage=random.randint(500, 1000)))
        clients = []
        for rack_id in rack_ids:
            client = Mock()
            client.ident = rack_id
            client.return_value = succeed({
                "chassis": chassis,
            })
            clients.append(client)

        self.patch(chassis_module, "getAllClients").return_value = clients
        discovered = yield discover_chassis(factory.make_name("chassis"), {})
        self.assertEquals(({
            rack_id: chassis
            for rack_id in rack_ids
        }, {}), discovered)

    @wait_for_reactor
    @inlineCallbacks
    def test__returns_discovered_chassis_and_errors(self):
        chassis_type = factory.make_name("chassis")
        chassis = DiscoveredChassis(
            architecture='amd64/generic',
            cores=random.randint(1, 8),
            cpu_speed=random.randint(1000, 3000),
            memory=random.randint(1024, 4096),
            local_storage=random.randint(500, 1000),
            hints=DiscoveredChassisHints(
                cores=random.randint(1, 8),
                cpu_speed=random.randint(1000, 3000),
                memory=random.randint(1024, 4096),
                local_storage=random.randint(500, 1000)))

        clients = []
        client = Mock()
        error_rack_id = factory.make_name("system_id")
        client.ident = error_rack_id
        exception = UnknownChassisType(chassis_type)
        client.return_value = fail(exception)
        clients.append(client)

        valid_rack_id = factory.make_name("system_id")
        client = Mock()
        client.ident = valid_rack_id
        client.return_value = succeed({
            "chassis": chassis
        })
        clients.append(client)

        self.patch(chassis_module, "getAllClients").return_value = clients
        discovered = yield discover_chassis(chassis_type, {})
        self.assertEquals(({
            valid_rack_id: chassis,
        }, {
            error_rack_id: exception,
        }), discovered)

    @wait_for_reactor
    @inlineCallbacks
    def test__handles_timeout(self):

        def defer_way_later(*args, **kwargs):
            # Create a defer that will finish in 1 minute.
            return deferLater(reactor, 60 * 60, lambda: None)

        rack_id = factory.make_name("system_id")
        client = Mock()
        client.ident = rack_id
        client.side_effect = defer_way_later

        self.patch(chassis_module, "getAllClients").return_value = [client]
        discovered = yield discover_chassis(
            factory.make_name("chassis"), {}, timeout=0.5)
        self.assertThat(discovered[0], Equals({}))
        self.assertThat(discovered[1], MatchesDict({
            rack_id: IsInstance(CancelledError),
        }))


class TestGetBestDiscoveredResult(MAASTestCase):

    def test_returns_one_of_the_discovered(self):
        self.assertThat(get_best_discovered_result(({
            factory.make_name("system_id"): sentinel.first,
            factory.make_name("system_id"): sentinel.second,
            }, {})), MatchesAny(Is(sentinel.first), Is(sentinel.second)))

    def test_returns_None(self):
        self.assertIsNone(get_best_discovered_result(({}, {})))

    def test_raises_unknown_exception(self):
        exc_type = factory.make_exception_type()
        self.assertRaises(exc_type, get_best_discovered_result, ({}, {
            factory.make_name("system_id"): exc_type(),
        }))

    def test_raises_UnknownChassisType_over_unknown(self):
        exc_type = factory.make_exception_type()
        self.assertRaises(
            UnknownChassisType, get_best_discovered_result, ({}, {
                factory.make_name("system_id"): exc_type(),
                factory.make_name("system_id"): UnknownChassisType("unknown"),
            }))

    def test_raises_NotImplemended_over_UnknownChassisType(self):
        exc_type = factory.make_exception_type()
        self.assertRaises(
            NotImplementedError, get_best_discovered_result, ({}, {
                factory.make_name("system_id"): exc_type(),
                factory.make_name("system_id"): UnknownChassisType("unknown"),
                factory.make_name("system_id"): NotImplementedError(),
            }))

    def test_raises_ChassisActionFail_over_NotImplemended(self):
        exc_type = factory.make_exception_type()
        self.assertRaises(
            ChassisActionFail, get_best_discovered_result, ({}, {
                factory.make_name("system_id"): exc_type(),
                factory.make_name("system_id"): UnknownChassisType("unknown"),
                factory.make_name("system_id"): NotImplementedError(),
                factory.make_name("system_id"): ChassisActionFail(),
            }))
