# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.cobblerclient`."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from provisioningserver.cobblerclient import (
    CobblerXMLRPCProxy,
    tilde_to_None,
    )
from testtools import TestCase
from twisted.test.proto_helpers import MemoryReactor


class TestRepairingCobblerResponses(TestCase):
    """See `tilde_to_None`."""

    def test_tilde_to_None(self):
        self.assertIsNone(tilde_to_None("~"))

    def test_tilde_to_None_list(self):
        self.assertEqual(
            [1, 2, 3, None, 5],
            tilde_to_None([1, 2, 3, "~", 5]))

    def test_tilde_to_None_nested_list(self):
        self.assertEqual(
            [1, 2, [3, None], 5],
            tilde_to_None([1, 2, [3, "~"], 5]))

    def test_tilde_to_None_dict(self):
        self.assertEqual(
            {"one": 1, "two": None},
            tilde_to_None({"one": 1, "two": "~"}))

    def test_tilde_to_None_nested_dict(self):
        self.assertEqual(
            {"one": 1, "two": {"three": None}},
            tilde_to_None({"one": 1, "two": {"three": "~"}}))

    def test_tilde_to_None_nested_mixed(self):
        self.assertEqual(
            {"one": 1, "two": [3, 4, None]},
            tilde_to_None({"one": 1, "two": [3, 4, "~"]}))

    def test_CobblerXMLRPCProxy(self):
        reactor = MemoryReactor()
        proxy = CobblerXMLRPCProxy(
            "http://localhost:1234/nowhere", reactor=reactor)
        d = proxy.callRemote("cobble", 1, 2, 3)
        # A connection has been initiated.
        self.assertEqual(1, len(reactor.tcpClients))
        [client] = reactor.tcpClients
        self.assertEqual("localhost", client[0])
        self.assertEqual(1234, client[1])
        # A "broken" response from Cobbler is "repaired".
        d.callback([1, 2, "~"])
        self.assertEqual([1, 2, None], d.result)
