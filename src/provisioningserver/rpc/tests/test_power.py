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


import random

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
    )
from maastesting.testcase import MAASTestCase
from mock import (
    ANY,
    call,
    Mock,
    )
import provisioningserver
from provisioningserver.events import EVENT_TYPES
from provisioningserver.power.poweraction import PowerActionFail
from provisioningserver.rpc import (
    power,
    region,
    )
from provisioningserver.rpc.testing import ClusterToRegionRPCFixture
from testtools.deferredruntest import (
    assert_fails_with,
    AsynchronousDeferredRunTest,
    )
from twisted.internet.defer import maybeDeferred
from twisted.internet.task import Clock


class TestPowerHelpers(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def patch_rpc_methods(self):
        fixture = self.useFixture(ClusterToRegionRPCFixture())
        protocol, io = fixture.makeEventLoop(
            region.MarkNodeBroken, region.UpdateNodePowerState,
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
        return d

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
        return d

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
        return d

    def test_power_query_failure_emits_event(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        message = factory.make_name('message')
        protocol, io = self.patch_rpc_methods()
        d = power.power_query_failure(
            system_id, hostname, message)
        # This blocks until the deferred is complete
        io.flush()
        self.assertTrue(d.called)
        self.assertThat(
            protocol.SendEvent,
            MockCalledOnceWith(
                ANY,
                type_name=EVENT_TYPES.NODE_POWER_QUERY_FAILED,
                system_id=system_id,
                description=message)
        )
        return d

    def test_power_query_failure_marks_node_broken(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        message = factory.make_name('message')
        protocol, io = self.patch_rpc_methods()
        d = power.power_query_failure(
            system_id, hostname, message)
        # This blocks until the deferred is complete
        io.flush()
        self.assertTrue(d.called)
        self.assertThat(
            protocol.MarkNodeBroken,
            MockCalledOnceWith(
                ANY,
                system_id=system_id,
                error_description=message)
        )
        return d

    def test_power_state_update_calls_UpdateNodePowerState(self):
        system_id = factory.make_name('system_id')
        state = random.choice(['on', 'off'])
        protocol, io = self.patch_rpc_methods()
        d = power.power_state_update(
            system_id, state)
        # This blocks until the deferred is complete
        io.flush()
        self.assertTrue(d.called)
        self.assertThat(
            protocol.UpdateNodePowerState,
            MockCalledOnceWith(
                ANY,
                system_id=system_id,
                power_state=state)
        )
        return d


class TestChangePowerChange(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def setUp(self):
        super(TestChangePowerChange, self).setUp()
        self.patch(
            provisioningserver.rpc.power, 'deferToThread', maybeDeferred)

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

    def patch_rpc_methods(self, return_value={}, side_effect=None):
        fixture = self.useFixture(ClusterToRegionRPCFixture())
        protocol, io = fixture.makeEventLoop(
            region.MarkNodeBroken, region.UpdateNodePowerState,
            region.SendEvent)
        protocol.MarkNodeBroken.return_value = return_value
        protocol.MarkNodeBroken.side_effect = side_effect
        return protocol.MarkNodeBroken, io

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
        markNodeBroken, io = self.patch_rpc_methods()

        d = power.change_power_state(
            system_id, hostname, power_type, power_change, context)
        io.flush()
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
        return d

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
        markNodeBroken, io = self.patch_rpc_methods()

        d = power.change_power_state(
            system_id, hostname, power_type, power_change, context)
        io.flush()
        self.assertThat(
            execute,
            MockCallsMatch(
                # Only one call to change the power state.
                call(power_change=power_change, **context),
            ),
        )
        # The node hasn't been marked broken.
        self.assertThat(markNodeBroken, MockNotCalled())
        return d

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
        markNodeBroken, io = self.patch_rpc_methods()

        d = power.change_power_state(
            system_id, hostname, power_type, power_change, context)
        io.flush()
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
        return d

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
        markNodeBroken, io = self.patch_rpc_methods()

        d = power.change_power_state(
            system_id, hostname, power_type, power_change, context)
        io.flush()

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
        return d

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
        markNodeBroken, io = self.patch_rpc_methods()

        d = power.change_power_state(
            system_id, hostname, power_type, power_change, context)
        io.flush()
        assert_fails_with(d, PowerActionFail)
        error_message = "Node could not be powered on: %s" % exception_message

        def check(failure):
            self.assertThat(
                markNodeBroken,
                MockCalledOnceWith(
                    ANY, system_id=system_id, error_description=error_message))

        return d.addCallback(check)

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
        self.patch(power, "deferToThread", maybeDeferred)
        markNodeBroken, io = self.patch_rpc_methods()
        clock = Clock()

        calls_and_pause = [
            ([
                call(power_change=power_change, **context),
            ], 3),
            ([
                call(power_change='query', **context),
                call(power_change=power_change, **context),
            ], 5),
            ([
                call(power_change='query', **context),
                call(power_change=power_change, **context),
            ], 10),
            ([
                call(power_change='query', **context),
            ], 0),
        ]
        calls = []
        d = power.change_power_state(
            system_id, hostname, power_type, power_change, context,
            clock=clock)
        for newcalls, waiting_time in calls_and_pause:
            calls.extend(newcalls)
            io.flush()
            self.assertThat(execute, MockCallsMatch(*calls))
            clock.advance(waiting_time)
        return d


class TestPowerQuery(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

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
        fixture = self.useFixture(ClusterToRegionRPCFixture())
        protocol, io = fixture.makeEventLoop(
            region.MarkNodeBroken, region.SendEvent)
        protocol.MarkNodeBroken.return_value = return_value
        protocol.MarkNodeBroken.side_effect = side_effect
        return protocol.SendEvent, protocol.MarkNodeBroken, io

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
        self.assertTrue(d.called)
        self.assertThat(
            execute,
            MockCallsMatch(
                # One call to change the power state.
                call(power_change='query', **context),
            ),
        )
        self.assertEqual(power_state, d.result)
        return d

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
        self.assertTrue(d.called)
        self.assertEqual('unknown', d.result)
        return d

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
        self.assertTrue(d.called)
        self.assertThat(
            execute,
            MockCallsMatch(
                call(power_change='query', **context),
                call(power_change='query', **context),
            )
        )
        # The node hasn't been marked broken.
        self.assertThat(markNodeBroken, MockNotCalled())
        self.assertEqual(power_state, d.result)
        return d

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
        self.assertTrue(d.called)
        # The node has been marked broken.
        self.assertThat(
            markNodeBroken,
            MockCalledOnceWith(
                ANY,
                system_id=system_id,
                error_description="Node could not be queried %s (%s) %s" % (
                    system_id, hostname, err_msg))
        )
        self.assertEqual('error', d.result)
        return d

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
        return d

    def make_nodes(self):
        nodes = []
        for node in nodes:
            system_id = factory.make_name('system_id')
            hostname = factory.make_name('hostname')
            power_type = random.choice(power.QUERY_POWER_TYPES)
            state = random.choice(['on', 'off', 'unknown', 'error'])
            context = {
                factory.make_name(
                    'context-key'): factory.make_name('context-val')
            }
            nodes.append({
                'system_id': system_id,
                'hostname': hostname,
                'power_type': power_type,
                'context': context,
                'state': state,
                })
        return nodes

    def pick_alternate_state(self, state):
        return random.choice([
            value for value in ['on', 'off', 'unknown', 'error']
            if value != state])

    def test_query_all_nodes_calls_get_power_state(self):
        nodes = self.make_nodes()
        states = [node['state'] for node in nodes]
        get_state = self.patch(power, 'get_power_state')
        get_state.side_effect = states

        calls = []
        for node in nodes:
            calls.append(
                call(
                    node['system_id'], node['hostname'],
                    node['power_type'], node['context']))

        self.assertThat(get_state, MockCallsMatch(*calls))

    def test_query_all_nodes_calls_power_state_update(self):
        nodes = self.make_nodes()
        states = [self.pick_alternate_state(node['state']) for node in nodes]
        get_state = self.patch(power, 'get_power_state')
        get_state.side_effect = states
        update_state = self.patch(power, 'power_state_update')

        calls = []
        for i in range(len(nodes)):
            node = nodes[i]
            new_state = states[i]
            calls.append(
                call(
                    node['system_id'], new_state))

        self.assertThat(update_state, MockCallsMatch(*calls))
