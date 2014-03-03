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

from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import (
    create_autospec,
    sentinel,
    )
from provisioningserver.rpc import common
from testtools.matchers import (
    Equals,
    Is,
    Not,
    )
from twisted.protocols import amp


class TestClient(MAASTestCase):

    def test_init(self):
        client = common.Client(sentinel.connection)
        self.assertThat(client._conn, Is(sentinel.connection))

    def make_connection_and_client(self):
        conn = create_autospec(amp.AMP())
        client = common.Client(conn)
        return conn, client

    def test_call(self):
        conn, client = self.make_connection_and_client()
        conn.callRemote.return_value = sentinel.response
        response = client(sentinel.command, foo=sentinel.foo, bar=sentinel.bar)
        self.assertThat(response, Is(sentinel.response))
        self.assertThat(conn.callRemote, MockCalledOnceWith(
            sentinel.command, foo=sentinel.foo, bar=sentinel.bar))

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
