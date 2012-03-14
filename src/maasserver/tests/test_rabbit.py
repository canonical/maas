# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Rabbit messaging tests."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []


from amqplib import client_0_8 as amqp
from fixtures import MonkeyPatch
from maasserver.rabbit import (
    RabbitBase,
    RabbitExchange,
    RabbitMessaging,
    RabbitQueue,
    RabbitSession,
    )
from maasserver.testing.factory import factory
from maastesting.testcase import TestCase
from rabbitfixture.server import RabbitServer


class RabbitTestCase(TestCase):

    def setUp(self):
        super(RabbitTestCase, self).setUp()
        self.rabbit_server = self.useFixture(RabbitServer())
        self.rabbit_env = self.rabbit_server.runner.environment
        patch = MonkeyPatch(
            "maasserver.rabbit.connect", self.rabbit_env.get_connection)
        self.useFixture(patch)

    def get_command_output(self, command):
        # Returns the output of the given rabbit command.
        return self.rabbit_env.rabbitctl(str(command))[0]


class TestRabbitSession(RabbitTestCase):

    def test_session_connection(self):
        session = RabbitSession()
        # Referencing the connection property causes a connection to be
        # created.
        connection = session.connection
        self.assertIsNotNone(session._connection)
        # The same connection is returned every time.
        self.assertIs(connection, session.connection)

    def test_session_disconnect(self):
        session = RabbitSession()
        session.disconnect()
        self.assertIsNone(session._connection)


class TestRabbitMessaging(RabbitTestCase):

    def test_messaging_getExchange(self):
        exchange_name = factory.getRandomString()
        messaging = RabbitMessaging(exchange_name)
        exchange = messaging.getExchange()
        self.assertIsInstance(exchange, RabbitExchange)
        self.assertEqual(messaging._session, exchange._session)
        self.assertEqual(exchange_name, exchange.exchange_name)

    def test_messaging_getQueue(self):
        exchange_name = factory.getRandomString()
        messaging = RabbitMessaging(exchange_name)
        queue = messaging.getQueue()
        self.assertIsInstance(queue, RabbitQueue)
        self.assertEqual(messaging._session, queue._session)
        self.assertEqual(exchange_name, queue.exchange_name)


class TestRabbitBase(RabbitTestCase):

    def test_rabbitbase_contains_session(self):
        exchange_name = factory.getRandomString()
        rabbitbase = RabbitBase(RabbitSession(), exchange_name)
        self.assertIsInstance(rabbitbase._session, RabbitSession)

    def test_base_has_exchange_name(self):
        exchange_name = factory.getRandomString()
        rabbitbase = RabbitBase(RabbitSession(), exchange_name)
        self.assertEqual(exchange_name, rabbitbase.exchange_name)

    def test_base_channel(self):
        rabbitbase = RabbitBase(RabbitSession(), factory.getRandomString())
        # Referencing the channel property causes an open channel to be
        # created.
        channel = rabbitbase.channel
        self.assertTrue(channel.is_open)
        self.assertIsNotNone(rabbitbase._session._connection)
        # The same channel is returned every time.
        self.assertIs(channel, rabbitbase.channel)

    def test_base_channel_creates_exchange(self):
        exchange_name = factory.getRandomString()
        rabbitbase = RabbitBase(RabbitSession(), exchange_name)
        rabbitbase.channel
        self.assertIn(
            exchange_name,
            self.get_command_output('list_exchanges'))


class TestRabbitExchange(RabbitTestCase):

    def test_exchange_publish(self):
        exchange_name = factory.getRandomString()
        message_content = factory.getRandomString()
        exchange = RabbitExchange(RabbitSession(), exchange_name)

        channel = RabbitBase(RabbitSession(), exchange_name).channel
        queue_name = channel.queue_declare(auto_delete=True)[0]
        channel.queue_bind(exchange=exchange_name, queue=queue_name)
        exchange.publish(message_content)
        message = channel.basic_get(queue_name)
        self.assertEqual(message_content, message.body)


class TestRabbitQueue(RabbitTestCase):

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
