# Copyright 2005-2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for C{AMQFactory}."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from provisioningserver.amqpclient import AMQFactory
from provisioningserver.testing.amqpclient import AMQTest
from testtools import TestCase
from testtools.deferredruntest import flush_logged_errors
from twisted.internet.defer import Deferred
from txamqp.protocol import AMQChannel
from txamqp.queue import Closed
from txamqp.spec import Spec


class AMQFactoryTest(TestCase):

    def test_init(self):
        factory = AMQFactory("guest", "secret", "localhost", lambda x: None,
                             lambda: None, lambda x: None)
        self.assertEquals(factory.user, "guest")
        self.assertEquals(factory.password, "secret")
        self.assertEquals(factory.vhost, "localhost")
        self.assertTrue(isinstance(factory.spec, Spec))


class AMQFactoryConnectedTest(AMQTest):

    def test_connected_callback(self):
        self.assertTrue(isinstance(self.channel, AMQChannel))

    def test_disconnected_callback(self):
        d = Deferred()

        def disconnected():
            d.callback(None)

        self.factory.disconnected_callback = disconnected
        self.connector.disconnect()
        return d

    def test_reconnection(self):
        d = Deferred()

        def connected((client, channel)):
            self.assertTrue(isinstance(channel, AMQChannel))
            self.assertIsNot(channel, self.channel)
            d.callback(None)

        self.factory.connected_callback = connected
        self.factory.maxDelay = 0.01
        self.connector.disconnect()
        return d


class AMQClosingTest(AMQTest):
    """Tests the L{AMQFactory} when the connection is closing."""

    count = 0

    def amq_connected(self, (client, channel)):
        super(AMQClosingTest, self).amq_connected((client, channel))
        if not self.count:
            self.count += 1
            raise Closed()

    def test_catch_closed(self):
        """
        This test ensures that L{Closed} exception raised by C{amq_connected}
        is swallowed by L{AMQFactory}.
        """
        errors = flush_logged_errors()
        self.assertEquals(len(errors), 0)


# TODO: Get testresources working with nose. These tests are way too slow
# because testresources does not work with nose. Disabling for now until we
# have testresources support. Assigning None to the test classes seems to be
# the only sure-fire way of preventing all test collectors from finding them
# and satisfying lint tools at the same time.
AMQFactoryTest = None
AMQFactoryConnectedTest = None
AMQClosingTest = None
