# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.utils.dbtasks`."""


import random
import threading
from unittest.mock import sentinel

from twisted.internet import reactor
from twisted.internet.defer import (
    Deferred,
    DeferredQueue,
    inlineCallbacks,
    QueueOverflow,
)

from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.dbtasks import (
    DatabaseTaskAlreadyRunning,
    DatabaseTasksService,
)
from maasserver.utils.orm import transactional
from maastesting import get_testing_timeout
from maastesting.crochet import wait_for
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from maastesting.twisted import TwistedLoggerFixture

TIMEOUT = get_testing_timeout()
wait_for_reactor = wait_for()


def noop():
    pass


class TestDatabaseTaskService(MAASTestCase):
    """Tests for `DatabaseTasksService`."""

    def test_init(self):
        service = DatabaseTasksService()
        self.assertIsInstance(service.queue, DeferredQueue)
        self.assertEqual(service.queue.size, 0)
        self.assertEqual(service.queue.backlog, 1)

    def test_cannot_add_task_to_unstarted_service(self):
        service = DatabaseTasksService()
        self.assertRaises(QueueOverflow, service.addTask, noop)

    def test_cannot_add_task_to_stopped_service(self):
        service = DatabaseTasksService()
        service.startService()
        service.stopService()
        self.assertRaises(QueueOverflow, service.addTask, noop)

    def test_startup_creates_queue_with_previously_defined(self):
        service = DatabaseTasksService()
        service.startService()
        try:
            self.assertIsInstance(service.queue, DeferredQueue)
            self.assertEqual(service.queue.backlog, 1)
        finally:
            service.stopService()

    def test_task_is_executed_in_other_thread(self):
        def get_thread_ident():
            return threading.current_thread().ident

        service = DatabaseTasksService()
        service.startService()
        try:
            ident_from_task = service.deferTask(get_thread_ident).wait(TIMEOUT)
            ident_from_here = get_thread_ident()
            self.assertIsInstance(ident_from_task, int)
            self.assertNotEqual(ident_from_task, ident_from_here)
        finally:
            service.stopService()

    def test_arguments_are_passed_through_to_task(self):
        def return_args(*args, **kwargs):
            return sentinel.here, args, kwargs

        service = DatabaseTasksService()
        service.startService()
        try:
            result = service.deferTask(
                return_args, sentinel.arg, kw=sentinel.kw
            ).wait(TIMEOUT)
            self.assertEqual(
                (sentinel.here, (sentinel.arg,), {"kw": sentinel.kw}),
                result,
            )
        finally:
            service.stopService()

    def test_callbacks_are_called_from_deferredTask(self):
        def simple_function(input):
            return input + " world"

        def callback(data):
            sentinel.callback = data

        service = DatabaseTasksService()
        service.startService()
        try:
            service.deferTaskWithCallbacks(
                simple_function, [callback], "Hello"
            )
            service.syncTask().wait(TIMEOUT)
            self.assertEqual(
                "Hello world",
                sentinel.callback,
            )
        finally:
            service.stopService()

    def test_tasks_are_all_run_before_shutdown_completes(self):
        service = DatabaseTasksService()
        service.startService()
        try:
            queue = service.queue
            event = threading.Event()
            count = random.randint(20, 40)
            for _ in range(count):
                service.addTask(event.wait)
            # The queue has `count` tasks (or `count - 1` tasks; the first may
            # have already been pulled off the queue) still pending.
            self.assertIn(len(queue.pending), (count, count - 1))
        finally:
            event.set()
            service.stopService()
        # The queue is empty and nothing is waiting.
        self.assertEqual(queue.waiting, [])
        self.assertEqual(queue.pending, [])

    @wait_for_reactor
    @inlineCallbacks
    def test_deferred_task_can_be_cancelled_when_enqueued(self):
        things = []  # This will NOT be populated by tasks.

        service = DatabaseTasksService()
        yield service.startService()
        try:
            event = threading.Event()
            service.deferTask(event.wait)
            service.deferTask(things.append, 1).cancel()
        finally:
            event.set()
            yield service.stopService()

        self.assertEqual([], things)

    @wait_for_reactor
    @inlineCallbacks
    def test_deferred_task_cannot_be_cancelled_when_running(self):
        # DatabaseTaskAlreadyRunning is raised when attempting to cancel a
        # database task that's already running.
        service = DatabaseTasksService()
        yield service.startService()
        try:
            ready = Deferred()
            d = service.deferTask(reactor.callFromThread, ready.callback, None)
            # Wait for the task to begin running.
            yield ready
            # We have the reactor thread. Even if the task completes its
            # status will not be updated until the reactor's next iteration.
            self.assertRaises(DatabaseTaskAlreadyRunning, d.cancel)
        finally:
            yield service.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_sync_task_can_be_cancelled_when_enqueued(self):
        things = []  # This will NOT be populated by tasks.

        service = DatabaseTasksService()
        yield service.startService()
        try:
            event = threading.Event()
            service.deferTask(event.wait)
            service.syncTask().cancel()
        finally:
            event.set()
            yield service.stopService()

        self.assertEqual([], things)

    def test_sync_task_fires_with_service(self):
        service = DatabaseTasksService()
        service.startService()
        try:
            self.assertIs(service.syncTask().wait(TIMEOUT), service)
        finally:
            service.stopService()

    def test_failure_in_deferred_task_does_not_crash_service(self):
        things = []  # This will be populated by tasks.
        exception_type = factory.make_exception_type()

        def be_bad():
            raise exception_type("I'm being very naughty.")

        service = DatabaseTasksService()
        service.startService()
        try:
            service.deferTask(things.append, 1).wait(TIMEOUT)
            self.assertRaises(
                exception_type, service.deferTask(be_bad).wait, TIMEOUT
            )
            service.deferTask(things.append, 2).wait(TIMEOUT)
        finally:
            service.stopService()

        self.assertEqual([1, 2], things)

    def test_failure_in_added_task_does_not_crash_service(self):
        things = []  # This will be populated by tasks.
        exception_type = factory.make_exception_type()

        def be_bad():
            raise exception_type("I'm bad, so bad.")

        service = DatabaseTasksService()
        service.startService()
        try:
            service.addTask(things.append, 1)
            service.addTask(be_bad)
            service.addTask(things.append, 2)
        finally:
            service.stopService()

        self.assertEqual([1, 2], things)

    def test_failure_in_task_is_logged(self):
        logger = self.useFixture(TwistedLoggerFixture())

        service = DatabaseTasksService()
        service.startService()
        try:
            service.addTask(lambda: 0 / 0)
        finally:
            service.stopService()

        self.assertRegex(
            logger.output,
            r"(?s)Unhandled failure in database task\..*Traceback \(most recent call last\):.*builtins.ZeroDivision.*",
        )


class TestDatabaseTaskServiceWithActualDatabase(MAASTransactionServerTestCase):
    """Tests for `DatabaseTasksService` with the databse."""

    def test_task_can_access_database_from_other_thread(self):
        @transactional
        def database_task():
            # Merely being here means we've accessed the database.
            return sentinel.beenhere

        service = DatabaseTasksService()
        service.startService()
        try:
            result = service.deferTask(database_task).wait(TIMEOUT)
            self.assertIs(result, sentinel.beenhere)
        finally:
            service.stopService()
