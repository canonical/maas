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

from itertools import izip
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
    Mock,
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
    MockClusterToRegionRPCFixture,
    MockLiveClusterToRegionRPCFixture,
    )
from testtools import ExpectedException
from testtools.deferredruntest import extract_result
from twisted.internet import reactor
from twisted.internet.defer import (
    fail,
    inlineCallbacks,
    maybeDeferred,
    returnValue,
    )
from twisted.internet.task import Clock


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

    def test_power_query_failure_marks_node_broken(self):
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
            protocol.MarkNodeFailed,
            MockCalledOnceWith(
                ANY,
                system_id=system_id,
                error_description=message)
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


class TestChangePowerChange(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def patch_power_action(self, return_value=None, side_effect=None):
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
        power_action = self.patch(power, 'PowerAction')
        power_action.return_value = power_action_obj
        return power_action, power_action_obj_execute

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
        # Patch the power action utility so that it says the node is
        # in the required power state.
        power_action, execute = self.patch_power_action(
            return_value=power_change)
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
        self.patch(power, 'pause')
        power_action, execute = self.patch_power_action(
            return_value=random.choice(['on', 'off']))
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
        # Simulate a failure to power up the node, then a success.
        power_action, execute = self.patch_power_action(
            side_effect=[None, 'off', None, 'on'])
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
        # Simulate a persistent failure.
        power_action, execute = self.patch_power_action(return_value='off')
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
        # Simulate an exception.
        exception_message = factory.make_name('exception')
        power_action, execute = self.patch_power_action(
            side_effect=PowerActionFail(exception_message))
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
        # Simulate two failures to power up the node, then a success.
        power_action, execute = self.patch_power_action(
            side_effect=[None, 'off', None, 'off', None, 'on'])
        # Patch calls to pause() to `execute` so that we record both in the
        # same place, and can thus see ordering.
        self.patch(power, 'pause', execute)

        yield self.patch_rpc_methods()

        yield power.change_power_state(
            system_id, hostname, power_type, power_change, context)

        self.assertThat(execute, MockCallsMatch(
            call(power_change=power_change, **context),
            call(3, reactor),  # pause(3, reactor)
            call(power_change='query', **context),
            call(power_change=power_change, **context),
            call(5, reactor),  # pause(5, reactor)
            call(power_change='query', **context),
        ))


class TestPowerQuery(MAASTestCase):

    def setUp(self):
        super(TestPowerQuery, self).setUp()
        self.patch(
            provisioningserver.rpc.power, 'deferToThread', maybeDeferred)

    def patch_power_action(self, return_value=None, side_effect=None):
        """Patch the PowerAction object.

        Patch the PowerAction object so that PowerAction().execute
        is replaced by a Mock object created using the given `return_value`
        and `side_effect`.

        This can be used to simulate various successes or failures patterns
        while performing operations on the node.

        Returns a tuple of mock objects: power.PowerAction and
        power.PowerAction().execute.
        """
        power_action_obj = Mock()
        power_action_obj_execute = Mock(
            return_value=return_value, side_effect=side_effect)
        power_action_obj.execute = power_action_obj_execute
        power_action = self.patch(power, 'PowerAction')
        power_action.return_value = power_action_obj
        return power_action, power_action_obj_execute

    def patch_rpc_methods(self, return_value={}, side_effect=None):
        fixture = self.useFixture(MockClusterToRegionRPCFixture())
        protocol, io = fixture.makeEventLoop(
            region.MarkNodeFailed, region.SendEvent)
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
        power_action, execute = self.patch_power_action(
            return_value=power_state)
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
        # This blocks until the deferred is complete
        io.flush()
        self.assertEqual('unknown', extract_result(d))

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
        power_action, execute = self.patch_power_action(
            side_effect=[PowerActionFail(err_msg), power_state])
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

    def test_get_power_state_marks_the_node_broken_if_failure(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        err_msg = factory.make_name('error')
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'pause')
        # Simulate a persistent failure.
        power_action, execute = self.patch_power_action(
            side_effect=PowerActionFail(err_msg))
        _, markNodeBroken, io = self.patch_rpc_methods()

        d = power.get_power_state(
            system_id, hostname, power_type, context)
        # This blocks until the deferred is complete
        io.flush()
        self.assertEqual('error', extract_result(d))
        # The node has been marked broken.
        self.assertThat(
            markNodeBroken,
            MockCalledOnceWith(
                ANY,
                system_id=system_id,
                error_description="Node could not be queried %s (%s) %s" % (
                    system_id, hostname, err_msg))
        )

    def test_get_power_state_marks_node_broken_if_template_returns_crap(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        template_return_gibberish = factory.make_name('gibberish')
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'pause')
        power_action, execute = self.patch_power_action(
            return_value=template_return_gibberish)
        _, markNodeBroken, io = self.patch_rpc_methods()
        d = power.get_power_state(
            system_id, hostname, power_type, context)
        io.flush()
        self.assertEqual('error', extract_result(d))

        self.assertThat(
            markNodeBroken,
            MockCalledOnceWith(
                ANY,
                system_id=system_id,
                error_description="Node could not be queried %s (%s) %s" % (
                    system_id, hostname, template_return_gibberish))
        )

    def test_get_power_state_pauses_inbetween_retries(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        # Simulate two failures to power up the node, then a success.
        power_action, execute = self.patch_power_action(
            side_effect=[PowerActionFail, PowerActionFail, 'off'])
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
    def test_query_all_nodes_calls_power_state_update(self):
        nodes = self.make_nodes()
        # Report back that all nodes' power states have changed from recorded.
        power_states = [
            self.pick_alternate_state(node['power_state'])
            for node in nodes
        ]
        get_power_state = self.patch(power, 'get_power_state')
        get_power_state.side_effect = power_states
        # Capture calls to power_state_update.
        power_state_update = self.patch(power, 'power_state_update')

        yield power.query_all_nodes(nodes)

        self.assertThat(power_state_update, MockCallsMatch(*(
            call(node['system_id'], state)
            for node, state in izip(nodes, power_states)
        )))

    @inlineCallbacks
    def test_query_all_nodes_suppresses_NoSuchNode_when_rpting_status(self):
        nodes = self.make_nodes(1)
        # Report back that all nodes' power states have changed from recorded.
        power_states = [
            self.pick_alternate_state(node['power_state'])
            for node in nodes
        ]
        get_power_state = self.patch(power, 'get_power_state')
        get_power_state.side_effect = power_states
        # Capture calls to power_state_update, and return with errors.
        power_state_update = self.patch(power, 'power_state_update')
        power_state_update.side_effect = lambda system_id, state: fail(
            exceptions.NoSuchNode().from_system_id(system_id))

        with FakeLogger("maas.power", level=logging.DEBUG) as maaslog:
            yield power.query_all_nodes(nodes)

        self.assertThat(power_state_update, MockCallsMatch(*(
            call(node['system_id'], state)
            for node, state in izip(nodes, power_states)
        )))
        self.assertDocTestMatches(
            """\
            hostname-...: Power state has changed from ... to ...
            hostname-...: Could not update power status; no such node.
            """,
            maaslog.output)
