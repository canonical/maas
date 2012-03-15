# Copyright 2005-2011 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.amqpclient`."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from unittest import skip

from provisioningserver.amqpclient import AMQFactory
from testtools import TestCase
from testtools.deferredruntest import (
    AsynchronousDeferredRunTestForBrokenTwisted,
    )
from twisted.internet import reactor
from twisted.internet.defer import (
    Deferred,
    DeferredQueue,
    inlineCallbacks,
    )
from txamqp.client import Closed


class QueueWrapper(object):
    """
    Wrap a queue to have notifications when get is called on this particular
    queue.
    """

    def __init__(self, queue):
        self._real_queue_get = queue.get
        self.event_queue = DeferredQueue()
        queue.get = self.get

    def get(self, timeout=None):
        self.event_queue.put(None)
        return self._real_queue_get(timeout)


class AMQTest(TestCase):

    run_tests_with = AsynchronousDeferredRunTestForBrokenTwisted.make_factory(
        timeout=5)

    VHOST = "/"
    USER = "guest"
    PASSWORD = "guest"

    @property
    def rabbit(self):
        """A set-up `rabbitfixture.server.RabbitServer` instance.

        This is a compatibility shim in case we ever revert to using
        `testresources`_ here. At the moment the `RabbitServer` is being
        managed by `package-level fixture hooks`_ that nose recognizes.

        .. testresources_:
          https://launchpad.net/testresources

        .. package-level fixture hooks_:
          http://readthedocs.org/docs/nose/en/latest/writing_tests.html

        """
        from provisioningserver import tests
        return tests.get_rabbit()

    @skip(
        "RabbitMQ is not yet a required component "
        "of a running MAAS installation.")
    def setUp(self):
        """
        At each run, we delete the test vhost and recreate it, to be sure to be
        in a clean environment.
        """
        super(AMQTest, self).setUp()
        self.queues = set()
        self.exchanges = set()
        self.connected_deferred = Deferred()

        self.factory = AMQFactory(self.USER, self.PASSWORD, self.VHOST,
            self.amq_connected, self.amq_disconnected, self.amq_failed)
        self.factory.initialDelay = 2.0
        self.connector = reactor.connectTCP(
            self.rabbit.config.hostname, self.rabbit.config.port,
            self.factory)
        return self.connected_deferred

    @inlineCallbacks
    def tearDown(self):
        # XXX: Moving this up here to silence a nigh-on inexplicable error
        # that occurs when it's at the bottom of the function.
        self.factory.stopTrying()
        self.connector.disconnect()
        super(AMQTest, self).tearDown()

        # XXX: This is only safe because we tear down the whole server.
        #      We can't run this after the tearDown above, because the
        #      fixture is gone.
        return

        self.connected_deferred = Deferred()
        factory = AMQFactory(self.USER, self.PASSWORD, self.VHOST,
            self.amq_connected, self.amq_disconnected, self.amq_failed)
        connector = reactor.connectTCP(
            self.rabbit.config.hostname, self.rabbit.config.port, factory)
        yield self.connected_deferred
        channel_id = 1
        for queue in self.queues:
            try:
                yield self.channel.queue_delete(queue=queue)
            except Closed:
                channel_id += 1
                self.channel = yield self.client.channel(channel_id)
                yield self.channel.channel_open()
        for exchange in self.exchanges:
            try:
                yield self.channel.exchange_delete(exchange=exchange)
            except Closed:
                channel_id += 1
                self.channel = yield self.client.channel(channel_id)
                yield self.channel.channel_open()
        factory.stopTrying()
        connector.disconnect()

    def amq_connected(self, client_and_channel):
        """
        Save the channel and client, and fire C{self.connected_deferred}.

        This is the connected_callback that's pased to the L{AMQFactory}.
        """
        client, channel = client_and_channel
        self.real_queue_declare = channel.queue_declare
        channel.queue_declare = self.queue_declare
        self.real_exchange_declare = channel.exchange_declare
        channel.exchange_declare = self.exchange_declare
        self.channel = channel
        self.client = client
        self.connected_deferred.callback(None)

    def amq_disconnected(self):
        """
        This is the disconnected_callback that's passed to the L{AMQFactory}.
        """

    def amq_failed(self, connector_and_reason):
        """
        This is the failed_callback that's passed to the L{AMQFactory}.
        """
        connector, reason = connector_and_reason
        self.connected_deferred.errback(reason)

    def queue_declare(self, queue, **kwargs):
        """
        Keep track of the queue declaration, and forward to the real
        queue_declare function.
        """
        self.queues.add(queue)
        return self.real_queue_declare(queue=queue, **kwargs)

    def exchange_declare(self, exchange, **kwargs):
        """
        Keep track of the exchange declaration, and forward to the real
        exchange_declare function.
        """
        self.exchanges.add(exchange)
        return self.real_exchange_declare(exchange=exchange, **kwargs)
