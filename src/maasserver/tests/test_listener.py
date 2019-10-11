# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.listener`"""

__all__ = []

from collections import namedtuple
import errno
from unittest.mock import ANY, call, MagicMock, sentinel

from crochet import wait_for
from django.db import connection
from maasserver import listener as listener_module
from maasserver.listener import (
    PostgresListenerNotifyError,
    PostgresListenerRegistrationError,
    PostgresListenerService,
    PostgresListenerUnregistrationError,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maastesting.matchers import (
    DocTestMatches,
    MockCalledOnceWith,
    MockCalledWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.utils.twisted import DeferredValue
from psycopg2 import OperationalError
from testtools import ExpectedException
from testtools.matchers import (
    ContainsDict,
    Equals,
    HasLength,
    Is,
    IsInstance,
    Not,
)
from twisted.internet import error, reactor
from twisted.internet.defer import (
    CancelledError,
    Deferred,
    DeferredQueue,
    inlineCallbacks,
)
from twisted.logger import LogLevel
from twisted.python.failure import Failure


wait_for_reactor = wait_for(30)  # 30 seconds.


FakeNotify = namedtuple("FakeNotify", ["channel", "payload"])


class TestPostgresListenerService(MAASServerTestCase):
    @transactional
    def send_notification(self, event, obj_id):
        cursor = connection.cursor()
        cursor.execute("NOTIFY %s, '%s';" % (event, obj_id))
        cursor.close()

    def test_isSystemChannel_returns_true_for_channel_starting_with_sys(self):
        channel = factory.make_name("sys_", sep="")
        listener = PostgresListenerService()
        self.assertTrue(listener.isSystemChannel(channel))

    def test_isSystemChannel_returns_false_for_channel_not__sys(self):
        channel = factory.make_name("node_", sep="")
        listener = PostgresListenerService()
        self.assertFalse(listener.isSystemChannel(channel))

    def test__raises_error_if_system_handler_registered_more_than_once(self):
        channel = factory.make_name("sys_", sep="")
        listener = PostgresListenerService()
        listener.register(channel, lambda *args: None)
        with ExpectedException(PostgresListenerRegistrationError):
            listener.register(channel, lambda *args: None)

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_system_handler_on_notification(self):
        listener = PostgresListenerService()
        # Change notifications to a frozenset. This makes sure that
        # the system message does not go into the queue. Instead if should
        # call the handler directly in `doRead`.
        listener.notifications = frozenset()
        dv = DeferredValue()
        listener.register("sys_test", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.send_notification, "sys_test", 1)
            yield dv.get(timeout=2)
            self.assertEqual(("sys_test", "1"), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_event_on_connection(self):
        listener = PostgresListenerService()
        start_calls = []
        stop_calls = []
        listener.events.connected.registerHandler(
            lambda: start_calls.append(True)
        )
        listener.events.disconnected.registerHandler(
            lambda reason: stop_calls.append(reason)
        )
        yield listener.startService()
        self.assertEqual(len(start_calls), 1)
        yield listener.stopService()
        self.assertEqual(len(stop_calls), 1)
        [failure] = stop_calls
        self.assertIsInstance(failure.value, error.ConnectionDone)

    @wait_for_reactor
    @inlineCallbacks
    def test__handles_missing_system_handler_on_notification(self):
        # Captured notifications from the database will go here.
        notices = DeferredQueue()

        class PostgresListenerServiceSpy(PostgresListenerService):
            """Send notices off to `notices` right after processing."""

            def doRead(self):
                try:
                    self.connection.connection.poll()
                except Exception:
                    self.loseConnection(Failure(error.ConnectionLost()))
                else:
                    # Copy the pending notices now but don't put them in the
                    # queue until after the real doRead has processed them.
                    notifies = list(self.connection.connection.notifies)
                    try:
                        return super().doRead()
                    finally:
                        for notice in notifies:
                            notices.put(notice)

        listener = PostgresListenerServiceSpy()
        # Change notifications to a frozenset. This makes sure that
        # the system message does not go into the queue. Instead if should
        # call the handler directly in `doRead`.
        listener.notifications = frozenset()
        yield listener.startService()

        # Use a randomised channel name even though LISTEN/NOTIFY is
        # per-database and _not_ per-cluster.
        channel = factory.make_name("sys_test", sep="_").lower()
        self.assertTrue(listener.isSystemChannel(channel))
        payload = factory.make_name("payload")

        yield deferToDatabase(listener.registerChannel, channel)
        listener.listeners[channel] = []
        try:
            # Notify our channel with a payload and wait for it to come back.
            yield deferToDatabase(self.send_notification, channel, payload)
            while True:
                notice = yield notices.get()
                if notice.channel == channel:
                    self.assertThat(notice.payload, Equals(payload))
                    # Our channel has been deleted from the listeners map.
                    self.assertFalse(channel in listener.listeners)
                    break
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__handles_missing_notify_system_listener_on_notification(self):
        listener = PostgresListenerService()
        # Change notifications to a frozenset. This makes sure that
        # the system message does not go into the queue. Instead if should
        # call the handler directly in `doRead`.
        listener.notifications = frozenset()
        yield listener.startService()
        yield deferToDatabase(listener.registerChannel, "sys_test")
        try:
            yield deferToDatabase(self.send_notification, "sys_test", 1)
            self.assertFalse("sys_test" in listener.listeners)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_notification(self):
        listener = PostgresListenerService()
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield deferToDatabase(self.send_notification, "machine_create", 1)
            yield dv.get(timeout=2)
            self.assertEqual(("create", "1"), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_notification_with_delayed_registration(self):
        listener = PostgresListenerService()
        dv = DeferredValue()
        yield listener.startService()
        try:
            # Register after the service has been started. The handler should
            # still be called.
            listener.register("machine", lambda *args: dv.set(args))
            yield deferToDatabase(self.send_notification, "machine_create", 1)
            yield dv.get(timeout=2)
            self.assertEqual(("create", "1"), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_connects_to_database(self):
        listener = PostgresListenerService()

        yield listener.tryConnection()
        try:
            self.assertTrue(listener.connected())
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_sets_registeredChannels_to_True(self):
        listener = PostgresListenerService()

        yield listener.tryConnection()
        try:
            self.assertTrue(listener.registeredChannels)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_logs_error(self):
        listener = PostgresListenerService()

        exception_type = factory.make_exception_type()
        exception_message = factory.make_name("message")

        startConnection = self.patch(listener, "startConnection")
        startConnection.side_effect = exception_type(exception_message)

        with TwistedLoggerFixture() as logger:
            with ExpectedException(exception_type):
                yield listener.tryConnection()

        self.assertThat(logger.events, HasLength(1))
        self.assertThat(
            logger.events[0],
            ContainsDict(
                {
                    "log_format": Equals(
                        "Unable to connect to database: {error}"
                    ),
                    "log_level": Equals(LogLevel.error),
                    "error": Equals(exception_message),
                }
            ),
        )

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_will_retry_in_3_seconds_if_autoReconnect_set(self):
        listener = PostgresListenerService()
        listener.autoReconnect = True

        startConnection = self.patch(listener, "startConnection")
        startConnection.side_effect = factory.make_exception()
        deferLater = self.patch(listener_module, "deferLater")
        deferLater.return_value = sentinel.retry

        result = yield listener.tryConnection()

        self.assertThat(result, Is(sentinel.retry))
        self.assertThat(deferLater, MockCalledWith(reactor, 3, ANY))

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_will_not_retry_if_autoReconnect_not_set(self):
        listener = PostgresListenerService()
        listener.autoReconnect = False

        exception_type = factory.make_exception_type()
        exception_message = factory.make_name("message")

        startConnection = self.patch(listener, "startConnection")
        startConnection.side_effect = exception_type(exception_message)
        deferLater = self.patch(listener_module, "deferLater")
        deferLater.return_value = sentinel.retry

        with ExpectedException(exception_type):
            yield listener.tryConnection()

        self.assertThat(deferLater, MockNotCalled())

    @wait_for_reactor
    @inlineCallbacks
    def test__stopping_cancels_start(self):
        listener = PostgresListenerService()

        # Start then stop immediately, without waiting for start to complete.
        starting = listener.startService()
        starting_spy = DeferredValue()
        starting_spy.observe(starting)
        stopping = listener.stopService()

        # Both `starting` and `stopping` have callbacks yet to fire.
        self.assertThat(starting.callbacks, Not(Equals([])))
        self.assertThat(stopping.callbacks, Not(Equals([])))

        # Wait for the listener to stop.
        yield stopping

        # Neither `starting` nor `stopping` have callbacks. This is because
        # `stopping` chained itself onto the end of `starting`.
        self.assertThat(starting.callbacks, Equals([]))
        self.assertThat(stopping.callbacks, Equals([]))

        # Confirmation that `starting` was cancelled.
        with ExpectedException(CancelledError):
            yield starting_spy.get()

    @wait_for_reactor
    def test__multiple_starts_return_same_Deferred(self):
        listener = PostgresListenerService()
        self.assertThat(listener.startService(), Is(listener.startService()))
        return listener.stopService()

    @wait_for_reactor
    def test__multiple_stops_return_same_Deferred(self):
        listener = PostgresListenerService()
        self.assertThat(listener.stopService(), Is(listener.stopService()))
        return listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_calls_registerChannels_after_startConnection(self):
        listener = PostgresListenerService()

        exception_type = factory.make_exception_type()

        self.patch(listener, "startConnection")
        mock_registerChannels = self.patch(listener, "registerChannels")
        mock_registerChannels.side_effect = exception_type

        with ExpectedException(exception_type):
            yield listener.tryConnection()

        self.assertThat(mock_registerChannels, MockCalledOnceWith())

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_adds_self_to_reactor(self):
        listener = PostgresListenerService()

        # Spy on calls to reactor.addReader.
        self.patch(reactor, "addReader").side_effect = reactor.addReader

        yield listener.tryConnection()
        try:
            self.assertThat(reactor.addReader, MockCalledOnceWith(listener))
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_closes_connection_on_failure(self):
        listener = PostgresListenerService()

        exc_type = factory.make_exception_type()
        startReading = self.patch(listener, "startReading")
        startReading.side_effect = exc_type("no reason")

        with ExpectedException(exc_type):
            yield listener.tryConnection()

        self.assertThat(listener.connection, Is(None))

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_logs_success(self):
        listener = PostgresListenerService()

        with TwistedLoggerFixture() as logger:
            yield listener.tryConnection()
            try:
                self.assertThat(
                    logger.output,
                    Equals("Listening for database notifications."),
                )
            finally:
                yield listener.stopService()

    @wait_for_reactor
    def test__connectionLost_logs_reason(self):
        listener = PostgresListenerService()
        failure = Failure(factory.make_exception("Treason!"))

        with TwistedLoggerFixture() as logger:
            listener.connectionLost(failure)

        self.assertThat(
            logger.output,
            DocTestMatches(
                """\
            Connection lost.
            Traceback (most recent call last):...
            Failure: maastesting.factory.TestException#...: Treason!
            """
            ),
        )

    @wait_for_reactor
    def test__connectionLost_does_not_log_reason_when_lost_cleanly(self):
        listener = PostgresListenerService()

        with TwistedLoggerFixture() as logger:
            listener.connectionLost(Failure(error.ConnectionDone()))

        self.assertThat(logger.errors, HasLength(0))

    def test_register_adds_channel_and_handler(self):
        listener = PostgresListenerService()
        channel = factory.make_name("channel")
        listener.register(channel, sentinel.handler)
        self.assertEqual([sentinel.handler], listener.listeners[channel])

    def test__convertChannel_raises_exception_if_not_valid_channel(self):
        listener = PostgresListenerService()
        self.assertRaises(
            PostgresListenerNotifyError, listener.convertChannel, "node_create"
        )

    def test__convertChannel_raises_exception_if_not_valid_action(self):
        listener = PostgresListenerService()
        self.assertRaises(
            PostgresListenerNotifyError,
            listener.convertChannel,
            "node_unknown",
        )

    @wait_for_reactor
    @inlineCallbacks
    def test__doRead_removes_self_from_reactor_on_error(self):
        listener = PostgresListenerService()

        connection = self.patch(listener, "connection")
        connection.connection.poll.side_effect = OperationalError()

        self.patch(reactor, "removeReader")
        self.patch(listener, "connectionLost")

        failure = listener.doRead()

        # No failure is returned; see the comment in
        # PostgresListenerService.doRead() that explains why we don't do that.
        self.assertThat(failure, Is(None))

        # The listener has begun disconnecting.
        self.assertThat(listener.disconnecting, IsInstance(Deferred))
        # Wait for disconnection to complete.
        yield listener.disconnecting
        # The listener has removed itself from the reactor.
        self.assertThat(reactor.removeReader, MockCalledOnceWith(listener))
        # connectionLost() has been called with a simple ConnectionLost.
        self.assertThat(listener.connectionLost, MockCalledOnceWith(ANY))
        [failure] = listener.connectionLost.call_args[0]
        self.assertThat(failure, IsInstance(Failure))
        self.assertThat(failure.value, IsInstance(error.ConnectionLost))

    def test__doRead_adds_notifies_to_notifications(self):
        listener = PostgresListenerService()
        notifications = [
            FakeNotify(
                channel=factory.make_name("channel_action"),
                payload=factory.make_name("payload"),
            )
            for _ in range(3)
        ]

        connection = self.patch(listener, "connection")
        connection.connection.poll.return_value = None
        # Add the notifications twice, so it can test that duplicates are
        # accumulated together.
        connection.connection.notifies = notifications + notifications
        self.patch(listener, "handleNotify")

        listener.doRead()
        self.assertItemsEqual(listener.notifications, set(notifications))

    @wait_for_reactor
    @inlineCallbacks
    def test__listener_ignores_ENOENT_when_removing_itself_from_reactor(self):
        listener = PostgresListenerService()

        self.patch(reactor, "addReader")
        self.patch(reactor, "removeReader")

        # removeReader() is going to have a nasty accident.
        enoent = IOError("ENOENT")
        enoent.errno = errno.ENOENT
        reactor.removeReader.side_effect = enoent

        # The listener starts and stops without issue.
        yield listener.startService()
        yield listener.stopService()

        # addReader() and removeReader() were both called.
        self.assertThat(reactor.addReader, MockCalledOnceWith(listener))
        self.assertThat(reactor.removeReader, MockCalledOnceWith(listener))

    @wait_for_reactor
    @inlineCallbacks
    def test__listener_waits_for_notifier_to_complete(self):
        listener = PostgresListenerService()

        yield listener.startService()
        try:
            self.assertTrue(listener.notifier.running)
        finally:
            yield listener.stopService()
            self.assertFalse(listener.notifier.running)

    def test_unregister_raises_error_if_channel_not_registered(self):
        listener = PostgresListenerService()
        with ExpectedException(PostgresListenerUnregistrationError):
            listener.unregister(factory.make_name("channel"), sentinel.handler)

    def test_unregister_raises_error_if_handler_does_not_match(self):
        listener = PostgresListenerService()
        channel = factory.make_name("channel")
        listener.register(channel, sentinel.handler)
        with ExpectedException(PostgresListenerUnregistrationError):
            listener.unregister(channel, sentinel.other_handler)

    def test_unregister_removes_handler(self):
        listener = PostgresListenerService()
        channel = factory.make_name("channel")
        listener.register(channel, sentinel.handler)
        listener.unregister(channel, sentinel.handler)
        self.assertEquals({channel: []}, listener.listeners)

    def test_unregister_calls_unregisterChannel_when_connected(self):
        listener = PostgresListenerService()
        channel = factory.make_name("channel")
        listener.register(channel, sentinel.handler)
        listener.registeredChannels = True
        listener.connection = sentinel.connection
        mock_unregisterChannel = self.patch(listener, "unregisterChannel")
        listener.unregister(channel, sentinel.handler)
        self.assertThat(mock_unregisterChannel, MockCalledOnceWith(channel))

    def test_unregister_doesnt_call_unregisterChannel_multi_handlers(self):
        listener = PostgresListenerService()
        channel = factory.make_name("channel")
        listener.register(channel, sentinel.handler)
        listener.register(channel, sentinel.other_handler)
        listener.registeredChannels = True
        listener.connection = sentinel.connection
        mock_unregisterChannel = self.patch(listener, "unregisterChannel")
        listener.unregister(channel, sentinel.handler)
        self.assertThat(mock_unregisterChannel, MockNotCalled())

    def test_registerChannel_calls_listen_once_for_system_channel(self):
        listener = PostgresListenerService()
        listener.connection = MagicMock()
        cursor = MagicMock()
        listener.connection.cursor.return_value = cursor
        channel = factory.make_name("sys_")
        listener.registerChannel(channel)
        self.assertThat(
            cursor.execute, MockCalledOnceWith("LISTEN %s;" % channel)
        )

    def test_registerChannel_calls_listen_per_action_for_channel(self):
        listener = PostgresListenerService()
        listener.connection = MagicMock()
        cursor = MagicMock()
        listener.connection.cursor.return_value = cursor
        channel = factory.make_name("node")
        listener.registerChannel(channel)
        self.assertThat(
            cursor.execute,
            MockCallsMatch(
                call("LISTEN %s_create;" % channel),
                call("LISTEN %s_delete;" % channel),
                call("LISTEN %s_update;" % channel),
            ),
        )

    def test_unregisterChannel_calls_unlisten_once_for_system_channel(self):
        listener = PostgresListenerService()
        listener.connection = MagicMock()
        cursor = MagicMock()
        listener.connection.cursor.return_value = cursor
        channel = factory.make_name("sys_")
        listener.unregisterChannel(channel)
        self.assertThat(
            cursor.execute, MockCalledOnceWith("UNLISTEN %s;" % channel)
        )

    def test_unregisterChannel_calls_unlisten_per_action_for_channel(self):
        listener = PostgresListenerService()
        listener.connection = MagicMock()
        cursor = MagicMock()
        listener.connection.cursor.return_value = cursor
        channel = factory.make_name("node")
        listener.unregisterChannel(channel)
        self.assertThat(
            cursor.execute,
            MockCallsMatch(
                call("UNLISTEN %s_create;" % channel),
                call("UNLISTEN %s_delete;" % channel),
                call("UNLISTEN %s_update;" % channel),
            ),
        )
