# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Discovery model."""


from testtools.matchers import Equals, Is

from maasserver.models import Discovery
from maasserver.models import discovery as discovery_module
from maasserver.models import MDNS, Neighbour, RDNS
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import (
    DocTestMatches,
    IsNonEmptyString,
    Matches,
    MockCalledOnceWith,
    MockNotCalled,
)


class TestDiscoveryModel(MAASServerTestCase):
    def test_mac_organization(self):
        discovery = factory.make_Discovery(mac_address="48:51:b7:00:00:00")
        self.assertThat(discovery.mac_organization, IsNonEmptyString)

    def test_ignores_duplicate_macs(self):
        rack1 = factory.make_RackController()
        rack2 = factory.make_RackController()
        iface1 = factory.make_Interface(node=rack1)
        iface2 = factory.make_Interface(node=rack2)
        # Simulate a single device being observed from two different rack
        # interfaces.
        d1 = factory.make_Discovery(interface=iface1)
        factory.make_Discovery(
            interface=iface2, mac_address=d1.mac_address, ip=d1.ip
        )
        # ... the Discovery view should only display one entry.
        self.assertThat(Discovery.objects.count(), Equals(1))

    def test_query_by_unknown_mac(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        discovery = factory.make_Discovery(interface=iface)
        self.assertThat(Discovery.objects.by_unknown_mac().count(), Equals(1))
        factory.make_Interface(mac_address=discovery.mac_address)
        # Now that we have a known interface with the same MAC, the discovery
        # should disappear from this query.
        self.assertThat(Discovery.objects.by_unknown_mac().count(), Equals(0))

    def test_query_by_unknown_ip(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        discovery = factory.make_Discovery(interface=iface, ip="10.0.0.1")
        self.assertThat(Discovery.objects.by_unknown_ip().count(), Equals(1))
        factory.make_StaticIPAddress(ip=discovery.ip, cidr="10.0.0.0/8")
        # Now that we have a known IP address that matches, the discovery
        # should disappear from this query.
        self.assertThat(Discovery.objects.by_unknown_ip().count(), Equals(0))

    def test_query_by_unknown_ip_and_mac__known_ip(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        discovery = factory.make_Discovery(interface=iface, ip="10.0.0.1")
        self.assertThat(
            Discovery.objects.by_unknown_ip_and_mac().count(), Equals(1)
        )
        factory.make_StaticIPAddress(ip=discovery.ip, cidr="10.0.0.0/8")
        # Known IP address, unexpected MAC.
        self.assertThat(
            Discovery.objects.by_unknown_ip_and_mac().count(), Equals(0)
        )

    def test_query_by_unknown_ip_and_mac__known_mac(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        discovery = factory.make_Discovery(interface=iface)
        self.assertThat(
            Discovery.objects.by_unknown_ip_and_mac().count(), Equals(1)
        )
        # Known MAC, unknown IP.
        factory.make_Interface(mac_address=discovery.mac_address)
        self.assertThat(
            Discovery.objects.by_unknown_ip_and_mac().count(), Equals(0)
        )

    def test_does_not_fail_if_cannot_find_subnet(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        factory.make_Discovery(interface=iface, ip="10.0.0.1")
        self.assertThat(Discovery.objects.first().subnet, Is(None))

    def test_associates_known_subnet(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        subnet = factory.make_Subnet(cidr="10.0.0.0/8", vlan=iface.vlan)
        factory.make_Discovery(interface=iface, ip="10.0.0.1")
        self.assertThat(Discovery.objects.first().subnet, Equals(subnet))

    def test_associates_best_subnet(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        # Seems unlikely, but we'll test it anyway. ;-)
        subnet = factory.make_Subnet(cidr="10.0.0.0/24", vlan=iface.vlan)
        factory.make_Subnet(cidr="10.0.0.0/8", vlan=iface.vlan)
        factory.make_Discovery(interface=iface, ip="10.0.0.1")
        self.assertThat(Discovery.objects.first().subnet, Equals(subnet))
        self.assertThat(Discovery.objects.count(), Equals(1))

    def test_is_external_dhcp(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        factory.make_Subnet(cidr="10.0.0.0/8", vlan=iface.vlan)
        factory.make_Discovery(interface=iface, ip="10.0.0.1")
        discovery = Discovery.objects.first()
        self.assertThat(discovery.is_external_dhcp, Equals(False))
        iface.vlan.external_dhcp = "10.0.0.1"
        iface.vlan.save()
        discovery = Discovery.objects.first()
        self.assertThat(discovery.is_external_dhcp, Equals(True))

    def test_exposes_mdns_when_nothing_better_available(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        ip = factory.make_ip_address(ipv6=False)
        mdns_hostname = factory.make_hostname()
        factory.make_Discovery(hostname=mdns_hostname, interface=iface, ip=ip)
        discovery = Discovery.objects.first()
        self.assertThat(discovery.hostname, Equals(mdns_hostname))

    def test_prefers_rdns_to_mdns(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        ip = factory.make_ip_address(ipv6=False)
        mdns_hostname = factory.make_hostname()
        rdns_hostname = factory.make_hostname()
        factory.make_Discovery(hostname="", interface=iface, ip=ip)
        factory.make_MDNS(hostname=mdns_hostname, ip=ip, interface=iface)
        factory.make_RDNS(hostname=rdns_hostname, ip=ip, observer=rack)
        discovery = Discovery.objects.first()
        self.assertThat(discovery.hostname, Equals(rdns_hostname))


class TestDiscoveryManagerClear(MAASServerTestCase):
    """Tests for `DiscoveryManager.clear`"""

    def test_clear_mdns_entries(self):
        maaslog = self.patch(discovery_module.maaslog, "info")
        factory.make_MDNS()
        factory.make_MDNS()
        factory.make_Neighbour()
        factory.make_Neighbour()
        self.assertThat(MDNS.objects.count(), Equals(2))
        self.assertThat(Neighbour.objects.count(), Equals(2))
        Discovery.objects.clear(mdns=True)
        self.assertThat(MDNS.objects.count(), Equals(0))
        self.assertThat(Neighbour.objects.count(), Equals(2))
        self.assertThat(
            maaslog,
            MockCalledOnceWith(
                Matches(DocTestMatches("Cleared all mDNS entries."))
            ),
        )

    def test_clear_neighbour_entries(self):
        maaslog = self.patch(discovery_module.maaslog, "info")
        factory.make_MDNS()
        factory.make_MDNS()
        factory.make_Neighbour()
        factory.make_Neighbour()
        self.assertThat(MDNS.objects.count(), Equals(2))
        self.assertThat(Neighbour.objects.count(), Equals(2))
        Discovery.objects.clear(neighbours=True)
        self.assertThat(MDNS.objects.count(), Equals(2))
        self.assertThat(Neighbour.objects.count(), Equals(0))
        self.assertThat(
            maaslog,
            MockCalledOnceWith(
                Matches(DocTestMatches("Cleared all neighbour entries."))
            ),
        )

    def test_clear_all_entries(self):
        maaslog = self.patch(discovery_module.maaslog, "info")
        factory.make_MDNS()
        factory.make_MDNS()
        factory.make_Neighbour()
        factory.make_Neighbour()
        self.assertThat(MDNS.objects.count(), Equals(2))
        self.assertThat(Neighbour.objects.count(), Equals(2))
        Discovery.objects.clear(all=True)
        self.assertThat(MDNS.objects.count(), Equals(0))
        self.assertThat(Neighbour.objects.count(), Equals(0))
        self.assertThat(
            maaslog,
            MockCalledOnceWith(
                Matches(
                    DocTestMatches("Cleared all mDNS and neighbour entries.")
                )
            ),
        )

    def test_clear_mdns_entries_is_noop_if_what_to_clear_is_unspecified(self):
        maaslog = self.patch(discovery_module.maaslog, "info")
        factory.make_MDNS()
        factory.make_MDNS()
        factory.make_Neighbour()
        factory.make_Neighbour()
        self.assertThat(MDNS.objects.count(), Equals(2))
        self.assertThat(Neighbour.objects.count(), Equals(2))
        # clear() is a no-op if what to clear isn't specified.
        Discovery.objects.clear()
        self.assertThat(MDNS.objects.count(), Equals(2))
        self.assertThat(Neighbour.objects.count(), Equals(2))
        self.assertThat(maaslog, MockNotCalled())

    def test_clear_logs_username_if_given(self):
        user = factory.make_admin()
        maaslog = self.patch(discovery_module.maaslog, "info")
        factory.make_MDNS()
        factory.make_Neighbour()
        Discovery.objects.clear(user=user, all=True)
        self.assertThat(
            maaslog,
            MockCalledOnceWith(
                Matches(DocTestMatches("User '%s' cleared..." % user.username))
            ),
        )


class TestDiscoveryManagerDeleteByMacAndIP(MAASServerTestCase):
    """Tests for `DiscoveryManager.delete_by_mac_and_ip`"""

    def test_deletes_neighbours_matching_mac_and_ip(self):
        neigh = factory.make_Neighbour()
        factory.make_Neighbour(ip=neigh.ip, mac_address=neigh.mac_address)
        self.assertThat(Neighbour.objects.count(), Equals(2))
        Discovery.objects.delete_by_mac_and_ip(
            ip=neigh.ip, mac=neigh.mac_address
        )
        self.assertThat(Neighbour.objects.count(), Equals(0))

    def test_unrelated_neighbours_remain(self):
        neigh = factory.make_Neighbour()
        factory.make_Neighbour(ip=neigh.ip, mac_address=neigh.mac_address)
        # Make an extra neighbour; this one shouldn't go away.
        factory.make_Neighbour()
        self.assertThat(Neighbour.objects.count(), Equals(3))
        Discovery.objects.delete_by_mac_and_ip(
            ip=neigh.ip, mac=neigh.mac_address
        )
        self.assertThat(Neighbour.objects.count(), Equals(1))

    def test_deletes_related_mdns_entries(self):
        neigh = factory.make_Neighbour()
        factory.make_Neighbour(ip=neigh.ip, mac_address=neigh.mac_address)
        factory.make_MDNS(ip=neigh.ip)
        self.assertThat(Neighbour.objects.count(), Equals(2))
        self.assertThat(MDNS.objects.count(), Equals(1))
        Discovery.objects.delete_by_mac_and_ip(
            ip=neigh.ip, mac=neigh.mac_address
        )
        self.assertThat(Neighbour.objects.count(), Equals(0))
        self.assertThat(MDNS.objects.count(), Equals(0))

    def test_deletes_related_rdns_entries(self):
        neigh = factory.make_Neighbour()
        factory.make_Neighbour(ip=neigh.ip, mac_address=neigh.mac_address)
        factory.make_RDNS(ip=neigh.ip)
        self.assertThat(Neighbour.objects.count(), Equals(2))
        self.assertThat(RDNS.objects.count(), Equals(1))
        Discovery.objects.delete_by_mac_and_ip(
            ip=neigh.ip, mac=neigh.mac_address
        )
        self.assertThat(Neighbour.objects.count(), Equals(0))
        self.assertThat(MDNS.objects.count(), Equals(0))

    def test_log_entries(self):
        maaslog = self.patch(discovery_module.maaslog, "info")
        user = factory.make_admin()
        neigh = factory.make_Neighbour(
            ip="1.1.1.1", mac_address="00:01:02:03:04:05"
        )
        Discovery.objects.delete_by_mac_and_ip(
            ip=neigh.ip, mac=neigh.mac_address, user=user
        )
        self.assertThat(
            maaslog,
            MockCalledOnceWith(
                Matches(DocTestMatches("User '%s' cleared..." % user.username))
            ),
        )
        neigh = factory.make_Neighbour(
            ip="1.1.1.1", mac_address="00:01:02:03:04:05"
        )
        maaslog = self.patch(discovery_module.maaslog, "info")
        Discovery.objects.delete_by_mac_and_ip(
            ip=neigh.ip, mac=neigh.mac_address
        )
        self.assertThat(
            maaslog,
            MockCalledOnceWith(
                Matches(
                    DocTestMatches("Cleared neighbour entry: 1.1.1.1 (00:...")
                )
            ),
        )
