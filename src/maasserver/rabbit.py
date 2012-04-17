# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Rabbit messaging."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "RabbitExchange",
    "RabbitQueue",
    "RabbitMessaging",
    "RabbitSession",
    ]


from errno import ECONNREFUSED
import socket
import threading

from amqplib import client_0_8 as amqp
from django.conf import settings
from maasserver.exceptions import NoRabbit


def connect():
    """Connect to AMQP."""
    try:
        return amqp.Connection(
            host=settings.RABBITMQ_HOST,
            userid=settings.RABBITMQ_USERID,
            password=settings.RABBITMQ_PASSWORD,
            virtual_host=settings.RABBITMQ_VIRTUAL_HOST,
            insist=False)
    except socket.error as e:
        if e.errno == ECONNREFUSED:
            raise NoRabbit(e.message)
        else:
            raise


class RabbitSession(threading.local):

    def __init__(self):
        self._connection = None

    @property
    def connection(self):
        if self._connection is None or self._connection.transport is None:
            self._connection = connect()
        return self._connection

    def disconnect(self):
        if self._connection is not None:
            try:
                self._connection.close()
            finally:
                self._connection = None


class RabbitMessaging:

    def __init__(self, exchange_name):
        self.exchange_name = exchange_name
        self._session = RabbitSession()

    def getExchange(self):
        return RabbitExchange(self._session, self.exchange_name)

    def getQueue(self):
        return RabbitQueue(self._session, self.exchange_name)


class RabbitBase(threading.local):

    def __init__(self, session, exchange_name):
        self.exchange_name = exchange_name
        self._session = session
        self._channel = None

    @property
    def channel(self):
        if self._channel is None or not self._channel.is_open:
            self._channel = self._session.connection.channel()
            self._channel.exchange_declare(
                self.exchange_name, type='fanout')
        return self._channel


class RabbitExchange(RabbitBase):

    def publish(self, message):
        msg = amqp.Message(message)
        # Publish to a 'fanout' exchange: routing_key is ''.
        self.channel.basic_publish(
            exchange=self.exchange_name, routing_key='', msg=msg)


class RabbitQueue(RabbitBase):

    def __init__(self, session, exchange_name):
        super(RabbitQueue, self).__init__(session, exchange_name)
        self.queue_name = self.channel.queue_declare(
            nowait=False, auto_delete=False,
            arguments={"x-expires": 300000})[0]
        self.channel.queue_bind(
            exchange=self.exchange_name, queue=self.queue_name)

    @property
    def name(self):
        return self.queue_name
