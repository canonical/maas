# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Common RPC classes and utilties."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "Client",
    "Identify",
    "RPCProtocol",
]

from provisioningserver.rpc.interfaces import IConnection
from provisioningserver.utils.twisted import asynchronous
from twisted.internet.defer import Deferred
from twisted.protocols import amp


class Identify(amp.Command):
    """Request the identity of the remote side, e.g. its UUID.

    :since: 1.5
    """

    response = [(b"ident", amp.Unicode())]


class Client:
    """Wrapper around an :class:`amp.AMP` instance.

    Limits the API to a subset of the behaviour of :class:`amp.AMP`'s,
    with alterations to make it suitable for use from a thread outside
    of the reactor.
    """

    def __init__(self, conn):
        super(Client, self).__init__()
        assert IConnection.providedBy(conn), (
            "%r does not provide IConnection" % (conn,))
        self._conn = conn

    @property
    def ident(self):
        """Something that identifies the far end of the connection."""
        return self._conn.ident

    @asynchronous
    def __call__(self, cmd, *args, **kwargs):
        """Call a remote RPC method.

        This is how the client is normally used.

        :note:
            Though the call signature shows positional arguments, their use is
            an error. They're in the signature is so this method can detect
            them and provide a better error message than that from Python.
            Python's error message when arguments don't match the call's
            signature is not great at best, but it also makes it hard to
            figure out the receiver when the `TypeError` is raised in a
            different stack from the caller's, e.g. when calling into the
            Twisted reactor from a thread.

        :param cmd: The `amp.Command` child class representing the remote
            method to be invoked.
        :param kwargs: Any parameters to the remote method.  Only keyword
            arguments are accepted.
        :return: A deferred result.  Call its `wait` method (with a timeout
            in seconds) to block on the call's completion.
        """
        if len(args) != 0:
            receiver_name = "%s.%s" % (
                self.__module__, self.__class__.__name__)
            raise TypeError(
                "%s called with %d positional arguments, %r, but positional "
                "arguments are not supported. Usage: client(command, arg1="
                "value1, ...)" % (receiver_name, len(args), args))

        return self._conn.callRemote(cmd, **kwargs)

    @asynchronous
    def getHostCertificate(self):
        return self._conn.hostCertificate

    @asynchronous
    def getPeerCertificate(self):
        return self._conn.peerCertificate

    @asynchronous
    def isSecure(self):
        return self._conn.peerCertificate is not None

    def __eq__(self, other):
        return type(other) is type(self) and other._conn is self._conn

    def __hash__(self):
        return hash(self._conn)


class RPCProtocol(amp.AMP, object):
    """A specialisation of `amp.AMP`.

    It's hard to track exactly when an `amp.AMP` protocol is connected to its
    transport, or disconnected, from the "outside". It's necessary to subclass
    and override `connectionMade` and `connectionLost` and signal from there,
    which is what this class does.

    :ivar onConnectionMade: A `Deferred` that fires when `connectionMade` has
        been called, i.e. this protocol is now connected.
    :ivar onConnectionLost: A `Deferred` that fires when `connectionLost` has
        been called, i.e. this protocol is no longer connected.
    """

    def __init__(self):
        super(RPCProtocol, self).__init__()
        self.onConnectionMade = Deferred()
        self.onConnectionLost = Deferred()

    def connectionMade(self):
        super(RPCProtocol, self).connectionMade()
        self.onConnectionMade.callback(None)

    def connectionLost(self, reason):
        super(RPCProtocol, self).connectionLost(reason)
        self.onConnectionLost.callback(None)
