# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~provisioningserver.rpc.power`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import logging
import random

from fixtures import FakeLogger
from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
    )
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
    )
from mock import (
    ANY,
    call,
    DEFAULT,
    Mock,
    sentinel,
    )
import provisioningserver
from provisioningserver.events import EVENT_TYPES
from provisioningserver.power.poweraction import PowerActionFail
from provisioningserver.rpc import (
    exceptions,
    power,
    region,
    )
from provisioningserver.rpc.testing import (
    always_succeed_with,
    MockClusterToRegionRPCFixture,
    MockLiveClusterToRegionRPCFixture,
    )
from testtools import ExpectedException
from testtools.deferredruntest import (
    assert_fails_with,
    extract_result,
    )
from testtools.matchers import IsInstance
from twisted.internet import reactor
from twisted.internet.defer import (
    Deferred,
    inlineCallbacks,
    maybeDeferred,
    returnValue,
    )
from twisted.internet.task import Clock


def patch_power_action(test, return_value=DEFAULT, side_effect=None):
    """Patch the PowerAction object.

    Patch the PowerAction object so that PowerAction().execute
    is replaced by a Mock object created using the given `return_value`
    and `side_effect`.

    This can be used to simulate various successes or failures patterns
    while manipulating the power state of a node.

    Returns a tuple of mock objects: power.PowerAction and
    power.PowerAction().execute.
    """
    power_action_obj = Mock()
    power_action_obj_execute = Mock(
        return_value=return_value, side_effect=side_effect)
    power_action_obj.execute = power_action_obj_execute
    power_action = test.patch(power, 'PowerAction')
    power_action.return_value = power_action_obj
    return power_action, power_action_obj_execute


