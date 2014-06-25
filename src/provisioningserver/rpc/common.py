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
    "Identify",
    "Client",
]

from provisioningserver.rpc.interfaces import IConnection
from provisioningserver.utils import asynchronous
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
    def __call__(self, cmd, **kwargs):
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
