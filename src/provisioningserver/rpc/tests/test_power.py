# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~provisioningserver.rpc.power`."""


import logging
import random
from unittest import TestCase
from unittest.mock import ANY, call, sentinel

from fixtures import FakeLogger
from twisted.internet import reactor
from twisted.internet.defer import (
    fail,
    inlineCallbacks,
    maybeDeferred,
    succeed,
)
from twisted.internet.task import Clock
from twisted.python.failure import Failure

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from maastesting.twisted import (
    always_fail_with,
    extract_result,
    TwistedLoggerFixture,
)
from provisioningserver.drivers.power import DEFAULT_WAITING_POLICY, PowerError
from provisioningserver.drivers.power.registry import PowerDriverRegistry
from provisioningserver.events import EVENT_TYPES
from provisioningserver.rpc import clusterservice, exceptions, power, region
from provisioningserver.rpc.testing import MockClusterToRegionRPCFixture
from provisioningserver.testing.events import EventTypesAllRegistered

TIMEOUT = get_testing_timeout()


def suppress_reporting(test):
    # Skip telling the region; just pass-through the query result.
    report_power_state = test.patch(power, "report_power_state")
    report_power_state.side_effect = lambda d, system_id, hostname: d


class TestPowerHelpers(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.useFixture(EventTypesAllRegistered())
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}

    def patch_rpc_methods(self):
        fixture = self.useFixture(MockClusterToRegionRPCFixture())
        protocol, io = fixture.makeEventLoop(
            region.MarkNodeFailed,
            region.UpdateNodePowerState,
            region.SendEvent,
        )
        return protocol, io

    def test_power_state_update_calls_UpdateNodePowerState(self):
        system_id = factory.make_name("system_id")
        state = random.choice(["on", "off"])
        protocol, io = self.patch_rpc_methods()
        d = power.power_state_update(system_id, state)
        # This blocks until the deferred is complete
        io.flush()
        self.assertEqual(extract_result(d), {})
        protocol.UpdateNodePowerState.assert_called_once_with(
            ANY, system_id=system_id, power_state=state
        )


