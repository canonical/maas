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
from provisioningserver.rpc import (
    power,
    region,
    )
from provisioningserver.rpc.testing import RegionRPCFixture
from testtools.deferredruntest import (
    assert_fails_with,
    AsynchronousDeferredRunTest,
    )
from twisted.internet.defer import (
    inlineCallbacks,
    maybeDeferred,
    )
from twisted.internet.task import Clock


class TestPowerHelpers(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

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

    def patch_MarkNodeBroken(self, return_value={}, side_effect=None):
        fixture = self.useFixture(RegionRPCFixture())
        protocol, io = fixture.makeEventLoop(region.MarkNodeBroken)
        protocol.MarkNodeBroken.return_value = return_value
        protocol.MarkNodeBroken.side_effect = side_effect
        return protocol.MarkNodeBroken, io

    @inlineCallbacks
    def test_change_power_state_changes_power_state(self):
        system_id = factory.make_name('system_id')
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
        markNodeBroken, io = self.patch_MarkNodeBroken()

        yield power.change_power_state(
            system_id, power_type, power_change, context)
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

    @inlineCallbacks
    def test_change_power_state_doesnt_retry_for_certain_power_types(self):
        system_id = factory.make_name('system_id')
        # Use a power type that is not among power.QUERY_POWER_TYPES.
        power_type = factory.make_name('power_type')
        power_change = random.choice(['on', 'off'])
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'pause')
        power_action, execute = self.patch_power_action(
            return_value=random.choice(['on', 'off']))
        markNodeBroken, io = self.patch_MarkNodeBroken()

        yield power.change_power_state(
            system_id, power_type, power_change, context)
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

    @inlineCallbacks
    def test_change_power_state_retries_if_power_state_doesnt_change(self):
        system_id = factory.make_name('system_id')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = 'on'
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'pause')
        # Simulate a failure to power up the node, then a success.
        power_action, execute = self.patch_power_action(
            side_effect=[None, 'off', None, 'on'])
        markNodeBroken, io = self.patch_MarkNodeBroken()

        yield power.change_power_state(
            system_id, power_type, power_change, context)
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

    @inlineCallbacks
    def test_change_power_state_marks_the_node_broken_if_failure(self):
        system_id = factory.make_name('system_id')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = 'on'
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'pause')
        # Simulate a persistent failure.
        power_action, execute = self.patch_power_action(return_value='off')
        markNodeBroken, io = self.patch_MarkNodeBroken()

        yield power.change_power_state(
            system_id, power_type, power_change, context)
        io.flush()

        # The node has been marked broken.
        self.assertThat(
            markNodeBroken,
            MockCalledOnceWith(
                ANY,
                system_id=system_id,
                error_description="Node could not be powered on")
        )

    def test_change_power_state_marks_the_node_broken_if_exception(self):
        system_id = factory.make_name('system_id')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = 'on'
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        self.patch(power, 'pause')
        # Simulate an exception.
        exception_message = factory.make_name('exception')
        power_action, execute = self.patch_power_action(
            side_effect=Exception(exception_message))
        markNodeBroken, io = self.patch_MarkNodeBroken()

        d = power.change_power_state(
            system_id, power_type, power_change, context)
        assert_fails_with(d, Exception)
        error_message = "Node could not be powered on: %s" % exception_message

        def check(failure):
            io.flush()
            self.assertThat(
                markNodeBroken,
                MockCalledOnceWith(
                    ANY, system_id=system_id, error_description=error_message))

        return d.addCallback(check)

    def test_change_power_state_pauses_in_between_retries(self):
        system_id = factory.make_name('system_id')
        power_type = random.choice(power.QUERY_POWER_TYPES)
        power_change = 'on'
        context = {
            factory.make_name('context-key'): factory.make_name('context-val')
        }
        # Simulate two failures to power up the node, then a success.
        power_action, execute = self.patch_power_action(
            side_effect=[None, 'off', None, 'off', None, 'on'])
        self.patch(power, "deferToThread", maybeDeferred)
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
        yield power.change_power_state(
            system_id, power_type, power_change, context, clock=clock)
        for newcalls, waiting_time in calls_and_pause:
            calls.extend(newcalls)
            self.assertThat(execute, MockCallsMatch(*calls))
            clock.advance(waiting_time)