class TestPowerHelpers(MAASTestCase):

    def patch_rpc_methods(self):
        fixture = self.useFixture(MockClusterToRegionRPCFixture())
        protocol, io = fixture.makeEventLoop(
            region.MarkNodeFailed, region.UpdateNodePowerState,
            region.SendEvent)
        return protocol, io

    def test_power_change_success_emits_event(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_change = 'on'
        protocol, io = self.patch_rpc_methods()
        d = power.power_change_success(system_id, hostname, power_change)
        io.flush()
        self.assertThat(
            protocol.UpdateNodePowerState,
            MockCalledOnceWith(
                ANY,
                system_id=system_id,
                power_state=power_change)
        )
        self.assertThat(
            protocol.SendEvent,
            MockCalledOnceWith(
                ANY,
                type_name=EVENT_TYPES.NODE_POWERED_ON,
                system_id=system_id,
                description='')
        )
        self.assertIsNone(extract_result(d))

    def test_power_change_starting_emits_event(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_change = 'on'
        protocol, io = self.patch_rpc_methods()
        d = power.power_change_starting(system_id, hostname, power_change)
        io.flush()
        self.assertThat(
            protocol.SendEvent,
            MockCalledOnceWith(
                ANY,
                type_name=EVENT_TYPES.NODE_POWER_ON_STARTING,
                system_id=system_id,
                description='')
        )
        self.assertIsNone(extract_result(d))

    def test_power_change_failure_emits_event(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        message = factory.make_name('message')
        power_change = 'on'
        protocol, io = self.patch_rpc_methods()
        d = power.power_change_failure(
            system_id, hostname, power_change, message)
        io.flush()
        self.assertThat(
            protocol.SendEvent,
            MockCalledOnceWith(
                ANY,
                type_name=EVENT_TYPES.NODE_POWER_ON_FAILED,
                system_id=system_id,
                description=message)
        )
        self.assertIsNone(extract_result(d))

    def test_power_query_failure_emits_event(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        message = factory.make_name('message')
        protocol, io = self.patch_rpc_methods()
        d = power.power_query_failure(
            system_id, hostname, message)
        # This blocks until the deferred is complete
        io.flush()
        self.assertIsNone(extract_result(d))
        self.assertThat(
            protocol.SendEvent,
            MockCalledOnceWith(
                ANY,
                type_name=EVENT_TYPES.NODE_POWER_QUERY_FAILED,
                system_id=system_id,
                description=message)
        )

    def test_power_state_update_calls_UpdateNodePowerState(self):
        system_id = factory.make_name('system_id')
        state = random.choice(['on', 'off'])
        protocol, io = self.patch_rpc_methods()
        d = power.power_state_update(
            system_id, state)
        # This blocks until the deferred is complete
        io.flush()
        self.assertIsNone(extract_result(d))
        self.assertThat(
            protocol.UpdateNodePowerState,
            MockCalledOnceWith(
                ANY,
                system_id=system_id,
                power_state=state)
        )


class TestChangePowerState(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    @inlineCallbacks
    def patch_rpc_methods(self, return_value={}, side_effect=None):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.MarkNodeFailed, region.UpdateNodePowerState,
            region.SendEvent)
        protocol.MarkNodeFailed.return_value = return_value
        protocol.MarkNodeFailed.side_effect = side_effect
        self.addCleanup((yield connecting))
        returnValue(protocol.MarkNodeFailed)

    def test_change_power_state_calls_power_change_starting_early_on(self):
        # The first, or one of the first, things that change_power_state()
        # does is write to the node event log via power_change_starting().

        class ArbitraryException(Exception):
            """This allows us to return early from a function."""

        # Raise this exception when power_change_starting() is called, to
        # return early from change_power_state(). This lets us avoid set-up
        # for parts of the function that we're presently not interested in.
        self.patch_autospec(power, "power_change_starting")
        power.power_change_starting.side_effect = ArbitraryException()

        d = power.change_power_state(
            sentinel.system_id, sentinel.hostname, sentinel.power_type,
            sentinel.power_change, sentinel.context)
        self.assertRaises(ArbitraryException, extract_result, d)
        self.assertThat(
            power.power_change_starting, MockCalledOnceWith(
                sentinel.system_id, sentinel.hostname, sentinel.power_change))

    @inlineCallbacks
    def test_change_power_state_changes_power_state(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = random.choice(['on', 'off'])
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'pause')
        power.power_action_registry[system_id] = power_change
        # Patch the power action utility so that it says the node is
        # in the required power state.
        power_action, execute = patch_power_action(
            self, return_value=power_change)
        markNodeBroken = yield self.patch_rpc_methods()

        yield power.change_power_state(
            system_id, hostname, power_type, power_change, context)
        self.assertThat(
            execute,
            MockCallsMatch(
                # One call to change the power state.
                call(power_change=power_change, **context),
                # One call to query the power state.
                call(power_change='query', **context),
            ),
        )
        # The node hasn't been marked broken.
        self.assertThat(markNodeBroken, MockNotCalled())

    @inlineCallbacks
    def test_change_power_state_doesnt_retry_for_certain_power_types(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        # Use a power type that is not among power.QUERY_POWER_TYPES.
        power_type = factory.make_name('power_type')
        power_change = random.choice(['on', 'off'])
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        power.power_action_registry[system_id] = power_change
        self.patch(power, 'pause')
        power_action, execute = patch_power_action(
            self, return_value=random.choice(['on', 'off']))
        markNodeBroken = yield self.patch_rpc_methods()

        yield power.change_power_state(
            system_id, hostname, power_type, power_change, context)
        self.assertThat(
            execute,
            MockCallsMatch(
                # Only one call to change the power state.
                call(power_change=power_change, **context),
            ),
        )
        # The node hasn't been marked broken.
        self.assertThat(markNodeBroken, MockNotCalled())

    @inlineCallbacks
    def test_change_power_state_retries_if_power_state_doesnt_change(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = 'on'
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'pause')
        power.power_action_registry[system_id] = power_change
        # Simulate a failure to power up the node, then a success.
        power_action, execute = patch_power_action(
            self, side_effect=[None, 'off', None, 'on'])
        markNodeBroken = yield self.patch_rpc_methods()

        yield power.change_power_state(
            system_id, hostname, power_type, power_change, context)
        self.assertThat(
            execute,
            MockCallsMatch(
                call(power_change=power_change, **context),
                call(power_change='query', **context),
                call(power_change=power_change, **context),
                call(power_change='query', **context),
            )
        )
        # The node hasn't been marked broken.
        self.assertThat(markNodeBroken, MockNotCalled())

    @inlineCallbacks
    def test_change_power_state_marks_the_node_broken_if_failure(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = 'on'
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'pause')
        power.power_action_registry[system_id] = power_change
        # Simulate a persistent failure.
        power_action, execute = patch_power_action(
            self, return_value='off')
        markNodeBroken = yield self.patch_rpc_methods()

        yield power.change_power_state(
            system_id, hostname, power_type, power_change, context)

        # The node has been marked broken.
        msg = "Timeout after %s tries" % len(
            power.default_waiting_policy)
        self.assertThat(
            markNodeBroken,
            MockCalledOnceWith(
                ANY,
                system_id=system_id,
                error_description=msg)
        )

    @inlineCallbacks
    def test_change_power_state_marks_the_node_broken_if_exception(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = 'on'
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'pause')
        power.power_action_registry[system_id] = power_change
        # Simulate an exception.
        exception_message = factory.make_name('exception')
        power_action, execute = patch_power_action(
            self, side_effect=PowerActionFail(exception_message))
        markNodeBroken = yield self.patch_rpc_methods()

        with ExpectedException(PowerActionFail):
            yield power.change_power_state(
                system_id, hostname, power_type, power_change, context)

        error_message = "Node could not be powered on: %s" % exception_message
        self.assertThat(
            markNodeBroken, MockCalledOnceWith(
                ANY, system_id=system_id, error_description=error_message))

    @inlineCallbacks
    def test_change_power_state_pauses_inbetween_retries(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = 'on'
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        power.power_action_registry[system_id] = power_change
        # Simulate two failures to power up the node, then a success.
        power_action, execute = patch_power_action(
            self, side_effect=[None, 'off', None, 'off', None, 'on'])
        # Patch calls to pause() to `execute` so that we record both in the
        # same place, and can thus see ordering.
        self.patch(power, 'pause', execute)

        yield self.patch_rpc_methods()

        yield power.change_power_state(
            system_id, hostname, power_type, power_change, context)

        self.assertThat(execute, MockCallsMatch(
            call(power_change=power_change, **context),
            call(1, reactor),  # pause(1, reactor)
            call(power_change='query', **context),
            call(power_change=power_change, **context),
            call(1, reactor),  # pause(1, reactor)
            call(power_change='query', **context),
        ))

    @inlineCallbacks
    def test_change_power_state_removes_action_from_registry_on_success(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = random.choice(['on', 'off'])
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'pause')
        power.power_action_registry[system_id] = power_change
        # Patch the power action utility so that it doesn't actually try
        # to do anything.
        power_action, execute = patch_power_action(
            self, return_value=power_change)
        yield self.patch_rpc_methods()

        yield power.change_power_state(
            system_id, hostname, power_type, power_change, context)
        self.assertNotIn(system_id, power.power_action_registry.keys())

    @inlineCallbacks
    def test_change_power_state_removes_action_from_registry_on_failure(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = 'on'
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'pause')
        power.power_action_registry[system_id] = power_change
        # Simulate a persistent failure.
        power_action, execute = patch_power_action(self, return_value='off')
        yield self.patch_rpc_methods()

        yield power.change_power_state(
            system_id, hostname, power_type, power_change, context)
        self.assertNotIn(system_id, power.power_action_registry.keys())

    @inlineCallbacks
    def test_change_power_state_removes_action_from_registry_on_error(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = 'on'
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'pause')
        power.power_action_registry[system_id] = power_change
        # Simulate an exception.
        exception_message = factory.make_name('exception')
        power_action, execute = patch_power_action(
            self, side_effect=PowerActionFail(exception_message))
        yield self.patch_rpc_methods()

        with ExpectedException(PowerActionFail):
            yield power.change_power_state(
                system_id, hostname, power_type, power_change, context)

        self.assertNotIn(system_id, power.power_action_registry.keys())


class TestPowerQuery(MAASTestCase):

    def setUp(self):
        super(TestPowerQuery, self).setUp()
        self.patch(
            provisioningserver.rpc.power, 'deferToThread', maybeDeferred)

    def patch_rpc_methods(self, return_value={}, side_effect=None):
        fixture = self.useFixture(MockClusterToRegionRPCFixture())
        protocol, io = fixture.makeEventLoop(
            region.MarkNodeFailed, region.SendEvent,
            region.UpdateNodePowerState)
        protocol.MarkNodeFailed.return_value = return_value
        protocol.MarkNodeFailed.side_effect = side_effect
        return protocol.SendEvent, protocol.MarkNodeFailed, io

    def test_get_power_state_querys_node(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_state = random.choice(['on', 'off'])
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'pause')
        # Patch the power action utility so that it says the node is
        # in on/off power state.
        power_action, execute = patch_power_action(
            self, return_value=power_state)
        _, markNodeBroken, io = self.patch_rpc_methods()

        d = power.get_power_state(
            system_id, hostname, power_type, context)
        # This blocks until the deferred is complete
        io.flush()
        self.assertEqual(power_state, extract_result(d))
        self.assertThat(
            execute,
            MockCallsMatch(
                # One call to change the power state.
                call(power_change='query', **context),
            ),
        )

    def test_get_power_state_returns_unknown_for_certain_power_types(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        # Use a power type that is not among power.QUERY_POWER_TYPES.
        power_type = factory.make_name('power_type')
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        _, _, io = self.patch_rpc_methods()

        d = power.get_power_state(
            system_id, hostname, power_type, context)

        return assert_fails_with(d, PowerActionFail)

    def test_get_power_state_retries_if_power_query_fails(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_state = random.choice(['on', 'off'])
        err_msg = factory.make_name('error')
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'pause')
        # Simulate a failure to power query the node, then success.
        power_action, execute = patch_power_action(
            self, side_effect=[PowerActionFail(err_msg), power_state])
        sendEvent, markNodeBroken, io = self.patch_rpc_methods()

        d = power.get_power_state(
            system_id, hostname, power_type, context)
        # This blocks until the deferred is complete
        io.flush()
        self.assertEqual(power_state, extract_result(d))
        self.assertThat(
            execute,
            MockCallsMatch(
                call(power_change='query', **context),
                call(power_change='query', **context),
            )
        )
        # The node hasn't been marked broken.
        self.assertThat(markNodeBroken, MockNotCalled())

    def test_get_power_state_changes_power_state_if_failure(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        err_msg = factory.make_name('error')
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'pause')
        power_state_update = self.patch_autospec(power, 'power_state_update')

        # Simulate a persistent failure.
        power_action, execute = patch_power_action(
            self, side_effect=PowerActionFail(err_msg))
        _, _, io = self.patch_rpc_methods()

        d = power.get_power_state(
            system_id, hostname, power_type, context)
        io.flush()
        d.addCallback(self.fail)

        error = self.assertRaises(PowerActionFail, extract_result, d)
        self.assertEqual(err_msg, unicode(error))
        self.assertThat(
            power_state_update, MockCalledOnceWith(system_id, 'error'))

    def test_get_power_state_changes_power_state_if_success(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_state = random.choice(['on', 'off'])
        power_type = random.choice(power.QUERY_POWER_TYPES)
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'pause')
        power_state_update = self.patch_autospec(power, 'power_state_update')

        # Simulate success.
        power_action, execute = patch_power_action(
            self, return_value=power_state)
        _, _, io = self.patch_rpc_methods()

        d = power.get_power_state(
            system_id, hostname, power_type, context)
        io.flush()
        self.assertEqual(power_state, extract_result(d))
        self.assertThat(
            power_state_update, MockCalledOnceWith(system_id, power_state))

    def test_get_power_state_pauses_inbetween_retries(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        # Simulate two failures to power up the node, then a success.
        power_action, execute = patch_power_action(
            self, side_effect=[PowerActionFail, PowerActionFail, 'off'])
        self.patch(power, "deferToThread", maybeDeferred)
        _, _, io = self.patch_rpc_methods()
        clock = Clock()

        calls_and_pause = [
            ([
                call(power_change='query', **context),
            ], 3),
            ([
                call(power_change='query', **context),
            ], 5),
            ([
                call(power_change='query', **context),
            ], 10),
        ]
        calls = []
        d = power.get_power_state(
            system_id, hostname, power_type, context, clock=clock)
        for newcalls, waiting_time in calls_and_pause:
            calls.extend(newcalls)
            # This blocks until the deferred is complete
            io.flush()
            self.assertThat(execute, MockCallsMatch(*calls))
            clock.advance(waiting_time)
        self.assertEqual("off", extract_result(d))


class TestPowerQueryAsync(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def make_node(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        state = random.choice(['on', 'off', 'unknown', 'error'])
        context = {
            factory.make_name('context-key'): (
                factory.make_name('context-val'))
        }
        return {
            'context': context,
            'hostname': hostname,
            'power_state': state,
            'power_type': power_type,
            'system_id': system_id,
        }

    def make_nodes(self, count=3):
        nodes = [self.make_node() for _ in xrange(count)]
        # Sanity check that these nodes are something that can emerge
        # from a call to ListNodePowerParameters.
        region.ListNodePowerParameters.makeResponse({"nodes": nodes}, None)
        return nodes

    def pick_alternate_state(self, state):
        return random.choice([
            value for value in ['on', 'off', 'unknown', 'error']
            if value != state])

    @inlineCallbacks
    def test_query_all_nodes_calls_get_power_state(self):
        nodes = self.make_nodes()
        # Report back that all nodes' power states are as recorded.
        power_states = [node['power_state'] for node in nodes]
        get_power_state = self.patch(power, 'get_power_state')
        get_power_state.side_effect = power_states

        yield power.query_all_nodes(nodes)
        self.assertThat(get_power_state, MockCallsMatch(*(
            call(
                node['system_id'], node['hostname'],
                node['power_type'], node['context'],
                clock=reactor)
            for node in nodes
        )))

    @inlineCallbacks
    def test_query_all_nodes_swallows_PowerActionFail(self):
        node1, node2 = self.make_nodes(2)
        new_state_2 = self.pick_alternate_state(node2['power_state'])
        get_power_state = self.patch(power, 'get_power_state')
        error_msg = factory.make_name("error")
        get_power_state.side_effect = [
            PowerActionFail(error_msg), new_state_2]

        with FakeLogger("maas.power", level=logging.DEBUG) as maaslog:
            yield power.query_all_nodes([node1, node2])

        self.assertDocTestMatches(
            """\
            hostname-...: Failed to query power state: %s.
            hostname-...: Power state has changed from ... to ...
            """ % error_msg,
            maaslog.output)

    @inlineCallbacks
    def test_query_all_nodes_swallows_NoSuchNode(self):
        node1, node2 = self.make_nodes(2)
        new_state_2 = self.pick_alternate_state(node2['power_state'])
        get_power_state = self.patch(power, 'get_power_state')
        get_power_state.side_effect = [
            exceptions.NoSuchNode(), new_state_2]

        with FakeLogger("maas.power", level=logging.DEBUG) as maaslog:
            yield power.query_all_nodes([node1, node2])

        self.assertDocTestMatches(
            """\
            hostname-...: Could not update power status; no such node.
            hostname-...: Power state has changed from ... to ...
            """,
            maaslog.output)


class TestMaybeChangePowerState(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def patch_methods_using_rpc(self):
        self.patch_autospec(power, 'power_change_starting')
        power.power_change_starting.side_effect = always_succeed_with(None)

        def change_power_state(system_id, *args, **kwargs):
            del power.power_action_registry[system_id]

        self.patch_autospec(power, 'change_power_state')
        power.change_power_state.side_effect = change_power_state

    def test_always_returns_deferred(self):
        clock = Clock()
        d = power.maybe_change_power_state(
            sentinel.system_id, sentinel.hostname, sentinel.power_type,
            random.choice(("on", "off")), sentinel.context, clock=clock)
        self.assertThat(d, IsInstance(Deferred))

    @inlineCallbacks
    def test_adds_action_to_registry(self):
        self.patch_methods_using_rpc()

        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = random.choice(['on', 'off'])
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }

        yield power.maybe_change_power_state(
            system_id, hostname, power_type, power_change, context)
        self.assertEqual(
            {system_id: power_change},
            power.power_action_registry)
        reactor.runUntilCurrent()  # Run all delayed calls.
        self.assertEqual({}, power.power_action_registry)

    @inlineCallbacks
    def test_errors_when_change_already_registered(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = random.choice(['on', 'off'])
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }

        power.power_action_registry[system_id] = power_change
        with ExpectedException(exceptions.PowerActionAlreadyInProgress):
            yield power.maybe_change_power_state(
                system_id, hostname, power_type, power_change, context)

    @inlineCallbacks
    def test_calls_change_power_state_later(self):
        self.patch_methods_using_rpc()

        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = random.choice(['on', 'off'])
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }

        yield power.maybe_change_power_state(
            system_id, hostname, power_type, power_change, context)
        reactor.runUntilCurrent()  # Run all delayed calls.
        self.assertThat(
            power.change_power_state,
            MockCalledOnceWith(
                system_id, hostname, power_type, power_change, context,
                clock=power.reactor))
