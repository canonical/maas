# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.listener`"""


from collections import namedtuple
import errno
from unittest.mock import ANY, call, MagicMock, Mock, sentinel

from django.db import connection
from psycopg2 import OperationalError
from testtools import ExpectedException
from testtools.matchers import ContainsDict, Equals, HasLength
from twisted.internet import error, reactor
from twisted.internet.defer import (
    CancelledError,
    Deferred,
    DeferredQueue,
    inlineCallbacks,
    returnValue,
)
from twisted.logger import LogLevel
from twisted.python.failure import Failure

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
from maastesting.crochet import wait_for
from maastesting.matchers import (
    DocTestMatches,
    MockCalledOnceWith,
    MockCalledWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.utils.twisted import DeferredValue

wait_for_reactor = wait_for()


FakeNotify = namedtuple("FakeNotify", ["channel", "payload"])


class PostgresListenerServiceSpy(PostgresListenerService):
    """Save received notifies `captured_notifies` before processing them.."""

    HANDLE_NOTIFY_DELAY = CHANNEL_REGISTRAR_DELAY = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Captured notifications from the database will go here.
        self._captured_notifies = DeferredQueue()
        # Change notifications to a frozenset. This makes sure that the system
        # message does not go into the queue. Instead it should call the
        # handler directly in `doRead`.
        self.notifications = frozenset()

    def _process_notifies(self):
        self.log.debug("Start processing notifies for tests")
        for notify in self.connection.connection.notifies:
            self._captured_notifies.put(notify)
        super()._process_notifies()
        self.log.debug("Done processing notifies for tests")

    @inlineCallbacks
    def wait_notification(self, channel):
        """Wait for a notification to be received."""
        while True:
            notice = yield self._captured_notifies.get()
            if notice.channel == channel:
                self.log.debug(f"Found a notification for channel {channel}")
                returnValue(notice)


class TestPostgresListenerService(MAASServerTestCase):
    @transactional
    def send_notification(self, event, obj_id):
        cursor = connection.cursor()
        cursor.execute(f"NOTIFY {event}, '{obj_id}';")
        cursor.close()

    def mock_cursor(self, listener):
        listener.connection = MagicMock()
        cursor_ctx = MagicMock()
        listener.connection.cursor.return_value = cursor_ctx
        cursor = MagicMock()
        cursor_ctx.__enter__.return_value = cursor
        return cursor

    def test_isSystemChannel_returns_true_for_channel_starting_with_sys(self):
        channel = factory.make_name("sys_", sep="")
        listener = PostgresListenerService()
        self.assertTrue(listener.isSystemChannel(channel))

    def test_isSystemChannel_returns_false_for_channel_not__sys(self):
        channel = factory.make_name("node_", sep="")
        listener = PostgresListenerService()
        self.assertFalse(listener.isSystemChannel(channel))

    def test_raises_error_if_system_handler_registered_more_than_once(self):
        channel = factory.make_name("sys_", sep="")
        listener = PostgresListenerService()
        listener.register(channel, lambda *args: None)
        with ExpectedException(PostgresListenerRegistrationError):
            listener.register(channel, lambda *args: None)

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_system_handler_on_notification(self):
        listener = PostgresListenerService()
        listener.HANDLE_NOTIFY_DELAY = listener.CHANNEL_REGISTRAR_DELAY = 0
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
    def test_handles_missing_system_handler_on_notification(self):
        listener = PostgresListenerServiceSpy()
        yield listener.startService()

        # Use a randomised channel name even though LISTEN/NOTIFY is
        # per-database and _not_ per-cluster.
        channel = factory.make_name("sys_test", sep="_").lower()
        self.assertTrue(listener.isSystemChannel(channel))
        payload = factory.make_name("payload")

        yield deferToDatabase(listener.registerChannel, channel)
        listener.listeners[channel] = []

        try:
            deferred = listener.wait_notification(channel)
            # Notify our channel with a payload and wait for it to come
            yield deferToDatabase(self.send_notification, channel, payload)
            notice = yield deferred
            self.assertEqual(notice.payload, payload)
            # Our channel has been deleted from the listeners map.
            self.assertNotIn(channel, listener.listeners)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_handles_missing_notify_system_listener_on_notification(self):
        listener = PostgresListenerServiceSpy()
        yield listener.startService()
        yield deferToDatabase(listener.registerChannel, "sys_test")
        try:
            deferred = listener.wait_notification("sys_test")
            yield deferToDatabase(self.send_notification, "sys_test", "msg")
            notice = yield deferred
            self.assertEqual(notice.payload, "msg")
            self.assertFalse("sys_test" in listener.listeners)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_notification(self):
        listener = PostgresListenerService()
        listener.HANDLE_NOTIFY_DELAY = listener.CHANNEL_REGISTRAR_DELAY = 0
        dv = DeferredValue()
        listener.register("machine", lambda *args: dv.set(args))
        yield listener.startService()
        yield listener.channelRegistrarDone
        try:
            yield deferToDatabase(self.send_notification, "machine_create", 1)
            yield dv.get(timeout=2)
            self.assertEqual(("create", "1"), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_handler_on_notification_with_delayed_registration(self):
        listener = PostgresListenerService()
        listener.HANDLE_NOTIFY_DELAY = listener.CHANNEL_REGISTRAR_DELAY = 0
        dv = DeferredValue()
        yield listener.startService()
        try:
            # Register after the service has been started. The handler should
            # still be called.
            listener.register("machine", lambda *args: dv.set(args))
            yield listener.channelRegistrarDone
            yield deferToDatabase(self.send_notification, "machine_create", 1)
            yield dv.get(timeout=2)
            self.assertEqual(("create", "1"), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_tryConnection_connects_to_database(self):
        listener = PostgresListenerService()

        yield listener.tryConnection()
        try:
            self.assertTrue(listener.connected())
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_tryConnection_logs_error(self):
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
    def test_tryConnection_will_retry_in_3_seconds_if_autoReconnect_set(self):
        listener = PostgresListenerService()
        listener.autoReconnect = True

        startConnection = self.patch(listener, "startConnection")
        startConnection.side_effect = factory.make_exception()
        deferLater = self.patch(listener_module, "deferLater")
        deferLater.return_value = sentinel.retry

        result = yield listener.tryConnection()

        self.assertIs(result, sentinel.retry)
        self.assertThat(deferLater, MockCalledWith(reactor, 3, ANY))

    @wait_for_reactor
    @inlineCallbacks
    def test_tryConnection_will_not_retry_if_autoReconnect_not_set(self):
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
    def test_tryConnection_reregisters_channels(self):
        listener = PostgresListenerService()
        listener.HANDLE_NOTIFY_DELAY = listener.CHANNEL_REGISTRAR_DELAY = 0
        handler = object()
        listener.register("channel", handler)
        yield listener.startService()
        yield listener.channelRegistrarDone
        listener.registerChannel = Mock()
        yield listener.stopService()
        yield listener.tryConnection()
        yield listener.channelRegistrarDone
        try:
            self.assertEqual(
                [call("channel")], listener.registerChannel.mock_calls
            )
            self.assertEqual({"channel": [handler]}, listener.listeners)
            self.assertEqual({"channel"}, listener.registeredChannels)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_stopping_cancels_start(self):
        listener = PostgresListenerService()

        # Start then stop immediately, without waiting for start to complete.
        starting = listener.startService()
        starting_spy = DeferredValue()
        starting_spy.observe(starting)
        stopping = listener.stopService()

        # Both `starting` and `stopping` have callbacks yet to fire.
        self.assertNotEqual([], starting.callbacks)
        self.assertNotEqual([], stopping.callbacks)

        # Wait for the listener to stop.
        yield stopping

        # Neither `starting` nor `stopping` have callbacks. This is because
        # `stopping` chained itself onto the end of `starting`.
        self.assertEqual([], starting.callbacks)
        self.assertEqual([], stopping.callbacks)

        # Confirmation that `starting` was cancelled.
        with ExpectedException(CancelledError):
            yield starting_spy.get()

    @wait_for_reactor
    def test_multiple_starts_return_same_Deferred(self):
        listener = PostgresListenerService()
        self.assertIs(listener.startService(), listener.startService())
        return listener.stopService()

    @wait_for_reactor
    def test_multiple_stops_return_same_Deferred(self):
        listener = PostgresListenerService()
        self.assertIs(listener.stopService(), listener.stopService())
        return listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_tryConnection_adds_self_to_reactor(self):
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
    def test_tryConnection_closes_connection_on_failure(self):
        listener = PostgresListenerService()

        exc_type = factory.make_exception_type()
        startReading = self.patch(listener, "startReading")
        startReading.side_effect = exc_type("no reason")

        with ExpectedException(exc_type):
            yield listener.tryConnection()

        self.assertIsNone(listener.connection)

    @wait_for_reactor
    @inlineCallbacks
    def test_tryConnection_logs_success(self):
        listener = PostgresListenerService()

        with TwistedLoggerFixture() as logger:
            yield listener.tryConnection()
            try:
                self.assertEqual(
                    "Listening for database notifications.",
                    logger.output,
                )
            finally:
                yield listener.stopService()

    @wait_for_reactor
    def test_connectionLost_logs_reason(self):
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
    def test_connectionLost_does_not_log_reason_when_lost_cleanly(self):
        listener = PostgresListenerService()

        with TwistedLoggerFixture() as logger:
            listener.connectionLost(Failure(error.ConnectionDone()))

        self.assertThat(logger.errors, HasLength(0))

    @wait_for_reactor
    @inlineCallbacks
    def test_register_adds_channel_and_handler(self):
        listener = PostgresListenerService()
        listener.HANDLE_NOTIFY_DELAY = listener.CHANNEL_REGISTRAR_DELAY = 0
        channel = factory.make_name("channel", sep="_").lower()
        listener.register(channel, sentinel.handler)
        yield listener.startService()
        try:
            yield listener.channelRegistrarDone
            self.assertEqual([sentinel.handler], listener.listeners[channel])
            self.assertIn(channel, listener.registeredChannels)
        finally:
            yield listener.stopService()

    def test_register_not_starts_registrar_not_connected(self):
        listener = PostgresListenerService()
        channel = factory.make_name("channel", sep="_").lower()
        listener.register(channel, sentinel.handler)
        self.assertIsNone(listener.channelRegistrarDone)
        self.assertEqual([sentinel.handler], listener.listeners[channel])
        self.assertNotIn(channel, listener.registeredChannels)

    def test_convertChannel_raises_exception_if_not_valid_channel(self):
        listener = PostgresListenerService()
        self.assertRaises(
            PostgresListenerNotifyError, listener.convertChannel, "node_create"
        )

    def test_convertChannel_raises_exception_if_not_valid_action(self):
        listener = PostgresListenerService()
        self.assertRaises(
            PostgresListenerNotifyError,
            listener.convertChannel,
            "node_unknown",
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_doRead_removes_self_from_reactor_on_error(self):
        listener = PostgresListenerService()

        connection = self.patch(listener, "connection")
        connection.connection.poll.side_effect = OperationalError()

        self.patch(reactor, "removeReader")
        self.patch(listener, "connectionLost")

        failure = listener.doRead()

        # No failure is returned; see the comment in
        # PostgresListenerService.doRead() that explains why we don't do that.
        self.assertIsNone(failure)

        # The listener has begun disconnecting.
        self.assertIsInstance(listener.disconnecting, Deferred)
        # Wait for disconnection to complete.
        yield listener.disconnecting
        # The listener has removed itself from the reactor.
        self.assertThat(reactor.removeReader, MockCalledOnceWith(listener))
        # connectionLost() has been called with a simple ConnectionLost.
        self.assertThat(listener.connectionLost, MockCalledOnceWith(ANY))
        [failure] = listener.connectionLost.call_args[0]
        self.assertIsInstance(failure, Failure)
        self.assertIsInstance(failure.value, error.ConnectionLost)

    def test_doRead_adds_notifies_to_notifications(self):
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
        self.assertCountEqual(listener.notifications, set(notifications))

    @wait_for_reactor
    @inlineCallbacks
    def test_listener_ignores_ENOENT_when_removing_itself_from_reactor(self):
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
    def test_listener_waits_for_notifier_to_complete(self):
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
        channel = factory.make_name("channel", sep="_").lower()
        listener.register(channel, sentinel.handler)
        with ExpectedException(PostgresListenerUnregistrationError):
            listener.unregister(channel, sentinel.other_handler)

    def test_unregister_removes_handler_last(self):
        listener = PostgresListenerService()
        channel = factory.make_name("channel", sep="_").lower()
        listener.register(channel, sentinel.handler)
        self.assertEqual({channel: [sentinel.handler]}, listener.listeners)
        listener.unregister(channel, sentinel.handler)
        self.assertEqual({}, listener.listeners)

    def test_unregister_removes_handler_others(self):
        listener = PostgresListenerService()
        channel = factory.make_name("channel", sep="_").lower()
        listener.register(channel, sentinel.handler1)
        listener.register(channel, sentinel.handler2)
        listener.unregister(channel, sentinel.handler2)
        self.assertEqual({channel: [sentinel.handler1]}, listener.listeners)

    @wait_for_reactor
    @inlineCallbacks
    def test_unregister_calls_unregisterChannel_when_connected(self):
        listener = PostgresListenerService()
        listener.HANDLE_NOTIFY_DELAY = listener.CHANNEL_REGISTRAR_DELAY = 0
        channel = factory.make_name("channel", sep="_").lower()
        listener.register(channel, sentinel.handler)
        yield listener.startService()
        try:
            yield listener.channelRegistrarDone
            self.assertIn(channel, listener.registeredChannels)
            listener.unregister(channel, sentinel.handler)
            yield listener.channelRegistrarDone
        finally:
            yield listener.stopService()

        self.assertNotIn(channel, listener.registeredChannels)

    @wait_for_reactor
    @inlineCallbacks
    def test_unregister_doesnt_call_unregisterChannel_multi_handlers(self):
        listener = PostgresListenerService()
        listener.HANDLE_NOTIFY_DELAY = listener.CHANNEL_REGISTRAR_DELAY = 0
        channel = factory.make_name("channel", sep="_").lower()
        listener.register(channel, sentinel.handler)
        listener.register(channel, sentinel.other_handler)
        listener.registeredChannels = set()
        listener.connection = MagicMock()
        mock_unregisterChannel = self.patch(listener, "unregisterChannel")
        listener.unregister(channel, sentinel.handler)
        yield listener.channelRegistrarDone
        self.assertThat(mock_unregisterChannel, MockNotCalled())

    def test_registerChannel_calls_listen_once_for_system_channel(self):
        listener = PostgresListenerService()
        cursor = self.mock_cursor(listener)
        channel = factory.make_name("sys", sep="_").lower()
        listener.registerChannel(channel)
        self.assertThat(
            cursor.execute, MockCalledOnceWith("LISTEN %s;" % channel)
        )

    def test_registerChannel_calls_listen_per_action_for_channel(self):
        listener = PostgresListenerService()
        cursor = self.mock_cursor(listener)
        channel = factory.make_name("node", sep="_").lower()
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
        cursor = self.mock_cursor(listener)
        channel = factory.make_name("sys", sep="_").lower()
        listener.unregisterChannel(channel)
        self.assertThat(
            cursor.execute, MockCalledOnceWith("UNLISTEN %s;" % channel)
        )

    def test_unregisterChannel_calls_unlisten_per_action_for_channel(self):
        listener = PostgresListenerService()
        cursor = self.mock_cursor(listener)
        channel = factory.make_name("node", sep="_").lower()
        listener.unregisterChannel(channel)
        self.assertThat(
            cursor.execute,
            MockCallsMatch(
                call("UNLISTEN %s_create;" % channel),
                call("UNLISTEN %s_delete;" % channel),
                call("UNLISTEN %s_update;" % channel),
            ),
        )

    def test_listen_registers_and_unregisters_channel(self):
        listener = PostgresListenerService()
        listener.register = MagicMock()
        listener.unregister = MagicMock()
        channel = factory.make_name("sys", sep="_").lower()
        with listener.listen(channel, sentinel.handler):
            listener.register.assert_called_once_with(
                channel, sentinel.handler
            )
        listener.unregister.assert_called_once_with(channel, sentinel.handler)

    def test_listen_unregisters_channel_when_exception_raised(self):
        listener = PostgresListenerService()
        listener.register = MagicMock()
        listener.unregister = MagicMock()
        channel = factory.make_name("sys", sep="_").lower()
        exception_text = "Expected exception"
        with ExpectedException(Exception, exception_text):
            with listener.listen(channel, sentinel.handler):
                listener.register.assert_called_once_with(
                    channel, sentinel.handler
                )
                raise Exception(exception_text)
        listener.unregister.assert_called_once_with(channel, sentinel.handler)
