# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `osystems` module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from collections import (
    Counter,
    Iterator,
    )

from maasserver import eventloop
from maasserver.clusterrpc.osystems import gen_all_known_operating_systems
from maasserver.rpc import getAllClients
from maasserver.rpc.testing.fixtures import ClusterRPCFixture
from maasserver.testing.eventloop import RegionEventLoopFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import (
    AfterPreprocessing,
    AllMatch,
    Equals,
    HasLength,
    IsInstance,
    Not,
    )
from twisted.internet.defer import succeed


class TestGenAllKnownOperatingSystems(MAASServerTestCase):
    """Tests for `gen_all_known_operating_systems`."""

    def fake_cluster_rpc(self):
        # Set-up the event-loop with only the RPC service running, then
        # layer on a fake cluster RPC implementation.
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.addCleanup(lambda: eventloop.reset().wait(5))
        eventloop.start().wait(5)
        self.useFixture(ClusterRPCFixture())

    def test_yields_oses_known_to_a_cluster(self):
        # The operating systems known to a single node are returned.
        factory.make_node_group().accept()
        self.fake_cluster_rpc()
        osystems = gen_all_known_operating_systems()
        self.assertIsInstance(osystems, Iterator)
        osystems = list(osystems)
        self.assertThat(osystems, Not(HasLength(0)))
        self.assertThat(osystems, AllMatch(IsInstance(dict)))

    def test_yields_oses_known_to_multiple_clusters(self):
        factory.make_node_group().accept()
        factory.make_node_group().accept()
        self.fake_cluster_rpc()
        osystems = gen_all_known_operating_systems()
        self.assertIsInstance(osystems, Iterator)
        osystems = list(osystems)
        self.assertThat(osystems, Not(HasLength(0)))
        self.assertThat(osystems, AllMatch(IsInstance(dict)))

    def test_only_yields_os_once(self):
        # Duplicate OSes that exactly match are suppressed. Typically
        # every cluster will have several (or all) OSes in common.
        factory.make_node_group().accept()
        factory.make_node_group().accept()
        self.fake_cluster_rpc()
        counter = Counter(
            osystem["name"] for osystem in
            gen_all_known_operating_systems())

        def get_count(item):
            name, count = item
            return count

        self.assertThat(
            counter.viewitems(), AllMatch(
                AfterPreprocessing(get_count, Equals(1))))

    def test_os_data_is_passed_through_unmolested(self):
        factory.make_node_group().accept()
        self.fake_cluster_rpc()
        example = {
            "osystems": [
                {
                    "name": factory.make_name("name"),
                    "foo": factory.make_name("foo"),
                    "bar": factory.make_name("bar"),
                },
            ],
        }
        for client in getAllClients().wait():
            callRemote = self.patch(client._conn, "callRemote")
            callRemote.return_value = succeed(example)

        self.assertItemsEqual(
            example["osystems"], gen_all_known_operating_systems())

    def test_ignores_failures_when_talking_to_clusters(self):
        factory.make_node_group().accept()
        factory.make_node_group().accept()
        factory.make_node_group().accept()
        self.fake_cluster_rpc()

        clients = getAllClients().wait()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            if index == 0:
                # The first client found returns dummy OS information which
                # includes the cluster's UUID (client.ident).
                example = {"osystems": [{"name": client.ident}]}
                callRemote.return_value = succeed(example)
            else:
                # All clients but the first raise an exception.
                callRemote.side_effect = ZeroDivisionError()

        # The only OS information to get through is that from the first. The
        # failures arising from communicating with the other clusters have all
        # been suppressed.
        self.assertItemsEqual(
            [{"name": clients[0].ident}],
            gen_all_known_operating_systems())
