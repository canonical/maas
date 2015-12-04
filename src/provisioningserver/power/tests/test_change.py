# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~provisioningserver.power.change`."""

__all__ = []

import random

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
from provisioningserver import power
from provisioningserver.drivers.power import (
    DEFAULT_WAITING_POLICY,
    get_error_message as get_driver_error_message,
    power_drivers_by_name,
    PowerDriverRegistry,
    PowerError,
)
from provisioningserver.events import EVENT_TYPES
from provisioningserver.power import poweraction
from provisioningserver.rpc import (
    exceptions,
    region,
)
from provisioningserver.rpc.testing import (
    MockClusterToRegionRPCFixture,
    MockLiveClusterToRegionRPCFixture,
)
from provisioningserver.testing.events import EventTypesAllRegistered
from testtools import ExpectedException
from testtools.deferredruntest import extract_result
from testtools.matchers import (
    Equals,
    IsInstance,
)
from twisted.internet import reactor
from twisted.internet.defer import (
    Deferred,
    inlineCallbacks,
    returnValue,
)
from twisted.internet.task import Clock


def patch_PowerAction(test, return_value=DEFAULT, side_effect=None):
    """Patch the PowerAction object.

    Patch the PowerAction object so that PowerAction().execute
    is replaced by a Mock object created using the given `return_value`
    and `side_effect`.

    This can be used to simulate various successes or failures patterns
    while manipulating the power state of a node.

    Returns a tuple of mock objects: power.poweraction.PowerAction and
    power.poweraction.PowerAction().execute.
    """
    power_action_obj = Mock()
    power_action_obj_execute = Mock(
        return_value=return_value, side_effect=side_effect)
    power_action_obj.execute = power_action_obj_execute
    power_action = test.patch(poweraction, 'PowerAction')
    power_action.return_value = power_action_obj
    return power_action, power_action_obj_execute


def do_not_pause(test):
    test.patch_autospec(power.change, "pause", always_succeed_with(None))
    test.patch_autospec(power.query, "pause", always_succeed_with(None))