class TestPowerQuery(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.useFixture(EventTypesAllRegistered())
        self.patch(power, "deferToThread", maybeDeferred)
        for _, power_driver in PowerDriverRegistry:
            self.patch(
                power_driver, "detect_missing_packages"
            ).return_value = []
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}

    def patch_rpc_methods(self, return_value={}, side_effect=None):
        fixture = self.useFixture(MockClusterToRegionRPCFixture())
        protocol, io = fixture.makeEventLoop(
            region.MarkNodeFailed,
            region.SendEvent,
            region.UpdateNodePowerState,
        )
        protocol.MarkNodeFailed.return_value = return_value
        protocol.MarkNodeFailed.side_effect = side_effect
        return protocol.SendEvent, protocol.MarkNodeFailed, io

    def test_power_query_failure_emits_event(self):
        system_id = factory.make_name("system_id")
        hostname = factory.make_name("hostname")
        message = factory.make_name("message")
        SendEvent, _, io = self.patch_rpc_methods()
        d = power.power_query_failure(
            system_id, hostname, Failure(Exception(message))
        )
        # This blocks until the deferred is complete.
        io.flush()
        self.assertIsNone(extract_result(d))
        SendEvent.assert_called_once_with(
            ANY,
            type_name=EVENT_TYPES.NODE_POWER_QUERY_FAILED,
            system_id=system_id,
            description=message,
        )

    def test_get_power_state_queries_node(self):
        system_id = factory.make_name("system_id")
        hostname = factory.make_name("hostname")
        power_driver = random.choice(
            [driver for _, driver in PowerDriverRegistry if driver.queryable]
        )
        power_state = random.choice(["on", "off"])
        context = {
            factory.make_name("context-key"): factory.make_name("context-val")
        }
        self.patch(power, "is_driver_available").return_value = True
        _, markNodeBroken, io = self.patch_rpc_methods()
        mock_perform_power_driver_query = self.patch(
            power, "perform_power_driver_query"
        )
        mock_perform_power_driver_query.return_value = power_state

        d = power.get_power_state(
            system_id, hostname, power_driver.name, context
        )
        # This blocks until the deferred is complete.
        io.flush()
        self.assertEqual(power_state, extract_result(d))
        power_driver.detect_missing_packages.assert_called_once_with()
        power.perform_power_driver_query.assert_called_once_with(
            system_id,
            hostname,
            power_driver.name,
            context,
        )

    @inlineCallbacks
    def test_get_power_state_fails_for_missing_packages(self):
        system_id = factory.make_name("system_id")
        hostname = factory.make_name("hostname")
        power_driver = random.choice(
            [driver for _, driver in PowerDriverRegistry if driver.queryable]
        )
        context = {
            factory.make_name("context-key"): factory.make_name("context-val")
        }
        self.patch(power, "is_driver_available").return_value = False
        _, markNodeBroken, io = self.patch_rpc_methods()

        power_driver.detect_missing_packages.return_value = ["gone"]

        d = power.get_power_state(
            system_id, hostname, power_driver.name, context
        )
        # This blocks until the deferred is complete.
        io.flush()

        power_driver.detect_missing_packages.assert_called_once_with()
        with TestCase.assertRaises(self, exceptions.PowerActionFail):
            yield d

    def test_report_power_state_changes_power_state_if_failure(self):
        system_id = factory.make_name("system_id")
        hostname = factory.make_name("hostname")
        err_msg = factory.make_name("error")

        _, _, io = self.patch_rpc_methods()
        self.patch_autospec(power, "power_state_update")

        # Simulate a failure when querying state.
        query = fail(exceptions.PowerActionFail(err_msg))
        report = power.report_power_state(query, system_id, hostname)
        # This blocks until the deferred is complete.
        io.flush()

        error = self.assertRaises(
            exceptions.PowerActionFail, extract_result, report
        )
        self.assertEqual(err_msg, str(error))
        power.power_state_update.assert_called_once_with(system_id, "error")

    def test_report_power_state_changes_power_state_if_success(self):
        system_id = factory.make_name("system_id")
        hostname = factory.make_name("hostname")
        power_state = random.choice(["on", "off"])

        _, _, io = self.patch_rpc_methods()
        self.patch_autospec(power, "power_state_update")

        # Simulate a success when querying state.
        query = succeed(power_state)
        report = power.report_power_state(query, system_id, hostname)
        # This blocks until the deferred is complete.
        io.flush()

        self.assertEqual(power_state, extract_result(report))
        power.power_state_update.assert_called_once_with(
            system_id, power_state
        )

    def test_report_power_state_changes_power_state_if_unknown(self):
        system_id = factory.make_name("system_id")
        hostname = factory.make_name("hostname")
        power_state = "unknown"

        _, _, io = self.patch_rpc_methods()
        self.patch_autospec(power, "power_state_update")

        # Simulate a success when querying state.
        query = succeed(power_state)
        report = power.report_power_state(query, system_id, hostname)
        # This blocks until the deferred is complete.
        io.flush()

        self.assertEqual(power_state, extract_result(report))
        power.power_state_update.assert_called_once_with(
            system_id, power_state
        )


class TestPowerQueryExceptions(MAASTestCase):
    scenarios = tuple(
        (
            driver.name,
            {
                "power_type": driver.name,
                "power_driver": driver,
                "func": (  # Function to invoke power driver.
                    "perform_power_driver_query"
                ),
                "waits": (  # Pauses between retries.
                    []
                    if driver.name in PowerDriverRegistry
                    else DEFAULT_WAITING_POLICY
                ),
                "calls": (  # No. of calls to the driver.
                    1
                    if driver.name in PowerDriverRegistry
                    else len(DEFAULT_WAITING_POLICY)
                ),
            },
        )
        for _, driver in PowerDriverRegistry
        if driver.queryable
    )

    def test_report_power_state_reports_all_exceptions(self):
        logger_twisted = self.useFixture(TwistedLoggerFixture())
        logger_maaslog = self.useFixture(FakeLogger("maas"))

        # Avoid threads here.
        self.patch(power, "deferToThread", maybeDeferred)

        exception_type = factory.make_exception_type()
        exception_message = factory.make_string()
        exception = exception_type(exception_message)

        # Pretend the query always fails with `exception`.
        query = self.patch_autospec(power, self.func)
        query.side_effect = always_fail_with(exception)

        # Intercept calls to power_state_update() and send_node_event().
        power_state_update = self.patch_autospec(power, "power_state_update")
        power_state_update.return_value = succeed(None)
        send_node_event = self.patch_autospec(power, "send_node_event")
        send_node_event.return_value = succeed(None)

        self.patch(
            self.power_driver, "detect_missing_packages"
        ).return_value = []

        system_id = factory.make_name("system_id")
        hostname = factory.make_name("hostname")
        context = sentinel.context
        clock = Clock()

        d = power.get_power_state(
            system_id, hostname, self.power_type, context, clock
        )
        d = power.report_power_state(d, system_id, hostname)

        # Crank through some number of retries.
        for wait in self.waits:
            self.assertFalse(d.called)
            clock.advance(wait)
        self.assertTrue(d.called)

        # Finally the exception from the query is raised.
        self.assertRaises(exception_type, extract_result, d)

        # The broken power query function patched earlier was called the same
        # number of times as there are steps in the default waiting policy.
        expected_call = call(system_id, hostname, self.power_type, context)
        expected_calls = [expected_call] * self.calls
        query.assert_has_calls(expected_calls)

        expected_message = "{}: Power state could not be queried: {}".format(
            hostname,
            exception_message,
        )

        # An attempt was made to report the failure to the region.
        power_state_update.assert_called_once_with(system_id, "error")
        # An attempt was made to log a node event with details.
        send_node_event.assert_called_once_with(
            EVENT_TYPES.NODE_POWER_QUERY_FAILED,
            system_id,
            hostname,
            exception_message,
        )

        # Nothing was logged to the Twisted log.
        self.assertEqual("", logger_twisted.output)
        # A brief message is written to maaslog.
        self.assertEqual(expected_message + "\n", logger_maaslog.output)


