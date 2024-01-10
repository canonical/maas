# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.regiondservices.syslog`."""


from netaddr import IPAddress
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from maasserver.models.config import Config
from maasserver.regiondservices import syslog
from maasserver.service_monitor import service_monitor
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for
from maastesting.fixtures import MAASRootFixture
from maastesting.testcase import MAASTestCase
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.utils.testing import MAASIDFixture

wait_for_reactor = wait_for()


def make_region_rack_with_address(space):
    region = factory.make_RegionRackController()
    iface = factory.make_Interface(node=region)
    cidr4 = factory.make_ipv4_network(24)
    subnet4 = factory.make_Subnet(space=space, cidr=cidr4)
    cidr6 = factory.make_ipv6_network(64)
    subnet6 = factory.make_Subnet(space=space, cidr=cidr6)
    sip4 = factory.make_StaticIPAddress(interface=iface, subnet=subnet4)
    sip6 = factory.make_StaticIPAddress(interface=iface, subnet=subnet6)
    return region, sip4, sip6


class TestRegionSyslogService_Basic(MAASTestCase):
    """Basic tests for `RegionSyslogService`."""

    def test_service_uses__tryUpdate_as_periodic_function(self):
        service = syslog.RegionSyslogService(reactor)
        self.assertEqual((service._tryUpdate, (), {}), service.call)

    def test_service_iterates_every_30_seconds(self):
        service = syslog.RegionSyslogService(reactor)
        self.assertEqual(30.0, service.step)


class TestRegionSyslogService(MAASTransactionServerTestCase):
    """Tests for `RegionSyslogService`."""

    def setUp(self):
        super().setUp()
        self.useFixture(MAASRootFixture())

    @transactional
    def make_example_configuration(self):
        # Set the syslog port.
        port = factory.pick_port()
        Config.objects.set_config("maas_syslog_port", port)
        # Populate the database with example peers.
        space = factory.make_Space()
        region, addr4, addr6 = make_region_rack_with_address(space)
        self.useFixture(MAASIDFixture(region.system_id))
        peer1, addr1_4, addr1_6 = make_region_rack_with_address(space)
        peer2, addr2_4, addr2_6 = make_region_rack_with_address(space)
        # Return the servers and all possible peer IP addresses.
        return (
            port,
            [
                (
                    peer1,
                    sorted([IPAddress(addr1_4.ip), IPAddress(addr1_6.ip)])[0],
                ),
                (
                    peer2,
                    sorted([IPAddress(addr2_4.ip), IPAddress(addr2_6.ip)])[0],
                ),
            ],
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_tryUpdate_updates_syslog_server(self):
        service = syslog.RegionSyslogService(reactor)
        port, peers = yield deferToDatabase(self.make_example_configuration)
        write_config = self.patch_autospec(syslog, "write_config")
        restartService = self.patch_autospec(service_monitor, "restartService")
        yield service._tryUpdate()
        self.assertEqual(write_config.call_count, 1)
        self.assertEqual(
            write_config.call_args.kwargs,
            {"port": port, "promtail_port": None},
        )
        write_local, called_peers = write_config.call_args.args
        self.assertTrue(write_local)
        self.assertCountEqual(
            called_peers,
            [
                {"ip": service._formatIP(ip), "name": node.hostname}
                for node, ip in peers
            ],
        )

        restartService.assert_called_once_with("syslog_region")
        write_config.reset_mock()
        restartService.reset_mock()
        # If the configuration has not changed then a second call to
        # `_tryUpdate` does not result in another call to `write_config`.
        yield service._tryUpdate()
        write_config.assert_not_called()
        restartService.assert_not_called()


class TestRegionSyslogService_Errors(MAASTransactionServerTestCase):
    """Tests for error handing in `RegionSyslogService`."""

    scenarios = (
        ("_getConfiguration", dict(method="_getConfiguration")),
        ("_maybeApplyConfiguration", dict(method="_maybeApplyConfiguration")),
        ("_applyConfiguration", dict(method="_applyConfiguration")),
        ("_configurationApplied", dict(method="_configurationApplied")),
    )

    @wait_for_reactor
    @inlineCallbacks
    def test_tryUpdate_logs_errors_from_broken_method(self):
        service = syslog.RegionSyslogService(reactor)
        broken_method = self.patch_autospec(service, self.method)
        broken_method.side_effect = factory.make_exception()

        # Don't actually write the file.
        self.patch_autospec(syslog, "write_config")

        # Ensure that we never actually execute against systemd.
        self.patch_autospec(service_monitor, "restartService")

        with TwistedLoggerFixture() as logger:
            yield service._tryUpdate()

        self.maxDiff = None
        self.assertIn(
            "Failed to update syslog configuration.\nTraceback (most recent call last):",
            logger.output,
        )
        self.assertIn(str(broken_method.side_effect), logger.output)


class TestRegionSyslogService_Database(MAASServerTestCase):
    """Database tests for `RegionSyslogService`."""

    def test_getConfiguration_returns_configuration_object(self):
        service = syslog.RegionSyslogService(reactor)

        # Put all addresses in the same space so they're mutually routable.
        space = factory.make_Space()
        # Populate the database with "this" region rack and an example peer.
        region_rack, _, _ = make_region_rack_with_address(space)
        self.useFixture(MAASIDFixture(region_rack.system_id))
        peer, addr4, addr6 = make_region_rack_with_address(space)

        observed = service._getConfiguration()
        self.assertIsInstance(observed, syslog._Configuration)

        self.assertEqual(
            observed.peers, {(peer.hostname, IPAddress(addr4.ip))}
        )