class TestPowerHelpers(MAASTestCase):

    def setUp(self):
        super(TestPowerHelpers, self).setUp()
        self.useFixture(EventTypesAllRegistered())

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
        d = power.change.power_change_success(
            system_id, hostname, power_change)
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
        d = power.change.power_change_starting(
            system_id, hostname, power_change)
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
        d = power.change.power_change_failure(
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


class TestChangePowerState(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def setUp(self):
        super(TestChangePowerState, self).setUp()
        self.useFixture(EventTypesAllRegistered())
        do_not_pause(self)

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
        self.patch_autospec(power.change, "power_change_starting")
        power.change.power_change_starting.side_effect = ArbitraryException()

        d = power.change.change_power_state(
            sentinel.system_id, sentinel.hostname, sentinel.power_type,
            sentinel.power_change, sentinel.context)
        self.assertRaises(ArbitraryException, extract_result, d)
        self.assertThat(
            power.change.power_change_starting, MockCalledOnceWith(
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
        self.patch(power, 'is_driver_available').return_value = False
        power.power_action_registry[system_id] = power_change, sentinel.d
        # Patch the power action utility so that it says the node is
        # in the required power state.
        power_action, execute = patch_PowerAction(
            self, return_value=power_change)
        markNodeBroken = yield self.patch_rpc_methods()

        yield power.change.change_power_state(
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
        self.patch(power, 'is_driver_available').return_value = False
        power.power_action_registry[system_id] = power_change, sentinel.d
        power_action, execute = patch_PowerAction(
            self, return_value=random.choice(['on', 'off']))
        markNodeBroken = yield self.patch_rpc_methods()

        yield power.change.change_power_state(
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
        self.patch(power, 'is_driver_available').return_value = False
        power.power_action_registry[system_id] = power_change, sentinel.d
        # Simulate a failure to power up the node, then a success.
        power_action, execute = patch_PowerAction(
            self, side_effect=[None, 'off', None, 'on'])
        markNodeBroken = yield self.patch_rpc_methods()

        yield power.change.change_power_state(
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
        self.patch(power, 'is_driver_available').return_value = False
        power.power_action_registry[system_id] = power_change, sentinel.d
        # Patch the power action utility so that it says the node is
        # in the required power state.
        power_action, execute = patch_PowerAction(
            self, return_value="unknown")
        markNodeBroken = yield self.patch_rpc_methods()

        yield power.change.change_power_state(
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
        self.patch(power, 'is_driver_available').return_value = False
        power.power_action_registry[system_id] = power_change, sentinel.d
        # Simulate a persistent failure.
        power_action, execute = patch_PowerAction(
            self, return_value='off')
        markNodeBroken = yield self.patch_rpc_methods()

        yield power.change.change_power_state(
            system_id, hostname, power_type, power_change, context)

        # The node has been marked broken.
        msg = "Timeout after %s tries" % len(DEFAULT_WAITING_POLICY)
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
        self.patch(power, 'is_driver_available').return_value = False
        power.power_action_registry[system_id] = power_change, sentinel.d
        # Simulate an exception.
        exception_message = factory.make_name('exception')
        power_action, execute = patch_PowerAction(
            self, side_effect=poweraction.PowerActionFail(exception_message))
        markNodeBroken = yield self.patch_rpc_methods()

        with ExpectedException(poweraction.PowerActionFail):
            yield power.change.change_power_state(
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
        self.patch(power, 'is_driver_available').return_value = False
        power.power_action_registry[system_id] = power_change, sentinel.d
        # Simulate two failures to power up the node, then a success.
        power_action, execute = patch_PowerAction(
            self, side_effect=[None, 'off', None, 'off', None, 'on'])
        # Patch calls to pause() to `execute` so that we record both in the
        # same place, and can thus see ordering.
        self.patch(power.change, 'pause', execute)
        self.patch(power.query, 'pause', execute)

        yield self.patch_rpc_methods()

        yield power.change.change_power_state(
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
        self.patch(power, 'is_driver_available').return_value = True
        perform_power_driver_change = self.patch_autospec(
            power.change, 'perform_power_driver_change')
        perform_power_driver_query = self.patch_autospec(
            power.query, 'perform_power_driver_query',
            Mock(return_value=power_change))
        power_change_success = self.patch_autospec(
            power.change, 'power_change_success')
        yield self.patch_rpc_methods()

        yield power.change.change_power_state(
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
        self.patch(power, 'is_driver_available').return_value = True
        get_item = self.patch(PowerDriverRegistry, 'get_item')
        get_item.return_value = Mock(return_value='on')
        perform_power_driver_query = self.patch(
            power.query, 'perform_power_driver_query',
            Mock(return_value=power_change))
        self.patch(power.change, 'power_change_success')
        yield self.patch_rpc_methods()

        result = yield power.change.change_power_state(
            system_id, hostname, power_type, power_change, context)

        self.expectThat(get_item, MockCalledOnceWith(power_type))
        self.expectThat(
            perform_power_driver_query, MockCalledOnceWith(
                system_id, hostname, power_type, context))
        self.expectThat(
            power.change.power_change_success, MockCalledOnceWith(
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
        self.patch(power, 'is_driver_available').return_value = True
        get_item = self.patch(PowerDriverRegistry, 'get_item')
        get_item.return_value = Mock(return_value='off')
        perform_power_driver_query = self.patch(
            power.query, 'perform_power_driver_query',
            Mock(return_value=power_change))
        self.patch(power.change, 'power_change_success')
        yield self.patch_rpc_methods()

        result = yield power.change.change_power_state(
            system_id, hostname, power_type, power_change, context)

        self.expectThat(get_item, MockCalledOnceWith(power_type))
        self.expectThat(
            perform_power_driver_query, MockCalledOnceWith(
                system_id, hostname, power_type, context))
        self.expectThat(
            power.change.power_change_success, MockCalledOnceWith(
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
        self.patch(power, 'is_driver_available').return_value = True
        exception = PowerError(factory.make_string())
        get_item = self.patch(PowerDriverRegistry, 'get_item')
        get_item.side_effect = exception
        self.patch(power.change, 'power_change_failure')

        markNodeBroken = yield self.patch_rpc_methods()

        with ExpectedException(PowerError):
            yield power.change.change_power_state(
                system_id, hostname, power_type, power_change, context)

        error_message = "Node could not be powered on: %s" % (
            get_driver_error_message(exception))
        self.expectThat(
            markNodeBroken, MockCalledOnceWith(
                ANY, system_id=system_id, error_description=error_message))
        self.expectThat(
            power.change.power_change_failure, MockCalledOnceWith(
                system_id, hostname, power_change, error_message))


class TestMaybeChangePowerState(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def setUp(self):
        super(TestMaybeChangePowerState, self).setUp()
        self.patch(power, 'power_action_registry', {})
        for power_driver in power_drivers_by_name.values():
            self.patch(
                power_driver, "detect_missing_packages").return_value = []
        self.useFixture(EventTypesAllRegistered())
        do_not_pause(self)

    def patch_methods_using_rpc(self):
        self.patch_autospec(power.change, 'power_change_starting')
        power.change.power_change_starting.side_effect = (
            always_succeed_with(None))

        self.patch_autospec(power.change, 'change_power_state')
        power.change.change_power_state.side_effect = always_succeed_with(None)

    def test_always_returns_deferred(self):
        clock = Clock()
        power_type = random.choice(power.QUERY_POWER_TYPES)
        d = power.change.maybe_change_power_state(
            sentinel.system_id, sentinel.hostname, power_type,
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

        yield power.change.maybe_change_power_state(
            system_id, hostname, power_type, power_change, context)
        self.assertEqual(
            {system_id: (power_change, ANY)},
            power.power_action_registry)
        reactor.runUntilCurrent()  # Run all delayed calls.
        self.assertEqual({}, power.power_action_registry)

    @inlineCallbacks
    def test_checks_missing_packages(self):
        self.patch_methods_using_rpc()

        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = random.choice(['on', 'off'])
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        power_driver = power_drivers_by_name.get(power_type)
        yield power.change.maybe_change_power_state(
            system_id, hostname, power_type, power_change, context)
        reactor.runUntilCurrent()  # Run all delayed calls.
        self.assertThat(
            power_driver.detect_missing_packages, MockCalledOnceWith())

    @inlineCallbacks
    def test_errors_when_missing_packages(self):
        self.patch_methods_using_rpc()

        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = random.choice(['on', 'off'])
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        power_driver = power_drivers_by_name.get(power_type)
        power_driver.detect_missing_packages.return_value = ['gone']
        with ExpectedException(poweraction.PowerActionFail):
            yield power.change.maybe_change_power_state(
                system_id, hostname, power_type, power_change, context)
        self.assertThat(
            power_driver.detect_missing_packages, MockCalledOnceWith())

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
            yield power.change.maybe_change_power_state(
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
        yield power.change.maybe_change_power_state(
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

        yield power.change.maybe_change_power_state(
            system_id, hostname, power_type, power_change, context)
        reactor.runUntilCurrent()  # Run all delayed calls.
        self.assertThat(
            power.change.change_power_state,
            MockCalledOnceWith(
                system_id, hostname, power_type, power_change, context,
                power.change.reactor))

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

        yield power.change.maybe_change_power_state(
            system_id, hostname, power_type, power_change, context)
        reactor.runUntilCurrent()  # Run all delayed calls.
        self.assertNotIn(system_id, power.power_action_registry)

    @inlineCallbacks
    def test_clears_lock_if_change_power_state_fails(self):

        class TestException(Exception):
            pass

        self.patch_autospec(power.change, 'power_change_starting')
        power.change.power_change_starting.side_effect = TestException('boom')

        system_id = factory.make_name('system_id')
        hostname = factory.make_hostname()
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = random.choice(['on', 'off'])
        context = sentinel.context

        logger = self.useFixture(TwistedLoggerFixture())

        yield power.change.maybe_change_power_state(
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
        self.patch_autospec(power.change, 'change_power_state')
        power.change.change_power_state.return_value = Deferred()
        self.patch_autospec(power.change, 'power_change_failure')

        system_id = factory.make_name('system_id')
        hostname = factory.make_hostname()
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = random.choice(['on', 'off'])
        context = sentinel.context

        logger = self.useFixture(TwistedLoggerFixture())

        yield power.change.maybe_change_power_state(
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
            power.change.power_change_failure, MockCalledOnceWith(
                system_id, hostname, power_change, "Timed out"))

    @inlineCallbacks
    def test__calls_change_power_state_with_timeout(self):
        self.patch_methods_using_rpc()
        defer_with_timeout = self.patch(power.change, 'deferWithTimeout')

        system_id = factory.make_name('system_id')
        hostname = factory.make_name('hostname')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = random.choice(['on', 'off'])
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }

        yield power.change.maybe_change_power_state(
            system_id, hostname, power_type, power_change, context)
        reactor.runUntilCurrent()  # Run all delayed calls.
        self.assertThat(
            defer_with_timeout, MockCalledOnceWith(
                power.change.CHANGE_POWER_STATE_TIMEOUT,
                power.change.change_power_state, system_id, hostname,
                power_type, power_change, context, power.change.reactor))
