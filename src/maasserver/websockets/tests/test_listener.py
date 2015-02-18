# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.listner`"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from crochet import wait_for_reactor
from django.db import connection
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.async import transactional
from maasserver.websockets.listener import (
    PostgresListener,
    PostgresListenerNotifyError,
    )
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCalledWith,
    )
from mock import sentinel
from provisioningserver.utils.twisted import DeferredValue
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread


class TestPostgresListener(MAASServerTestCase):

    @transactional
    def send_notification(self, event, obj_id):
        cursor = connection.cursor()
        cursor.execute("NOTIFY %s, '%s';" % (event, obj_id))
        cursor.close()

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_handler_on_notification(self):
        listener = PostgresListener()
        dv = DeferredValue()
        listener.register("node", lambda *args: dv.set(args))
        yield listener.start()
        try:
            yield deferToThread(self.send_notification, "node_create", 1)
            yield dv.get(timeout=2)
            self.assertEqual(('create', '1'), dv.value)
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_connects_to_database(self):
        listener = PostgresListener()

        yield listener.tryConnection()
        try:
            self.assertTrue(listener.connected())
        finally:
            yield listener.stop()

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_logs_error(self):
        listener = PostgresListener()

        exc = factory.make_exception()
        self.patch(listener, "startConnection").side_effect = exc
        mock_logMsg = self.patch(listener, "logMsg")
        self.patch(reactor, "callLater")
        yield listener.tryConnection()
        self.assertThat(
            mock_logMsg,
            MockCalledOnceWith(
                format="Unable to connect to database: %(error)r",
                error=exc.message))

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_will_retry_in_3_seconds(self):
        listener = PostgresListener()

        self.patch(
            listener, "startConnection").side_effect = factory.make_exception()
        mock_callLater = self.patch(reactor, "callLater")
        yield listener.tryConnection()
        self.assertThat(
            mock_callLater,
            MockCalledWith(3, listener.tryConnection))

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_calls_registerChannels_after_startConnection(self):
        listener = PostgresListener()

        self.patch(listener, "startConnection")
        mock_registerChannels = self.patch(listener, "registerChannels")
        mock_registerChannels.side_effect = factory.make_exception()
        self.patch(reactor, "callLater")
        yield listener.tryConnection()
        self.assertThat(
            mock_registerChannels,
            MockCalledOnceWith())

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_adds_self_to_reactor(self):
        listener = PostgresListener()

        self.patch(listener, "startConnection")
        self.patch(listener, "registerChannels")
        mock_addReader = self.patch(reactor, "addReader")
        yield listener.tryConnection()
        self.assertThat(
            mock_addReader,
            MockCalledOnceWith(listener))

    @wait_for_reactor
    @inlineCallbacks
    def test__tryConnection_logs_success(self):
        listener = PostgresListener()

        mock_logMsg = self.patch(listener, "logMsg")
        yield listener.tryConnection()
        try:
            self.assertThat(
                mock_logMsg,
                MockCalledOnceWith("Listening for notificaton from database."))
        finally:
            yield listener.stop()

    def test_register_adds_channel_and_handler(self):
        listener = PostgresListener()
        channel = factory.make_name("channel")
        listener.register(channel, sentinel.handler)
        self.assertEqual(
            [sentinel.handler], listener.listeners[channel])

    def test__convertChannel_raises_exception_if_not_valid_channel(self):
        listener = PostgresListener()
        self.assertRaises(
            PostgresListenerNotifyError,
            listener.convertChannel, "node_create")

    def test__convertChannel_raises_exception_if_not_valid_action(self):
        listener = PostgresListener()
        self.assertRaises(
            PostgresListenerNotifyError,
            listener.convertChannel, "node_unknown")
