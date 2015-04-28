# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.pserv_services.neighbours`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from mock import ANY
from netaddr import (
    EUI,
    IPAddress,
)
from provisioningserver.pserv_services import neighbours
from provisioningserver.pserv_services.neighbours import NeighboursService
from provisioningserver.rpc.testing import TwistedLoggerFixture
from provisioningserver.utils.network import NeighboursProtocol
from testtools.matchers import (
    Equals,
    Is,
)
from twisted.internet.defer import inlineCallbacks

# The lines in the following output containing "lladdr" in the 4th column will
# become part of the parsed mappings. Other lines will be silently ignored.
example_ip_neigh_output = b"""\
fe80::9e97:26ff:fe94:f884 dev eth0 lladdr 9c:97:26:94:f8:84 router STALE
2001:8b0:1219:a75e:9e97::f884 dev eth0 lladdr 9c:97:26:94:f8:84 router STALE
172.16.1.254 dev eth1 lladdr 00:50:56:f9:33:8e STALE
192.168.1.254 dev eth0 lladdr 9c:97:26:94:f8:84 STALE
172.16.1.1 dev eth1 lladdr 00:50:56:c0:00:01 STALE
172.16.1.1 dev eth1 lladdr 00:50:56:c0:00:02 STALE
10.0.3.166 dev lxcbr0 lladdr 00:16:3e:da:8b:9e STALE
10.0.3.167 dev lxcbr0 lladdr 00:16:3e:da:8b:9e STALE
10.155.0.4 dev wlan0  FAILED
2.2.2.2 dev wlan0  INCOMPLETE
"""

example_ip_neigh_mappings = (
    NeighboursProtocol.collateNeighbours(
        NeighboursProtocol.parseOutput(
            example_ip_neigh_output.splitlines())))


class TestNeighboursService(MAASTestCase):
    """Tests for `NeighboursService`."""

    def setUp(self):
        super(TestNeighboursService, self).setUp()
        self.reactor = self.patch(neighbours, "reactor")

    def test__update_spawns_process(self):
        NeighboursService().update()
        self.assertThat(
            self.reactor.spawnProcess,
            MockCalledOnceWith(ANY, b"ip", (b"ip", b"neigh")))

    def test__find_ip_addresses(self):
        service = NeighboursService()
        service.update().callback(example_ip_neigh_mappings)
        # Multiple IP addresses or MAC addresses can be returned.
        self.assertThat(
            service.find_ip_addresses(EUI("00:50:56:c0:00:01")),
            Equals({IPAddress("172.16.1.1")}))
        self.assertThat(
            service.find_ip_addresses(EUI("00:16:3e:da:8b:9e")),
            Equals({IPAddress("10.0.3.166"), IPAddress("10.0.3.167")}))
        # Some addresses will yield empty results.
        self.assertThat(
            service.find_ip_addresses(EUI("12:34:56:78:90:ab")), Equals(set()))

    def test__find_ip_address(self):
        service = NeighboursService()
        service.update().callback(example_ip_neigh_mappings)
        # A single IP address or MAC address will be returned.
        self.assertThat(
            service.find_ip_address(EUI("00:50:56:c0:00:01")),
            Equals(IPAddress("172.16.1.1")))
        self.assertThat(
            service.find_ip_address(EUI("00:16:3e:da:8b:9e")),
            Equals(IPAddress("10.0.3.166")))
        # Some addresses will yield None.
        self.assertThat(
            service.find_ip_address(EUI("12:34:56:78:90:ab")), Is(None))

    def test__find_mac_addresses(self):
        service = NeighboursService()
        service.update().callback(example_ip_neigh_mappings)
        # Multiple IP addresses or MAC addresses can be returned.
        self.assertThat(
            service.find_mac_addresses(IPAddress("172.16.1.1")),
            Equals({EUI("00:50:56:c0:00:01"), EUI("00:50:56:c0:00:02")}))
        self.assertThat(
            service.find_mac_addresses(IPAddress("10.0.3.166")),
            Equals({EUI("00:16:3e:da:8b:9e")}))
        # Some addresses will yield empty results.
        self.assertThat(
            service.find_mac_addresses(IPAddress("1.2.3.4")), Equals(set()))

    def test__find_mac_address(self):
        service = NeighboursService()
        service.update().callback(example_ip_neigh_mappings)
        # A single IP address or MAC address will be returned.
        self.assertThat(
            service.find_mac_address(IPAddress("172.16.1.1")),
            Equals(EUI("00:50:56:c0:00:01")))
        self.assertThat(
            service.find_mac_address(IPAddress("10.0.3.166")),
            Equals(EUI("00:16:3e:da:8b:9e")))
        # Some addresses will yield None.
        self.assertThat(
            service.find_mac_address(IPAddress("1.2.3.4")), Is(None))


class TestNeighboursServiceLive(MAASTestCase):
    """Tests for `NeighboursService` with a reactor."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    @inlineCallbacks
    def test__update_catches_failures_spawning_the_process(self):
        non_executable = self.make_file()
        service = NeighboursService()
        service.command = (non_executable.encode("ascii"), )
        with TwistedLoggerFixture() as logger:
            yield service.update()
        self.assertDocTestMatches(
            """\
            `ip neigh` wrote to stderr (an error may be reported separately):
            ...
            OSError: [Errno 13] Permission denied
            ...
            Updating neighbours failed.
            Traceback (most recent call last):
            Failure: twisted.internet.error.ProcessTerminated: ...
            """,
            logger.output)

    @inlineCallbacks
    def test__update_catches_failures_coming_from_the_process(self):
        service = NeighboursService()
        service.command = (b"false", )
        with TwistedLoggerFixture() as logger:
            yield service.update()
        self.assertDocTestMatches(
            """\
            Updating neighbours failed.
            Traceback (most recent call last):
            Failure: twisted.internet.error.ProcessTerminated: ...
            """,
            logger.output)
