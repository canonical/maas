# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for common RPC code."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import re

from maastesting.matchers import (
    IsFiredDeferred,
    IsUnfiredDeferred,
    MockCalledOnceWith,
    )
from maastesting.testcase import MAASTestCase
from mock import (
    create_autospec,
    sentinel,
    )
from provisioningserver.rpc import common
from provisioningserver.rpc.testing.doubles import DummyConnection
from testtools import ExpectedException
from testtools.matchers import (
    Equals,
    Is,
    IsInstance,
    Not,
    )
from twisted.internet.protocol import connectionDone
from twisted.protocols import amp
from twisted.test.proto_helpers import StringTransport


class TestClient(MAASTestCase):

    def test_init(self):
        conn = DummyConnection()
        client = common.Client(conn)
        self.assertThat(client._conn, Is(conn))

    def make_connection_and_client(self):
        conn = create_autospec(common.RPCProtocol())
        client = common.Client(conn)
        return conn, client

    def test_ident(self):
        conn, client = self.make_connection_and_client()
        conn.ident = self.getUniqueString()
        self.assertThat(client.ident, Equals(conn.ident))

    def test_call(self):
        conn, client = self.make_connection_and_client()
        conn.callRemote.return_value = sentinel.response
        response = client(sentinel.command, foo=sentinel.foo, bar=sentinel.bar)
        self.assertThat(response, Is(sentinel.response))
        self.assertThat(conn.callRemote, MockCalledOnceWith(
            sentinel.command, foo=sentinel.foo, bar=sentinel.bar))

    def test_call_with_keyword_arguments_raises_useful_error(self):
        conn = DummyConnection()
        client = common.Client(conn)
        expected_message = re.escape(
            "provisioningserver.rpc.common.Client called with 3 positional "
            "arguments, (1, 2, 3), but positional arguments are not "
            "supported. Usage: client(command, arg1=value1, ...)")
        with ExpectedException(TypeError, expected_message):
            client(sentinel.command, 1, 2, 3)

    def test_getHostCertificate(self):
        conn, client = self.make_connection_and_client()
        conn.hostCertificate = sentinel.hostCertificate
        self.assertThat(
            client.getHostCertificate(),
            Is(sentinel.hostCertificate))

    def test_getPeerCertificate(self):
        conn, client = self.make_connection_and_client()
        conn.peerCertificate = sentinel.peerCertificate
        self.assertThat(
            client.getPeerCertificate(),
            Is(sentinel.peerCertificate))

    def test_isSecure(self):
        conn, client = self.make_connection_and_client()
        conn.peerCertificate = sentinel.peerCertificate
        self.assertTrue(client.isSecure())

    def test_isSecure_not(self):
        conn, client = self.make_connection_and_client()
        conn.peerCertificate = None
        self.assertFalse(client.isSecure())

    def test___eq__(self):
        conn, client = self.make_connection_and_client()
        self.assertThat(client, Equals(client))
        client_for_same_connection = common.Client(conn)
        self.assertThat(client, Equals(client_for_same_connection))
        _, client_for_another_connection = self.make_connection_and_client()
        self.assertThat(client, Not(Equals(client_for_another_connection)))

    def test___hash__(self):
        conn, client = self.make_connection_and_client()
        # The hash of a common.Client object is that of its connection.
        self.assertThat(hash(conn), Equals(hash(client)))


class TestRPCProtocol(MAASTestCase):

    def test_init(self):
        protocol = common.RPCProtocol()
        self.assertThat(protocol.onConnectionMade, IsUnfiredDeferred())
        self.assertThat(protocol.onConnectionLost, IsUnfiredDeferred())
        self.assertThat(protocol, IsInstance(amp.AMP))

    def test_onConnectionMade_fires_when_connection_is_made(self):
        protocol = common.RPCProtocol()
        protocol.connectionMade()
        self.assertThat(protocol.onConnectionMade, IsFiredDeferred())

    def test_onConnectionLost_fires_when_connection_is_lost(self):
        protocol = common.RPCProtocol()
        protocol.makeConnection(StringTransport())
        protocol.connectionLost(connectionDone)
        self.assertThat(protocol.onConnectionLost, IsFiredDeferred())