class TestPowerQueryAsync(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def make_node(self, power_type=None):
        system_id = factory.make_name("system_id")
        hostname = factory.make_name("hostname")
        if power_type is None:
            power_type = random.choice(
                [
                    driver.name
                    for _, driver in PowerDriverRegistry
                    if driver.queryable
                ]
            )
        state = random.choice(["on", "off", "unknown", "error"])
        context = {
            factory.make_name("context-key"): (
                factory.make_name("context-val")
            )
        }
        return {
            "context": context,
            "hostname": hostname,
            "power_state": state,
            "power_type": power_type,
            "system_id": system_id,
        }

    def make_nodes(self, count=3):
        nodes = [self.make_node() for _ in range(count)]
        # Sanity check that these nodes are something that can emerge
        # from a call to ListNodePowerParameters.
        region.ListNodePowerParameters.makeResponse({"nodes": nodes}, None)
        return nodes

    def pick_alternate_state(self, state):
        return random.choice(
            [
                value
                for value in ["on", "off", "unknown", "error"]
                if value != state
            ]
        )

    @inlineCallbacks
    def test_query_all_nodes_gets_and_reports_power_state(self):
        nodes = self.make_nodes()

        # Report back that all nodes' power states are as recorded.
        power_states = [node["power_state"] for node in nodes]
        queries = list(map(succeed, power_states))
        get_power_state = self.patch(power, "get_power_state")
        get_power_state.side_effect = queries
        report_power_state = self.patch(power, "report_power_state")
        report_power_state.side_effect = lambda d, sid, hn: d

        yield power.query_all_nodes(nodes)
        get_power_state.assert_has_calls(
            [
                call(
                    node["system_id"],
                    node["hostname"],
                    node["power_type"],
                    node["context"],
                    clock=reactor,
                )
                for node in nodes
            ]
        )
        report_power_state.assert_has_calls(
            [
                call(query, node["system_id"], node["hostname"])
                for query, node in zip(queries, nodes)
            ]
        )

    @inlineCallbacks
    def test_query_all_nodes_skips_nodes_in_action_registry(self):
        nodes = self.make_nodes()

        # First node is in the registry.
        first_system_id = nodes[0]["system_id"]
        power.power_action_registry[first_system_id] = sentinel.action
        self.addCleanup(power.power_action_registry.pop, first_system_id)

        # Report back power state of nodes' not in registry.
        power_states = [node["power_state"] for node in nodes[1:]]
        get_power_state = self.patch(power, "get_power_state")
        get_power_state.side_effect = map(succeed, power_states)
        suppress_reporting(self)

        yield power.query_all_nodes(nodes)
        get_power_state.assert_has_calls(
            [
                call(
                    node["system_id"],
                    node["hostname"],
                    node["power_type"],
                    node["context"],
                    clock=reactor,
                )
                for node in nodes[1:]
            ]
        )
        self.assertNotIn(
            call(
                nodes[0]["system_id"],
                nodes[0]["hostname"],
                nodes[0]["power_type"],
                nodes[0]["context"],
                clock=reactor,
            ),
            get_power_state.mock_calls,
        )

    @inlineCallbacks
    def test_query_all_nodes_only_queries_queryable_power_types(self):
        nodes = self.make_nodes()
        # nodes are all queryable, so add one that isn't:
        nodes.append(self.make_node(power_type="manual"))

        # Report back that all nodes' power states are as recorded.
        power_states = [node["power_state"] for node in nodes]
        get_power_state = self.patch(power, "get_power_state")
        get_power_state.side_effect = map(succeed, power_states)
        suppress_reporting(self)

        yield power.query_all_nodes(nodes)
        get_power_state.assert_has_calls(
            [
                call(
                    node["system_id"],
                    node["hostname"],
                    node["power_type"],
                    node["context"],
                    clock=reactor,
                )
                for node in nodes
                if node["power_type"] in PowerDriverRegistry
            ]
        )

    @inlineCallbacks
    def test_query_all_nodes_swallows_PowerActionFail(self):
        node1, node2 = self.make_nodes(2)
        new_state_2 = self.pick_alternate_state(node2["power_state"])
        get_power_state = self.patch(power, "get_power_state")
        error_msg = factory.make_name("error")
        get_power_state.side_effect = [
            fail(exceptions.PowerActionFail(error_msg)),
            succeed(new_state_2),
        ]
        suppress_reporting(self)

        with FakeLogger("maas.power", level=logging.DEBUG) as maaslog:
            yield power.query_all_nodes([node1, node2])

        self.assertRegex(
            maaslog.output,
            rf"hostname-.*: Could not query power state: {error_msg}",
        )
        self.assertRegex(
            maaslog.output,
            rf"hostname-.*: Power state has changed from .* to {new_state_2}",
        )

    @inlineCallbacks
    def test_query_all_nodes_swallows_PowerError(self):
        node1, node2 = self.make_nodes(2)
        new_state_2 = self.pick_alternate_state(node2["power_state"])
        get_power_state = self.patch(power, "get_power_state")
        error_msg = factory.make_name("error")
        get_power_state.side_effect = [
            fail(PowerError(error_msg)),
            succeed(new_state_2),
        ]
        suppress_reporting(self)

        with FakeLogger("maas.power", level=logging.DEBUG) as maaslog:
            yield power.query_all_nodes([node1, node2])

        self.assertRegex(
            maaslog.output,
            rf"{node1['hostname']}: Could not query power state: {error_msg}",
        )
        self.assertRegex(
            maaslog.output,
            rf"{node2['hostname']}: Power state has changed from {node2['power_state']} to {new_state_2}",
        )

    @inlineCallbacks
    def test_query_all_nodes_swallows_NoSuchNode(self):
        node1, node2 = self.make_nodes(2)
        new_state_2 = self.pick_alternate_state(node2["power_state"])
        get_power_state = self.patch(power, "get_power_state")
        get_power_state.side_effect = [
            fail(exceptions.NoSuchNode()),
            succeed(new_state_2),
        ]
        suppress_reporting(self)

        with FakeLogger("maas.power", level=logging.DEBUG) as maaslog:
            yield power.query_all_nodes([node1, node2])

        self.assertRegex(
            maaslog.output,
            rf"{node2['hostname']}: Power state has changed from {node2['power_state']} to {new_state_2}",
        )

    @inlineCallbacks
    def test_query_all_nodes_swallows_Exception(self):
        node1, node2 = self.make_nodes(2)
        error_message = factory.make_name("error")
        error_type = factory.make_exception_type()
        new_state_2 = self.pick_alternate_state(node2["power_state"])
        get_power_state = self.patch(power, "get_power_state")
        get_power_state.side_effect = [
            fail(error_type(error_message)),
            succeed(new_state_2),
        ]
        suppress_reporting(self)

        maaslog = FakeLogger("maas.power", level=logging.DEBUG)
        twistlog = TwistedLoggerFixture()

        with maaslog, twistlog:
            yield power.query_all_nodes([node1, node2])

        self.assertRegex(
            maaslog.output,
            rf"{node1['hostname']}: Failed to refresh power state: {error_message}",
        )
        self.assertRegex(
            maaslog.output,
            rf"{node2['hostname']}: Power state has changed from {node2['power_state']} to {new_state_2}",
        )

    @inlineCallbacks
    def test_query_all_nodes_returns_deferredlist_of_number_of_nodes(self):
        node1, node2 = self.make_nodes(2)
        get_power_state = self.patch(power, "get_power_state")
        get_power_state.side_effect = [
            succeed(node1["power_state"]),
            succeed(node2["power_state"]),
        ]
        suppress_reporting(self)

        results = yield power.query_all_nodes([node1, node2])
        self.assertEqual(
            [(True, node1["power_state"]), (True, node2["power_state"])],
            results,
        )
