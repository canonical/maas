# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
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
    MockCalledWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from maastesting.twisted import (
    always_succeed_with,
    TwistedLoggerFixture,
)
from mock import (
    ANY,
    call,
    DEFAULT,
    Mock,
    sentinel,
)
import provisioningserver
from provisioningserver.drivers.power import PowerDriverRegistry
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
from testtools.deferredruntest import (
    assert_fails_with,
    extract_result,
)
from testtools.matchers import (
    Equals,
    IsInstance,
    Not,
)
from twisted.internet import reactor
from twisted.internet.defer import (
    Deferred,
    fail,
    inlineCallbacks,
    maybeDeferred,
    returnValue,
    succeed,
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
        d = power.power_state_update(system_id, state)
        # This blocks until the deferred is complete
        io.flush()
        self.expectThat(extract_result(d), Equals({}))
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
        self.patch(
            power, 'is_power_driver_available', Mock(return_value=False))
        self.patch(power, 'pause')
        power.power_action_registry[system_id] = power_change, sentinel.d
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
        self.patch(
            power, 'is_power_driver_available', Mock(return_value=False))
        power.power_action_registry[system_id] = power_change, sentinel.d
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
        self.patch(
            power, 'is_power_driver_available', Mock(return_value=False))
        self.patch(power, 'pause')
        power.power_action_registry[system_id] = power_change, sentinel.d
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
    def test_change_power_state_doesnt_retry_if_query_returns_unknown(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = random.choice(['on', 'off'])
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(
            power, 'is_power_driver_available', Mock(return_value=False))
        self.patch(power, 'pause')
        power.power_action_registry[system_id] = power_change, sentinel.d
        # Patch the power action utility so that it says the node is
        # in the required power state.
        power_action, execute = patch_power_action(
            self, return_value="unknown")
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
    def test_change_power_state_marks_the_node_broken_if_failure(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = 'on'
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(
            power, 'is_power_driver_available', Mock(return_value=False))
        self.patch(power, 'pause')
        power.power_action_registry[system_id] = power_change, sentinel.d
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
        self.patch(
            power, 'is_power_driver_available', Mock(return_value=False))
        self.patch(power, 'pause')
        power.power_action_registry[system_id] = power_change, sentinel.d
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
        self.patch(
            power, 'is_power_driver_available', Mock(return_value=False))
        power.power_action_registry[system_id] = power_change, sentinel.d
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
            call(2, reactor),  # pause(1, reactor)
            call(power_change='query', **context),
        ))

    @inlineCallbacks
    def test___handles_power_driver_power_types(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = random.choice(['on', 'off'])
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'is_power_driver_available', Mock(return_value=True))
        perform_power_driver_change = self.patch(
            power, 'perform_power_driver_change')
        self.patch(power, 'pause')
        perform_power_driver_query = self.patch(
            power, 'perform_power_driver_query',
            Mock(return_value=power_change))
        power_change_success = self.patch(power, 'power_change_success')
        yield self.patch_rpc_methods()

        yield power.change_power_state(
            system_id, hostname, power_type, power_change, context)

        self.expectThat(
            perform_power_driver_change, MockCalledOnceWith(
                system_id, hostname, power_type, power_change, context))
        self.expectThat(
            perform_power_driver_query, MockCalledOnceWith(
                system_id, hostname, power_type, context))
        self.expectThat(
            power_change_success, MockCalledOnceWith(
                system_id, hostname, power_change))

    @inlineCallbacks
    def test__calls_power_driver_on_for_power_driver(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = 'on'
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'is_power_driver_available', Mock(return_value=True))
        get_item = self.patch(PowerDriverRegistry, 'get_item')
        get_item.return_value = Mock(return_value='on')
        self.patch(power, 'pause')
        perform_power_driver_query = self.patch(
            power, 'perform_power_driver_query',
            Mock(return_value=power_change))
        power_change_success = self.patch(power, 'power_change_success')
        yield self.patch_rpc_methods()

        result = yield power.change_power_state(
            system_id, hostname, power_type, power_change, context)

        self.expectThat(get_item, MockCalledOnceWith(power_type))
        self.expectThat(
            perform_power_driver_query, MockCalledOnceWith(
                system_id, hostname, power_type, context))
        self.expectThat(
            power_change_success, MockCalledOnceWith(
                system_id, hostname, power_change))
        self.expectThat(result, Equals('on'))

    @inlineCallbacks
    def test__calls_power_driver_off_for_power_driver(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = 'off'
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'is_power_driver_available', Mock(return_value=True))
        get_item = self.patch(PowerDriverRegistry, 'get_item')
        get_item.return_value = Mock(return_value='off')
        self.patch(power, 'pause')
        perform_power_driver_query = self.patch(
            power, 'perform_power_driver_query',
            Mock(return_value=power_change))
        power_change_success = self.patch(power, 'power_change_success')
        yield self.patch_rpc_methods()

        result = yield power.change_power_state(
            system_id, hostname, power_type, power_change, context)

        self.expectThat(get_item, MockCalledOnceWith(power_type))
        self.expectThat(
            perform_power_driver_query, MockCalledOnceWith(
                system_id, hostname, power_type, context))
        self.expectThat(
            power_change_success, MockCalledOnceWith(
                system_id, hostname, power_change))
        self.expectThat(result, Equals('off'))

    @inlineCallbacks
    def test__marks_the_node_broken_if_exception_for_power_driver(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = 'on'
        context = {
            factory.make_name('context-key'): factory.make_name('context-val'),
            'system_id': system_id
        }
        self.patch(power, 'is_power_driver_available', Mock(return_value=True))
        exception_message = factory.make_name('exception')
        get_item = self.patch(PowerDriverRegistry, 'get_item')
        get_item.side_effect = PowerActionFail(exception_message)
        power_change_failure = self.patch(power, 'power_change_failure')

        markNodeBroken = yield self.patch_rpc_methods()

        with ExpectedException(PowerActionFail):
            yield power.change_power_state(
                system_id, hostname, power_type, power_change, context)

        error_message = "Node could not be powered on: %s" % exception_message
        self.expectThat(
            markNodeBroken, MockCalledOnceWith(
                ANY, system_id=system_id, error_description=error_message))
        self.expectThat(
            power_change_failure, MockCalledOnceWith(
                system_id, hostname, power_change, error_message))


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
        self.patch(
            power, 'is_power_driver_available', Mock(return_value=False))
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
        self.patch(
            power, 'is_power_driver_available', Mock(return_value=False))
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
        self.patch(
            power, 'is_power_driver_available', Mock(return_value=False))
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
        self.patch(
            power, 'is_power_driver_available', Mock(return_value=False))
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
        self.patch(
            power, 'is_power_driver_available', Mock(return_value=False))
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

    def test_get_power_state_changes_power_state_if_unknown(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_state = "unknown"
        power_type = random.choice(power.QUERY_POWER_TYPES)
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(
            power, 'is_power_driver_available', Mock(return_value=False))
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
        self.patch(
            power, 'is_power_driver_available', Mock(return_value=False))
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

    def make_node(self, power_type=None):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        if power_type is None:
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
        get_power_state.side_effect = [
            succeed(power_state)
            for power_state in power_states
            ]

        yield power.query_all_nodes(nodes)
        self.assertThat(get_power_state, MockCallsMatch(*(
            call(
                node['system_id'], node['hostname'],
                node['power_type'], node['context'],
                clock=reactor)
            for node in nodes
        )))

    @inlineCallbacks
    def test_query_all_nodes_logs_skip_if_node_in_action_registry(self):
        node = self.make_node()
        power.power_action_registry[node['system_id']] = sentinel.action
        with FakeLogger("maas.power", level=logging.DEBUG) as maaslog:
            yield power.query_all_nodes([node])
        self.assertDocTestMatches(
            "hostname-...: Skipping query power status, "
            "power action already in progress.",
            maaslog.output)

    @inlineCallbacks
    def test_query_all_nodes_skips_nodes_in_action_registry(self):
        nodes = self.make_nodes()

        # First node is in the registry.
        power.power_action_registry[nodes[0]['system_id']] = sentinel.action

        # Report back power state of nodes' not in registry.
        power_states = [node['power_state'] for node in nodes[1:]]
        get_power_state = self.patch(power, 'get_power_state')
        get_power_state.side_effect = [
            succeed(power_state)
            for power_state in power_states
            ]

        yield power.query_all_nodes(nodes)
        self.assertThat(get_power_state, MockCallsMatch(*(
            call(
                node['system_id'], node['hostname'],
                node['power_type'], node['context'],
                clock=reactor)
            for node in nodes[1:]
        )))
        self.assertThat(
            get_power_state, Not(MockCalledWith(
                nodes[0]['system_id'], nodes[0]['hostname'],
                nodes[0]['power_type'], nodes[0]['context'],
                clock=reactor)))

    @inlineCallbacks
    def test_query_all_nodes_only_queries_queryable_power_types(self):
        nodes = self.make_nodes()
        # nodes are all queryable, so add one that isn't:
        nodes.append(self.make_node(power_type='ether_wake'))

        # Report back that all nodes' power states are as recorded.
        power_states = [node['power_state'] for node in nodes]
        get_power_state = self.patch(power, 'get_power_state')
        get_power_state.side_effect = [
            succeed(power_state)
            for power_state in power_states
            ]

        yield power.query_all_nodes(nodes)
        self.assertThat(get_power_state, MockCallsMatch(*(
            call(
                node['system_id'], node['hostname'],
                node['power_type'], node['context'],
                clock=reactor)
            for node in nodes
            if node['power_type'] in power.QUERY_POWER_TYPES
        )))

    @inlineCallbacks
    def test_query_all_nodes_swallows_PowerActionFail(self):
        node1, node2 = self.make_nodes(2)
        new_state_2 = self.pick_alternate_state(node2['power_state'])
        get_power_state = self.patch(power, 'get_power_state')
        error_msg = factory.make_name("error")
        get_power_state.side_effect = [
            fail(PowerActionFail(error_msg)), succeed(new_state_2)]

        with FakeLogger("maas.power", level=logging.DEBUG) as maaslog:
            yield power.query_all_nodes([node1, node2])

        self.assertDocTestMatches(
            """\
            hostname-...: Could not query power state: %s.
            hostname-...: Power state has changed from ... to ...
            """ % error_msg,
            maaslog.output)

    @inlineCallbacks
    def test_query_all_nodes_swallows_NoSuchNode(self):
        node1, node2 = self.make_nodes(2)
        new_state_2 = self.pick_alternate_state(node2['power_state'])
        get_power_state = self.patch(power, 'get_power_state')
        get_power_state.side_effect = [
            fail(exceptions.NoSuchNode()), succeed(new_state_2)]

        with FakeLogger("maas.power", level=logging.DEBUG) as maaslog:
            yield power.query_all_nodes([node1, node2])

        self.assertDocTestMatches(
            """\
            hostname-...: Could not update power state: no such node.
            hostname-...: Power state has changed from ... to ...
            """,
            maaslog.output)

    @inlineCallbacks
    def test_query_all_nodes_swallows_Exception(self):
        node1, node2 = self.make_nodes(2)
        error_message = factory.make_name("error")
        error_type = factory.make_exception_type()
        new_state_2 = self.pick_alternate_state(node2['power_state'])
        get_power_state = self.patch(power, 'get_power_state')
        get_power_state.side_effect = [
            fail(error_type(error_message)),
            succeed(new_state_2),
        ]

        maaslog = FakeLogger("maas.power", level=logging.DEBUG)
        twistlog = TwistedLoggerFixture()

        with maaslog, twistlog:
            yield power.query_all_nodes([node1, node2])

        self.assertDocTestMatches(
            """\
            hostname-...: Failed to refresh power state: %s
            hostname-...: Power state has changed from ... to ...
            """ % error_message,
            maaslog.output)
        self.assertDocTestMatches(
            """\
            Failed to refresh power state.
            Traceback (most recent call last):
            Failure: maastesting.factory.TestException#...: %s
            """ % error_message,
            twistlog.output)

    @inlineCallbacks
    def test_query_all_nodes_returns_deferredlist_of_number_of_nodes(self):
        node1, node2 = self.make_nodes(2)
        get_power_state = self.patch(power, 'get_power_state')
        get_power_state.side_effect = [
            succeed(node1['power_state']), succeed(node2['power_state'])]

        results = yield power.query_all_nodes([node1, node2])
        self.assertEqual(
            [(True, node1['power_state']), (True, node2['power_state'])],
            results)


class TestMaybeChangePowerState(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def setUp(self):
        super(TestMaybeChangePowerState, self).setUp()
        self.patch(power, 'power_action_registry', {})

    def patch_methods_using_rpc(self):
        self.patch_autospec(power, 'power_change_starting')
        power.power_change_starting.side_effect = always_succeed_with(None)

        self.patch_autospec(power, 'change_power_state')
        power.change_power_state.side_effect = always_succeed_with(None)

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
            {system_id: (power_change, ANY)},
            power.power_action_registry)
        reactor.runUntilCurrent()  # Run all delayed calls.
        self.assertEqual({}, power.power_action_registry)

    @inlineCallbacks
    def test_errors_when_change_conflicts_with_in_progress_change(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_changes = ['on', 'off']
        random.shuffle(power_changes)
        current_power_change, power_change = power_changes
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        power.power_action_registry[system_id] = (
            current_power_change, sentinel.d)
        with ExpectedException(exceptions.PowerActionAlreadyInProgress):
            yield power.maybe_change_power_state(
                system_id, hostname, power_type, power_change, context)

    @inlineCallbacks
    def test_does_nothing_when_change_matches_in_progress_change(self):
        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        current_power_change = power_change = random.choice(['on', 'off'])
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        power.power_action_registry[system_id] = (
            current_power_change, sentinel.d)
        yield power.maybe_change_power_state(
            system_id, hostname, power_type, power_change, context)
        self.assertThat(power.power_action_registry, Equals(
            {system_id: (power_change, sentinel.d)}))

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
                power.reactor))

    @inlineCallbacks
    def test_clears_lock_if_change_power_state_success(self):
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
        self.assertNotIn(system_id, power.power_action_registry)

    @inlineCallbacks
    def test_clears_lock_if_change_power_state_fails(self):

        class TestException(Exception):
            pass

        self.patch_autospec(power, 'power_change_starting')
        power.power_change_starting.side_effect = TestException('boom')

        system_id = factory.make_name('system_id')
        hostname = factory.make_hostname()
        power_type = sentinel.power_type
        power_change = random.choice(['on', 'off'])
        context = sentinel.context

        logger = self.useFixture(TwistedLoggerFixture())

        yield power.maybe_change_power_state(
            system_id, hostname, power_type, power_change, context)
        reactor.runUntilCurrent()  # Run all delayed calls.
        self.assertNotIn(system_id, power.power_action_registry)
        self.assertDocTestMatches(
            """\
            %s: Power could not be turned %s.
            Traceback (most recent call last):
            ...
            %s.TestException: boom
            """ % (hostname, power_change, __name__),
            logger.dump())

    @inlineCallbacks
    def test_clears_lock_if_change_power_state_is_cancelled(self):
        # Patch in an unfired Deferred here. This will pause the call so that
        # we can grab the delayed call from the registry in time to cancel it.
        self.patch_autospec(power, 'change_power_state')
        power.change_power_state.return_value = Deferred()
        mock_power_change_failure = self.patch_autospec(
            power, 'power_change_failure')

        system_id = factory.make_name('system_id')
        hostname = factory.make_hostname()
        power_type = sentinel.power_type
        power_change = random.choice(['on', 'off'])
        context = sentinel.context

        logger = self.useFixture(TwistedLoggerFixture())

        yield power.maybe_change_power_state(
            system_id, hostname, power_type, power_change, context)

        # Get the Deferred from the registry and cancel it.
        _, d = power.power_action_registry[system_id]
        d.cancel()
        yield d

        self.assertNotIn(system_id, power.power_action_registry)
        self.assertDocTestMatches(
            """\
            %s: Power could not be turned %s; timed out.
            """ % (hostname, power_change),
            logger.dump())
        self.assertThat(
            mock_power_change_failure,
            MockCalledOnceWith(
                system_id, hostname, power_change, "Timed out")
        )

    @inlineCallbacks
    def test__calls_change_power_state_with_timeout(self):
        self.patch_methods_using_rpc()
        defer_with_timeout = self.patch(power, 'deferWithTimeout')

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
            defer_with_timeout, MockCalledOnceWith(
                power.CHANGE_POWER_STATE_TIMEOUT,
                power.change_power_state, system_id, hostname,
                power_type, power_change, context, power.reactor))
