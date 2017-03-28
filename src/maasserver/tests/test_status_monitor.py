# Copyright 2016-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the status monitor module."""

__all__ = []


from datetime import (
    datetime,
    timedelta,
)
import random
from unittest.mock import call

from maasserver import status_monitor
from maasserver.enum import (
    NODE_STATUS,
    NODE_STATUS_CHOICES,
)
from maasserver.models import Node
from maasserver.models.signals.testing import SignalsDisabled
from maasserver.node_status import (
    NODE_FAILURE_MONITORED_STATUS_TRANSITIONS,
    NODE_TESTING_RESET_READY_TRANSITIONS,
)
from maasserver.status_monitor import (
    fail_testing,
    mark_nodes_failed_after_expiring,
    mark_testing_nodes_failed_after_missing_timeout,
    StatusMonitorService,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maastesting.djangotestcase import CountQueries
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from metadataserver.enum import SCRIPT_STATUS
from nose.tools import nottest
from twisted.internet.defer import maybeDeferred
from twisted.internet.task import Clock

# Nose is over-zealous.
nottest(fail_testing)
nottest(mark_testing_nodes_failed_after_missing_timeout)


class TestMarkNodesFailedAfterExpiring(MAASServerTestCase):

    def test__marks_all_possible_failed_status_as_failed(self):
        self.useFixture(SignalsDisabled("power"))
        current_time = datetime.now()
        self.patch(status_monitor, "now").return_value = current_time
        expired_time = current_time - timedelta(minutes=1)
        nodes = [
            factory.make_Node(status=status, status_expires=expired_time)
            for status in NODE_FAILURE_MONITORED_STATUS_TRANSITIONS.keys()
        ]
        mark_nodes_failed_after_expiring()
        failed_statuses = [
            reload_object(node).status
            for node in nodes
        ]
        self.assertItemsEqual(
            NODE_FAILURE_MONITORED_STATUS_TRANSITIONS.values(),
            failed_statuses)

    def test__marks_all_scripts_as_timedout_on_failure(self):
        self.useFixture(SignalsDisabled("power"))
        current_time = datetime.now()
        self.patch(status_monitor, "now").return_value = current_time
        expired_time = current_time - timedelta(minutes=1)
        node = factory.make_Node(
            status=random.choice([
                NODE_STATUS.COMMISSIONING, NODE_STATUS.TESTING,
                NODE_STATUS.DEPLOYING]),
            status_expires=expired_time, with_empty_script_sets=True)
        script_results = [
            factory.make_ScriptResult(
                script_set=script_set, status=SCRIPT_STATUS.PENDING)
            for script_set in {
                node.current_commissioning_script_set,
                node.current_testing_script_set,
                node.current_installation_script_set,
            }
        ]

        mark_nodes_failed_after_expiring()

        for script_result in script_results:
            self.assertEquals(
                SCRIPT_STATUS.TIMEDOUT, reload_object(script_result).status)

    def test__skips_those_that_have_not_expired(self):
        self.useFixture(SignalsDisabled("power"))
        current_time = datetime.now()
        self.patch(status_monitor, "now").return_value = current_time
        expired_time = current_time + timedelta(minutes=1)
        nodes = [
            factory.make_Node(status=status, status_expires=expired_time)
            for status in NODE_FAILURE_MONITORED_STATUS_TRANSITIONS.keys()
        ]
        mark_nodes_failed_after_expiring()
        failed_statuses = [
            reload_object(node).status
            for node in nodes
        ]
        self.assertItemsEqual(
            NODE_FAILURE_MONITORED_STATUS_TRANSITIONS.keys(), failed_statuses)


class TestMarkTestingNodesFailedAfterMissingTimeout(MAASServerTestCase):

    def setUp(self):
        super().setUp()
        self.useFixture(SignalsDisabled("power"))

    def test_fail(self):
        user = factory.make_admin()
        node = factory.make_Node(
            previous_status=factory.pick_choice(
                NODE_STATUS_CHOICES,
                but_not=NODE_TESTING_RESET_READY_TRANSITIONS),
            status=NODE_STATUS.TESTING, with_empty_script_sets=True,
            owner=user)
        script_results = [
            factory.make_ScriptResult(
                script_set=node.current_testing_script_set,
                status=SCRIPT_STATUS.PENDING)
            for _ in range(3)
        ]
        reason = factory.make_string()
        mock_stop = self.patch(node, 'stop')

        fail_testing(node, reason)

        self.assertThat(mock_stop, MockCalledOnceWith(user, comment=reason))
        self.assertEquals(NODE_STATUS.FAILED_TESTING, node.status)
        self.assertEquals(reason, node.error_description)
        for script_result in script_results:
            self.assertEquals(
                SCRIPT_STATUS.TIMEDOUT, reload_object(script_result).status)

    def test_fail_doesnt_stop_with_ssh_enabled(self):
        user = factory.make_admin()
        node = factory.make_Node(
            previous_status=factory.pick_choice(
                NODE_STATUS_CHOICES,
                but_not=NODE_TESTING_RESET_READY_TRANSITIONS),
            status=NODE_STATUS.TESTING, with_empty_script_sets=True,
            owner=user, enable_ssh=True)
        script_results = [
            factory.make_ScriptResult(
                script_set=node.current_testing_script_set,
                status=SCRIPT_STATUS.PENDING)
            for _ in range(3)
        ]
        reason = factory.make_string()
        mock_stop = self.patch(node, 'stop')

        fail_testing(node, reason)

        self.assertThat(mock_stop, MockNotCalled())
        self.assertEquals(NODE_STATUS.FAILED_TESTING, node.status)
        self.assertEquals(reason, node.error_description)
        for script_result in script_results:
            self.assertEquals(
                SCRIPT_STATUS.TIMEDOUT, reload_object(script_result).status)

    def test_mark_testing_nodes_failed_after_missing_timeout_heartbeat(self):
        user = factory.make_admin()
        node = factory.make_Node(
            previous_status=random.choice(
                list(NODE_TESTING_RESET_READY_TRANSITIONS)),
            status=NODE_STATUS.TESTING, with_empty_script_sets=True,
            owner=user)
        node.current_testing_script_set.last_ping = (
            datetime.now() - timedelta(minutes=11))
        node.current_testing_script_set.save()
        script_results = [
            factory.make_ScriptResult(
                script_set=node.current_testing_script_set,
                status=SCRIPT_STATUS.PENDING)
            for _ in range(3)
        ]
        self.patch(Node, 'stop')

        mark_testing_nodes_failed_after_missing_timeout()
        node = reload_object(node)

        self.assertEquals(NODE_STATUS.FAILED_TESTING, node.status)
        self.assertEquals(
            'Node has missed the last 5 heartbeats', node.error_description)
        for script_result in script_results:
            self.assertEquals(
                SCRIPT_STATUS.TIMEDOUT, reload_object(script_result).status)

    def test_mark_testing_nodes_failed_after_script_overrun(self):
        user = factory.make_admin()
        node = factory.make_Node(
            previous_status=random.choice(
                list(NODE_TESTING_RESET_READY_TRANSITIONS)),
            status=NODE_STATUS.TESTING, with_empty_script_sets=True,
            owner=user)
        now = datetime.now()
        node.current_testing_script_set.last_ping = now
        node.current_testing_script_set.save()
        passed_script_result = factory.make_ScriptResult(
            script_set=node.current_testing_script_set,
            status=SCRIPT_STATUS.PASSED)
        failed_script_result = factory.make_ScriptResult(
            script_set=node.current_testing_script_set,
            status=SCRIPT_STATUS.FAILED)
        pending_script_result = factory.make_ScriptResult(
            script_set=node.current_testing_script_set,
            status=SCRIPT_STATUS.PENDING)
        script = factory.make_Script(timeout=timedelta(seconds=60))
        running_script_result = factory.make_ScriptResult(
            script_set=node.current_testing_script_set,
            status=SCRIPT_STATUS.RUNNING, script=script,
            started=now - timedelta(minutes=3))
        self.patch(Node, 'stop')

        mark_testing_nodes_failed_after_missing_timeout()
        node = reload_object(node)

        self.assertEquals(NODE_STATUS.FAILED_TESTING, node.status)
        self.assertEquals(
            "%s has run past it's timeout(%s)" % (
                running_script_result.name,
                str(running_script_result.script.timeout)),
            node.error_description)
        self.assertEquals(
            SCRIPT_STATUS.PASSED, reload_object(passed_script_result).status)
        self.assertEquals(
            SCRIPT_STATUS.FAILED, reload_object(failed_script_result).status)
        self.assertEquals(
            SCRIPT_STATUS.TIMEDOUT,
            reload_object(pending_script_result).status)
        self.assertEquals(
            SCRIPT_STATUS.TIMEDOUT,
            reload_object(running_script_result).status)

    def test_mark_testing_nodes_failed_after_missing_timeout_prefetches(self):
        user = factory.make_admin()
        self.patch(status_monitor, 'fail_testing')
        nodes = []
        for _ in range(3):
            node = factory.make_Node(
                previous_status=random.choice(
                    list(NODE_TESTING_RESET_READY_TRANSITIONS)),
                status=NODE_STATUS.TESTING, with_empty_script_sets=True,
                owner=user)
            now = datetime.now()
            node.current_testing_script_set.last_ping = now
            node.current_testing_script_set.save()
            script = factory.make_Script(timeout=timedelta(seconds=60))
            factory.make_ScriptResult(
                script_set=node.current_testing_script_set,
                status=SCRIPT_STATUS.RUNNING, script=script,
                started=now - timedelta(minutes=3))
            nodes.append(node)

        counter = CountQueries()
        with counter:
            mark_testing_nodes_failed_after_missing_timeout()
        # Initial lookup and prefetch take two queries. This is done once to
        # find the nodes which nodes are being tests and on each node which
        # scripts are currently running.
        self.assertEquals((len(nodes) + 1) * 2, counter.num_queries)


class TestStatusMonitorService(MAASServerTestCase):

    def test_init_with_default_interval(self):
        # The service itself calls `check_status` in a thread, via a couple of
        # decorators. This indirection makes it clearer to mock
        # `cleanup_old_nonces` here and track calls to it.
        mock_check_status = self.patch(status_monitor, "check_status")
        # Making `deferToDatabase` use the current thread helps testing.
        self.patch(status_monitor, "deferToDatabase", maybeDeferred)

        service = StatusMonitorService()
        # Use a deterministic clock instead of the reactor for testing.
        service.clock = Clock()

        # The interval is stored as `step` by TimerService,
        # StatusMonitorService's parent class.
        interval = 60  # seconds.
        self.assertEqual(service.step, interval)

        # `check_status` is not called before the service is started.
        self.assertThat(mock_check_status, MockNotCalled())
        # `check_status` is called the moment the service is started.
        service.startService()
        self.assertThat(mock_check_status, MockCalledOnceWith())
        # Advancing the clock by `interval - 1` means that
        # `mark_nodes_failed_after_expiring` has still only been called once.
        service.clock.advance(interval - 1)
        self.assertThat(mock_check_status, MockCalledOnceWith())
        # Advancing the clock one more second causes another call to
        # `check_status`.
        service.clock.advance(1)
        self.assertThat(mock_check_status, MockCallsMatch(call(), call()))

    def test_interval_can_be_set(self):
        interval = self.getUniqueInteger()
        service = StatusMonitorService(interval)
        self.assertEqual(interval, service.step)
