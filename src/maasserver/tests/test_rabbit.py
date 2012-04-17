# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Rabbit messaging tests."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []


import socket
import time

from amqplib import client_0_8 as amqp
from django.conf import settings
from maasserver.exceptions import NoRabbit
from maasserver.rabbit import (
    RabbitBase,
    RabbitExchange,
    RabbitMessaging,
    RabbitQueue,
    RabbitSession,
    )
from maasserver.testing.factory import factory
from maastesting.rabbit import (
    get_rabbit,
    uses_rabbit_fixture,
    )
from maastesting.testcase import TestCase
from testtools.testcase import ExpectedException


def run_rabbit_command(command):
    """Run a Rabbit command through rabbitctl, and return its output."""
    if isinstance(command, unicode):
        command = command.encode('ascii')
    rabbit_env = get_rabbit().runner.environment
    return rabbit_env.rabbitctl(command)[0]


class TestRabbitSession(TestCase):

    @uses_rabbit_fixture
    def test_connection_gets_connection(self):
        session = RabbitSession()
        # Referencing the connection property causes a connection to be
        # created.
        connection = session.connection
        self.assertIsNotNone(session._connection)
        # The same connection is returned every time.
        self.assertIs(connection, session.connection)

    def test_connection_raises_NoRabbit_if_cannot_connect(self):
        # Attempt to connect to a RabbitMQ on the local "discard"
        # service.  The connection will be refused.
        self.patch(settings, 'RABBITMQ_HOST', 'localhost:9')
        session = RabbitSession()
        with ExpectedException(NoRabbit):
            session.connection

    def test_connection_propagates_exceptions(self):

        def fail(*args, **kwargs):
            raise socket.error("Connection not refused, but failed anyway.")

        self.patch(amqp, 'Connection', fail)
        session = RabbitSession()
        with ExpectedException(socket.error):
            session.connection

    def test_disconnect(self):
        session = RabbitSession()
        session.disconnect()
        self.assertIsNone(session._connection)


class TestRabbitMessaging(TestCase):

    @uses_rabbit_fixture
    def test_messaging_getExchange(self):
        exchange_name = factory.getRandomString()
        messaging = RabbitMessaging(exchange_name)
        exchange = messaging.getExchange()
        self.assertIsInstance(exchange, RabbitExchange)
        self.assertEqual(messaging._session, exchange._session)
        self.assertEqual(exchange_name, exchange.exchange_name)

    @uses_rabbit_fixture
    def test_messaging_getQueue(self):
        exchange_name = factory.getRandomString()
        messaging = RabbitMessaging(exchange_name)
        queue = messaging.getQueue()
        self.assertIsInstance(queue, RabbitQueue)
        self.assertEqual(messaging._session, queue._session)
        self.assertEqual(exchange_name, queue.exchange_name)


class TestRabbitBase(TestCase):

    def test_rabbitbase_contains_session(self):
        exchange_name = factory.getRandomString()
        rabbitbase = RabbitBase(RabbitSession(), exchange_name)
        self.assertIsInstance(rabbitbase._session, RabbitSession)

    def test_base_has_exchange_name(self):
        exchange_name = factory.getRandomString()
        rabbitbase = RabbitBase(RabbitSession(), exchange_name)
        self.assertEqual(exchange_name, rabbitbase.exchange_name)

    @uses_rabbit_fixture
    def test_base_channel(self):
        rabbitbase = RabbitBase(RabbitSession(), factory.getRandomString())
        # Referencing the channel property causes an open channel to be
        # created.
        channel = rabbitbase.channel
        self.assertTrue(channel.is_open)
        self.assertIsNotNone(rabbitbase._session._connection)
        # The same channel is returned every time.
        self.assertIs(channel, rabbitbase.channel)

    @uses_rabbit_fixture
    def test_base_channel_creates_exchange(self):
        exchange_name = factory.getRandomString()
        rabbitbase = RabbitBase(RabbitSession(), exchange_name)
        rabbitbase.channel
        self.assertIn(exchange_name, run_rabbit_command('list_exchanges'))


class TestRabbitExchange(TestCase):

    def basic_get(self, channel, queue_name, timeout):
        endtime = time.time() + timeout
        while True:
            message = channel.basic_get(queue_name)
            if message is None:
                if time.time() > endtime:
                    self.fail('Cannot get message.')
                time.sleep(0.1)
            else:
                return message

    @uses_rabbit_fixture
    def test_exchange_publish(self):
        exchange_name = factory.getRandomString()
        message_content = factory.getRandomString()
        exchange = RabbitExchange(RabbitSession(), exchange_name)

        channel = RabbitBase(RabbitSession(), exchange_name).channel
        queue_name = channel.queue_declare(auto_delete=True)[0]
        channel.queue_bind(exchange=exchange_name, queue=queue_name)
        exchange.publish(message_content)
        message = self.basic_get(channel, queue_name, timeout=2)
        self.assertEqual(message_content, message.body)


class TestRabbitQueue(TestCase):

    @uses_rabbit_fixture
    def test_rabbit_queue_binds_queue(self):
        exchange_name = factory.getRandomString()
        message_content = factory.getRandomString()
        queue = RabbitQueue(RabbitSession(), exchange_name)

        # Publish to queue.name.
        base = RabbitBase(RabbitSession(), exchange_name)
        channel = base.channel
        msg = amqp.Message(message_content)
        channel.basic_publish(
            exchange=exchange_name, routing_key='', msg=msg)
        message = channel.basic_get(queue.name)
        self.assertEqual(message_content, message.body)
