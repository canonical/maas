# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

# Shamelessly cargo-culted from the txlongpoll source.

"""
Asynchronous client for AMQP using txAMQP.
"""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "AMQFactory",
    ]

import os.path

from twisted.internet.defer import maybeDeferred
from twisted.internet.protocol import ReconnectingClientFactory
from txamqp.client import TwistedDelegate
from txamqp.protocol import AMQClient
from txamqp.queue import Closed
from txamqp.spec import load as load_spec


class AMQClientWithCallback(AMQClient):
    """
    An C{AMQClient} that notifies connections with a callback.

    @ivar connected_callback: callback called when C{connectionMade} is
        called. It takes one argument, the protocol instance itself.
    """

    def __init__(self, connected_callback, *args, **kwargs):
        AMQClient.__init__(self, *args, **kwargs)
        self.connected_callback = connected_callback

    def connectionMade(self):
        AMQClient.connectionMade(self)
        self.connected_callback(self)


_base_dir = os.path.dirname(os.path.abspath(__file__))
AMQP0_8_SPEC = load_spec(os.path.join(_base_dir, "specs", "amqp0-8.xml"))
del _base_dir


class AMQFactory(ReconnectingClientFactory):
    """
    A C{ClientFactory} for C{AMQClient} protocol with reconnecting facilities.

    @ivar user: the user name to use to connect to the AMQP server.
    @ivar password: the corresponding password of the user.
    @ivar vhost: the AMQP vhost to create connections against.
    @ivar connected_callback: callback called when a successful connection
        happened. It takes one argument, the channel opened for the connection.
    @ivar disconnected_callback: callback called when a previously connected
        connection was lost. It takes no argument.
    """
    protocol = AMQClientWithCallback
    initialDelay = 0.01

    def __init__(self, user, password, vhost, connected_callback,
                 disconnected_callback, failed_callback, spec=None):
        self.user = user
        self.password = password
        self.vhost = vhost
        self.delegate = TwistedDelegate()
        if spec is None:
            spec = AMQP0_8_SPEC
        self.spec = spec
        self.connected_callback = connected_callback
        self.disconnected_callback = disconnected_callback
        self.failed_callback = failed_callback

    def buildProtocol(self, addr):
        """
        Create the protocol instance and returns it for letting Twisted
        connect it to the transport.

        @param addr: the attributed address, unused for now.
        """
        protocol = self.protocol(self.clientConnectionMade, self.delegate,
                                 self.vhost, spec=self.spec)
        protocol.factory = self
        return protocol

    def clientConnectionMade(self, client):
        """
        Called when a connection succeeds: login to the server, and open a
        channel against it.
        """
        self.resetDelay()

        def started(ignored):
            # We don't care about authenticate result as long as it succeeds
            return client.channel(1).addCallback(got_channel)

        def got_channel(channel):
            return channel.channel_open().addCallback(opened, channel)

        def opened(ignored, channel):
            deferred = maybeDeferred(
                self.connected_callback, (client, channel))
            deferred.addErrback(catch_closed)

        def catch_closed(failure):
            failure.trap(Closed)

        deferred = client.authenticate(self.user, self.password)
        return deferred.addCallback(started)

    def clientConnectionLost(self, connector, reason):
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)
        self.disconnected_callback()

    def clientConnectionFailed(self, connector, reason):
        ReconnectingClientFactory.clientConnectionFailed(
            self, connector, reason)
        self.failed_callback((connector, reason))
