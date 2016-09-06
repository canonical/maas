# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Discovery model."""

__all__ = []

from maasserver.dbviews import register_view
from maasserver.models import Discovery
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import (
    Equals,
    Is,
)


class TestDiscoveryModel(MAASServerTestCase):

    def setUp(self):
        super().setUp()
        register_view("maasserver_discovery")

    def test_mac_organization(self):
        discovery = factory.make_Discovery(mac_address="48:51:b7:00:00:00")
        self.assertThat(discovery.mac_organization, Equals("Intel Corporate"))

    def test__ignores_duplicate_macs(self):
        rack1 = factory.make_RackController()
        rack2 = factory.make_RackController()
        iface1 = factory.make_Interface(node=rack1)
        iface2 = factory.make_Interface(node=rack2)
        # Simulate a single device being observed from two different rack
        # interfaces.
        d1 = factory.make_Discovery(interface=iface1)
        factory.make_Discovery(
            interface=iface2, mac_address=d1.mac_address, ip=d1.ip)
        # ... the Discovery view should only display one entry.
        self.assertThat(Discovery.objects.count(), Equals(1))

    def test__query_by_unknown_mac(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        discovery = factory.make_Discovery(interface=iface)
        self.assertThat(Discovery.objects.by_unknown_mac().count(), Equals(1))
        factory.make_Interface(mac_address=discovery.mac_address)
        # Now that we have a known interface with the same MAC, the discovery
        # should disappear from this query.
        self.assertThat(Discovery.objects.by_unknown_mac().count(), Equals(0))

    def test__query_by_unknown_ip(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        discovery = factory.make_Discovery(interface=iface, ip="10.0.0.1")
        self.assertThat(Discovery.objects.by_unknown_ip().count(), Equals(1))
        factory.make_StaticIPAddress(ip=discovery.ip, cidr="10.0.0.0/8")
        # Now that we have a known IP address that matches, the discovery
        # should disappear from this query.
        self.assertThat(Discovery.objects.by_unknown_ip().count(), Equals(0))

    def test__query_by_unknown_ip_and_mac__known_ip(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        discovery = factory.make_Discovery(interface=iface, ip="10.0.0.1")
        self.assertThat(
            Discovery.objects.by_unknown_ip_and_mac().count(), Equals(1))
        factory.make_StaticIPAddress(ip=discovery.ip, cidr="10.0.0.0/8")
        # Known IP address, unexpected MAC.
        self.assertThat(
            Discovery.objects.by_unknown_ip_and_mac().count(), Equals(0))

    def test__query_by_unknown_ip_and_mac__known_mac(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        discovery = factory.make_Discovery(interface=iface)
        self.assertThat(
            Discovery.objects.by_unknown_ip_and_mac().count(), Equals(1))
        # Known MAC, unknown IP.
        factory.make_Interface(mac_address=discovery.mac_address)
        self.assertThat(
            Discovery.objects.by_unknown_ip_and_mac().count(), Equals(0))

    def test__does_not_fail_if_cannot_find_subnet(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        factory.make_Discovery(interface=iface, ip="10.0.0.1")
        self.assertThat(Discovery.objects.first().subnet, Is(None))

    def test__associates_known_subnet(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        subnet = factory.make_Subnet(cidr="10.0.0.0/8", vlan=iface.vlan)
        factory.make_Discovery(interface=iface, ip="10.0.0.1")
        self.assertThat(Discovery.objects.first().subnet, Equals(subnet))

    def test__associates_best_subnet(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        # Seems unlikely, but we'll test it anyway. ;-)
        subnet = factory.make_Subnet(cidr="10.0.0.0/24", vlan=iface.vlan)
        factory.make_Subnet(cidr="10.0.0.0/8", vlan=iface.vlan)
        factory.make_Discovery(interface=iface, ip="10.0.0.1")
        self.assertThat(Discovery.objects.first().subnet, Equals(subnet))
        self.assertThat(Discovery.objects.count(), Equals(1))
