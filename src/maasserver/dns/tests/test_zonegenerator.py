# Copyright 2014-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import os
import random
import socket
from unittest.mock import call, Mock
from urllib.parse import urlparse

from netaddr import IPAddress, IPNetwork
from testtools import TestCase

from maasserver import server_address
from maasserver.dns import zonegenerator
from maasserver.dns.zonegenerator import (
    get_dns_search_paths,
    get_dns_server_address,
    get_dns_server_addresses,
    get_hostname_dnsdata_mapping,
    get_hostname_ip_mapping,
    InternalDomain,
    InternalDomainResourse,
    InternalDomainResourseRecord,
    lazydict,
    warn_loopback,
    WARNING_MESSAGE,
    ZoneGenerator,
)
from maasserver.enum import IPADDRESS_TYPE, NODE_STATUS, RDNS_MODE
from maasserver.exceptions import UnresolvableHost
from maasserver.models import Config, Domain, Subnet
from maasserver.models.dnsdata import HostnameRRsetMapping
from maasserver.models.staticipaddress import (
    HostnameIPMapping,
    StaticIPAddress,
)
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import post_commit_hooks, transactional
from maastesting.factory import factory as maastesting_factory
from maastesting.fakemethod import FakeMethod
from provisioningserver.dns.config import DynamicDNSUpdate
from provisioningserver.dns.testing import patch_zone_file_config_path
from provisioningserver.dns.zoneconfig import (
    DNSForwardZoneConfig,
    DNSReverseZoneConfig,
)


class TestGetDNSServerAddress(MAASServerTestCase):
    def test_get_dns_server_address_resolves_hostname(self):
        url = maastesting_factory.make_simple_http_url()
        self.useFixture(RegionConfigurationFixture(maas_url=url))
        ip = factory.make_ipv4_address()
        resolver = self.patch(server_address, "resolve_hostname")
        resolver.return_value = {IPAddress(ip)}

        hostname = urlparse(url).hostname
        result = get_dns_server_address()
        self.assertEqual(ip, result)
        resolver.assert_any_call(hostname, 0)

    def test_get_dns_server_address_passes_on_IPv4_IPv6_selection(self):
        ipv4 = factory.pick_bool()
        ipv6 = factory.pick_bool()
        patch = self.patch(zonegenerator, "get_maas_facing_server_addresses")
        patch.return_value = [IPAddress(factory.make_ipv4_address())]

        get_dns_server_address(ipv4=ipv4, ipv6=ipv6)

        patch.assert_called_once_with(
            rack_controller=None,
            include_alternates=False,
            ipv4=ipv4,
            ipv6=ipv6,
            default_region_ip=None,
        )

    def test_get_dns_server_address_raises_if_hostname_doesnt_resolve(self):
        url = maastesting_factory.make_simple_http_url()
        self.useFixture(RegionConfigurationFixture(maas_url=url))
        self.patch(
            zonegenerator,
            "get_maas_facing_server_addresses",
            FakeMethod(failure=socket.error),
        )
        self.assertRaises(UnresolvableHost, get_dns_server_address)

    def test_get_dns_server_address_logs_warning_if_ip_is_localhost(self):
        logger = self.patch(zonegenerator, "logger")
        self.patch(
            zonegenerator,
            "get_maas_facing_server_addresses",
            Mock(return_value=[IPAddress("127.0.0.1")]),
        )
        get_dns_server_address()
        self.assertEqual(
            call(WARNING_MESSAGE % "127.0.0.1"), logger.warning.call_args
        )

    def test_get_dns_server_address_uses_rack_controller_url(self):
        ip = factory.make_ipv4_address()
        resolver = self.patch(server_address, "resolve_hostname")
        resolver.return_value = {IPAddress(ip)}
        hostname = factory.make_hostname()
        maas_url = "http://%s" % hostname
        rack_controller = factory.make_RackController(url=maas_url)
        result = get_dns_server_address(rack_controller)
        self.assertEqual(ip, result)
        resolver.assert_any_call(hostname, 0)

    def test_get_dns_server_address_ignores_unallowed_dns(self):
        # Regression test for LP:1847537
        subnet = factory.make_Subnet(cidr="10.0.0.0/24", allow_dns=False)
        ip = factory.make_StaticIPAddress(subnet=subnet)
        resolver = self.patch(server_address, "resolve_hostname")
        resolver.return_value = {IPAddress(ip.ip)}
        rack_controller = factory.make_RackController(
            subnet=subnet, url="http://%s" % ip.ip
        )
        self.assertIsNone(get_dns_server_address(rack_controller))


class TestGetDNSServerAddresses(MAASServerTestCase):
    def test_no_rack_all_subnets(self):
        subnet1 = factory.make_Subnet(cidr="10.10.0.0/24", allow_dns=False)
        subnet2 = factory.make_Subnet(cidr="10.20.0.0/24", allow_dns=True)
        ip1 = factory.make_StaticIPAddress(subnet=subnet1)
        ip2 = factory.make_StaticIPAddress(subnet=subnet2)
        ips = {IPAddress(ip1.ip), IPAddress(ip2.ip)}
        resolver = self.patch(server_address, "resolve_hostname")
        resolver.return_value = ips
        rack_controller = factory.make_RackController()
        self.assertCountEqual(
            get_dns_server_addresses(
                rack_controller=rack_controller, filter_allowed_dns=False
            ),
            ips,
        )

    def test_with_rack_only_allow_dns(self):
        subnet1 = factory.make_Subnet(cidr="10.10.0.0/24", allow_dns=False)
        subnet2 = factory.make_Subnet(cidr="10.20.0.0/24", allow_dns=True)
        ip1 = factory.make_StaticIPAddress(subnet=subnet1)
        ip2 = factory.make_StaticIPAddress(subnet=subnet2)
        resolver = self.patch(server_address, "resolve_hostname")
        resolver.return_value = {IPAddress(ip1.ip), IPAddress(ip2.ip)}
        rack_controller = factory.make_RackController()
        self.assertCountEqual(
            get_dns_server_addresses(rack_controller=rack_controller),
            [IPAddress(ip2.ip)],
        )


class TestGetDNSSearchPaths(MAASServerTestCase):
    def test_returns_all_authoritative_domains(self):
        domain_names = get_dns_search_paths()
        domain_names.update(
            factory.make_Domain(authoritative=True).name for _ in range(3)
        )
        for _ in range(3):
            factory.make_Domain(authoritative=False)
        self.assertEqual(domain_names, get_dns_search_paths())


class TestWarnLoopback(MAASServerTestCase):
    def test_warn_loopback_warns_about_IPv4_loopback(self):
        logger = self.patch(zonegenerator, "logger")
        loopback = "127.0.0.1"
        warn_loopback(loopback)
        logger.warning.assert_called_once_with(WARNING_MESSAGE % loopback)

    def test_warn_loopback_warns_about_any_IPv4_loopback(self):
        logger = self.patch(zonegenerator, "logger")
        loopback = "127.254.100.99"
        warn_loopback(loopback)
        logger.warning.assert_called_once_with(WARNING_MESSAGE % loopback)

    def test_warn_loopback_warns_about_IPv6_loopback(self):
        logger = self.patch(zonegenerator, "logger")
        loopback = "::1"
        warn_loopback(loopback)
        logger.warning.assert_called_once_with(WARNING_MESSAGE % loopback)

    def test_warn_loopback_does_not_warn_about_sensible_IPv4(self):
        logger = self.patch(zonegenerator, "logger")
        warn_loopback("10.1.2.3")
        logger.warning.assert_not_called()

    def test_warn_loopback_does_not_warn_about_sensible_IPv6(self):
        logger = self.patch(zonegenerator, "logger")
        warn_loopback("1::9")
        logger.warning.assert_not_called()


class TestLazyDict(TestCase):
    """Tests for `lazydict`."""

    def test_empty_initially(self):
        self.assertEqual({}, lazydict(Mock()))

    def test_populates_on_demand(self):
        value = factory.make_name("value")
        value_dict = lazydict(lambda key: value)
        key = factory.make_name("key")
        retrieved_value = value_dict[key]
        self.assertEqual(value, retrieved_value)
        self.assertEqual({key: value}, value_dict)

    def test_remembers_elements(self):
        value_dict = lazydict(lambda key: factory.make_name("value"))
        key = factory.make_name("key")
        self.assertEqual(value_dict[key], value_dict[key])

    def test_holds_one_value_per_key(self):
        value_dict = lazydict(lambda key: key)
        key1 = factory.make_name("key")
        key2 = factory.make_name("key")

        value1 = value_dict[key1]
        value2 = value_dict[key2]

        self.assertEqual((key1, key2), (value1, value2))
        self.assertEqual({key1: key1, key2: key2}, value_dict)


class TestGetHostnameMapping(MAASServerTestCase):
    """Test for `get_hostname_ip_mapping`."""

    def test_get_hostname_ip_mapping_containts_both_static_and_dynamic(self):
        node1 = factory.make_Node(interface=True)
        node1_interface = node1.get_boot_interface()
        subnet = factory.make_Subnet()
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=node1_interface,
        )
        node2 = factory.make_Node(interface=True)
        node2_interface = node2.get_boot_interface()
        subnet = factory.make_ipv4_Subnet_with_IPRanges()
        dynamic_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            ip=factory.pick_ip_in_IPRange(subnet.get_dynamic_ranges()[0]),
            subnet=subnet,
            interface=node2_interface,
        )
        ttl = random.randint(10, 300)
        Config.objects.set_config("default_dns_ttl", ttl)
        expected_mapping = {
            "%s.maas" % node1.hostname: HostnameIPMapping(
                node1.system_id, ttl, {static_ip.ip}, node1.node_type
            ),
            "%s.maas" % node2.hostname: HostnameIPMapping(
                node2.system_id, ttl, {dynamic_ip.ip}, node2.node_type
            ),
        }
        actual = get_hostname_ip_mapping(Domain.objects.get_default_domain())
        self.assertEqual(expected_mapping, actual)

    def test_get_hostname_dnsdata_mapping_contains_node_and_non_node(self):
        node = factory.make_Node(interface=True)
        dnsdata1 = factory.make_DNSData(
            name=node.hostname, domain=node.domain, rrtype="MX"
        )
        dnsdata2 = factory.make_DNSData(domain=node.domain)
        ttl = random.randint(10, 300)
        Config.objects.set_config("default_dns_ttl", ttl)
        expected_mapping = {
            dnsdata1.dnsresource.name: HostnameRRsetMapping(
                node.system_id,
                {(ttl, dnsdata1.rrtype, dnsdata1.rrdata)},
                node.node_type,
            ),
            dnsdata2.dnsresource.name: HostnameRRsetMapping(
                None, {(ttl, dnsdata2.rrtype, dnsdata2.rrdata)}, None
            ),
        }
        actual = get_hostname_dnsdata_mapping(node.domain)
        self.assertEqual(expected_mapping, actual)


def assertIsForwardZoneWithDomain(testcase, zone, domain):
    testcase.assertIsInstance(zone, DNSForwardZoneConfig)
    testcase.assertEqual(zone.domain, domain)


def assertIsReverseZoneWithDomain(testcase, zone, domain, network):
    network = network if network is None else IPNetwork(network)
    testcase.assertIsInstance(zone, DNSReverseZoneConfig)
    testcase.assertEqual(zone.domain, domain)
    testcase.assertEqual(zone._network, network)


class TestZoneGenerator(MAASServerTestCase):
    """Tests for :class:`ZoneGenerator`."""

    def setUp(self):
        super().setUp()
        self.useFixture(RegionConfigurationFixture())

    def test_empty_yields_nothing(self):
        self.assertEqual(
            [],
            ZoneGenerator((), (), serial=random.randint(0, 65535)).as_list(),
        )

    def test_defaults_ttl(self):
        zonegen = ZoneGenerator((), (), serial=random.randint(0, 65535))
        self.assertEqual(
            Config.objects.get_config("default_dns_ttl"), zonegen.default_ttl
        )
        self.assertEqual([], zonegen.as_list())

    def test_accepts_default_ttl(self):
        default_ttl = random.randint(10, 1000)
        zonegen = ZoneGenerator(
            (), (), default_ttl=default_ttl, serial=random.randint(0, 65535)
        )
        self.assertEqual(default_ttl, zonegen.default_ttl)

    def test_yields_forward_and_reverse_zone(self):
        default_domain = Domain.objects.get_default_domain().name
        domain = factory.make_Domain(name="henry")
        subnet = factory.make_Subnet(cidr=str(IPNetwork("10/29").cidr))
        fwd, rev1, rev2 = ZoneGenerator(
            domain, subnet, serial=random.randint(0, 65535)
        ).as_list()
        assertIsForwardZoneWithDomain(self, fwd, "henry")
        assertIsReverseZoneWithDomain(self, rev1, default_domain, "10/29")
        assertIsReverseZoneWithDomain(self, rev2, default_domain, "10/24")

    def test_yields_forward_and_reverse_zone_no_overlap_bug(self):
        domain = factory.make_Domain(name="overlap")
        subnet1 = factory.make_Subnet(cidr="192.168.33.0/25")
        subnet2 = factory.make_Subnet(cidr="192.168.35.0/26")
        subnet3 = factory.make_Subnet(cidr="192.168.36.0/26")
        zones = ZoneGenerator(
            domain,
            [
                subnet2,
                subnet1,
                subnet3,
            ],  # purposely out of order to assert subnets are being sorted
            serial=random.randint(0, 65535),
        ).as_list()
        expected_domains = [
            "0-25.33.168.192.in-addr.arpa",
            "0-26.35.168.192.in-addr.arpa",
            "0-26.36.168.192.in-addr.arpa",
            "33.168.192.in-addr.arpa",
            "35.168.192.in-addr.arpa",
            "36.168.192.in-addr.arpa",
            "overlap",
        ]
        zone_names = [
            info.zone_name for zone in zones for info in zone.zone_info
        ]
        self.assertCountEqual(zone_names, expected_domains)

    def test_yields_forward_and_reverse_zone_no_overlap(self):
        domain = factory.make_Domain(name="overlap")
        vlan1 = factory.make_VLAN(vid=1, dhcp_on=True)
        vlan2 = factory.make_VLAN(vid=2, dhcp_on=True)
        subnet1 = factory.make_Subnet(cidr="10.232.36.0/24", vlan=vlan1)
        subnet2 = factory.make_Subnet(cidr="10.232.32.0/21", vlan=vlan2)
        subnet3 = factory.make_Subnet(cidr="10.232.6.0/24", vlan=vlan1)
        subnet4 = factory.make_Subnet(cidr="10.2.36.0/24", vlan=vlan1)
        subnet5 = factory.make_Subnet(cidr="10.231.36.0/24", vlan=vlan1)
        subnet6 = factory.make_Subnet(cidr="10.232.40.0/24", vlan=vlan1)
        zones = ZoneGenerator(
            domain,
            [
                subnet2,
                subnet1,
                subnet3,
                subnet4,
                subnet5,
                subnet6,
            ],  # purposely out of order to assert subnets are being sorted
            serial=random.randint(0, 65535),
        ).as_list()
        self.assertEqual(len(zones), 13)  # 5 /24s and 8 from the /21
        expected_domains = [
            "overlap",
            "36.232.10.in-addr.arpa",
            "32.232.10.in-addr.arpa",
            "6.232.10.in-addr.arpa",
            "36.2.10.in-addr.arpa",
            "36.231.10.in-addr.arpa",
            "40.232.10.in-addr.arpa",
            "38.232.10.in-addr.arpa",
            "34.232.10.in-addr.arpa",
            "35.232.10.in-addr.arpa",
            "39.232.10.in-addr.arpa",
            "37.232.10.in-addr.arpa",
            "33.232.10.in-addr.arpa",
        ]
        zone_names = [
            info.zone_name for zone in zones for info in zone.zone_info
        ]
        self.assertCountEqual(zone_names, expected_domains)

    def test_with_node_yields_fwd_and_rev_zone(self):
        default_domain = Domain.objects.get_default_domain().name
        domain = factory.make_Domain(name="henry")
        subnet = factory.make_Subnet(cidr=str(IPNetwork("10/29").cidr))
        factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, vlan=subnet.vlan, fabric=subnet.vlan.fabric
        )
        fwd, rev1, rev2 = ZoneGenerator(
            domain, subnet, serial=random.randint(0, 65535)
        ).as_list()
        assertIsForwardZoneWithDomain(self, fwd, "henry")
        assertIsReverseZoneWithDomain(self, rev1, default_domain, "10/29")
        assertIsReverseZoneWithDomain(self, rev2, default_domain, "10/24")

    def test_with_child_domain_yields_delegation(self):
        default_domain = Domain.objects.get_default_domain().name
        domain = factory.make_Domain(name="henry")
        factory.make_Domain(name="john.henry")
        subnet = factory.make_Subnet(cidr=str(IPNetwork("10/29").cidr))
        factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, vlan=subnet.vlan, fabric=subnet.vlan.fabric
        )
        fwd, rev1, rev2 = ZoneGenerator(
            domain, subnet, serial=random.randint(0, 65535)
        ).as_list()
        assertIsForwardZoneWithDomain(self, fwd, "henry")
        assertIsReverseZoneWithDomain(self, rev1, default_domain, "10/29")
        assertIsReverseZoneWithDomain(self, rev2, default_domain, "10/24")
        expected_map = {
            "john": HostnameRRsetMapping(None, {(30, "NS", default_domain)})
        }
        self.assertEqual(expected_map, fwd._other_mapping)

    def test_with_child_domain_yields_glue_when_needed(self):
        default_domain = Domain.objects.get_default_domain().name
        domain = factory.make_Domain(name="henry")
        john = factory.make_Domain(name="john.henry")
        subnet = factory.make_Subnet(cidr=str(IPNetwork("10/29").cidr))
        sip = factory.make_StaticIPAddress(subnet=subnet)
        factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, vlan=subnet.vlan, fabric=subnet.vlan.fabric
        )
        factory.make_DNSResource(name="ns", domain=john, ip_addresses=[sip])
        factory.make_DNSData(name="@", domain=john, rrtype="NS", rrdata="ns")
        # We have a subdomain (john.henry) which as an NS RR of
        # 'ns.john.henry', and we should see glue records for it in the parent
        # zone, as well as the A RR in the child.
        fwd, rev1, rev2 = ZoneGenerator(
            domain, subnet, serial=random.randint(0, 65535)
        ).as_list()
        assertIsForwardZoneWithDomain(self, fwd, "henry")
        assertIsReverseZoneWithDomain(self, rev1, default_domain, "10/29")
        assertIsReverseZoneWithDomain(self, rev2, default_domain, "10/24")
        expected_map = {
            "john": HostnameRRsetMapping(
                None, {(30, "NS", default_domain), (30, "NS", "ns")}
            ),
            "ns": HostnameRRsetMapping(None, {(30, "A", sip.ip)}),
        }
        self.assertEqual(expected_map, fwd._other_mapping)

    def test_glue_receives_correct_dynamic_updates(self):
        domain = factory.make_Domain()
        subnet = factory.make_Subnet(cidr=str(IPNetwork("10/29").cidr))
        other_subnet = factory.make_Subnet()
        sip = factory.make_StaticIPAddress(subnet=subnet)
        other_sip = factory.make_StaticIPAddress(subnet=other_subnet)
        factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, vlan=subnet.vlan, fabric=subnet.vlan.fabric
        )
        update_rec = factory.make_DNSResource(
            name=factory.make_name(), domain=domain, ip_addresses=[sip]
        )
        updates = [
            DynamicDNSUpdate(
                operation="INSERT",
                name=update_rec.name,
                zone=domain.name,
                rectype="A",
                answer=sip.ip,
            ),
            DynamicDNSUpdate(
                operation="INSERT",
                name=update_rec.name,
                zone=domain.name,
                rectype="A",
                answer=other_sip.ip,
            ),
        ]
        zones = ZoneGenerator(
            domain,
            subnet,
            serial=random.randint(0, 65535),
            dynamic_updates=updates,
        ).as_list()
        self.assertCountEqual(zones[0]._dynamic_updates, updates)
        self.assertCountEqual(
            zones[1]._dynamic_updates,
            [
                DynamicDNSUpdate.as_reverse_record_update(
                    updates[0], IPNetwork("10/29")
                )
            ],
        )
        self.assertCountEqual(
            zones[2]._dynamic_updates,
            [
                DynamicDNSUpdate.as_reverse_record_update(
                    updates[0], IPNetwork("10/24")
                )
            ],
        )

    def test_parent_of_default_domain_gets_glue(self):
        default_domain = Domain.objects.get_default_domain()
        default_domain.name = "maas.example.com"
        default_domain.save()
        domains = [default_domain, factory.make_Domain("example.com")]
        self.patch(zonegenerator, "get_dns_server_addresses").return_value = [
            IPAddress("5.5.5.5")
        ]
        subnet = factory.make_Subnet(cidr=str(IPNetwork("10/29").cidr))
        factory.make_StaticIPAddress(subnet=subnet)
        factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, vlan=subnet.vlan, fabric=subnet.vlan.fabric
        )
        fwd1, fwd2, rev1, rev2 = ZoneGenerator(
            domains, subnet, serial=random.randint(0, 65535)
        ).as_list()
        assertIsForwardZoneWithDomain(self, fwd1, default_domain.name)
        assertIsForwardZoneWithDomain(self, fwd2, domains[1].name)
        assertIsReverseZoneWithDomain(self, rev1, default_domain.name, "10/29")
        assertIsReverseZoneWithDomain(self, rev2, default_domain.name, "10/24")
        # maas.example.com is the default zone, and has an A RR for its NS RR.
        # example.com has NS maas.example.com., and a glue record for that.
        expected_map_0 = {
            "@": HostnameRRsetMapping(None, {(30, "A", "5.5.5.5")}, None)
        }
        expected_map_1 = {
            "maas": HostnameRRsetMapping(
                None,
                {
                    (30, "A", IPAddress("5.5.5.5")),
                    (30, "NS", "maas.example.com"),
                },
                None,
            )
        }
        self.assertEqual(expected_map_0, fwd1._other_mapping)
        self.assertEqual(expected_map_1, fwd2._other_mapping)

    def test_returns_interface_ips_but_no_nulls(self):
        default_domain = Domain.objects.get_default_domain().name
        domain = factory.make_Domain(name="henry")
        subnet = factory.make_Subnet(cidr=str(IPNetwork("10/29").cidr))
        subnet.gateway_ip = str(IPAddress(IPNetwork(subnet.cidr).ip + 1))
        subnet.save()
        # Create a node with two interfaces, with NULL ips
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet,
            vlan=subnet.vlan,
            fabric=subnet.vlan.fabric,
            domain=domain,
            interface_count=3,
        )
        dnsdata = factory.make_DNSData(domain=domain)
        boot_iface = node.boot_interface
        interfaces = list(
            node.current_config.interface_set.all().exclude(id=boot_iface.id)
        )
        # Now go add IP addresses to the boot interface, and one other
        boot_ip = factory.make_StaticIPAddress(
            interface=boot_iface, subnet=subnet
        )
        sip = factory.make_StaticIPAddress(
            interface=interfaces[0], subnet=subnet
        )
        default_ttl = random.randint(10, 300)
        Config.objects.set_config("default_dns_ttl", default_ttl)
        fwd, rev1, rev2 = ZoneGenerator(
            domain,
            subnet,
            default_ttl=default_ttl,
            serial=random.randint(0, 65535),
        ).as_list()
        assertIsForwardZoneWithDomain(self, fwd, "henry")
        assertIsReverseZoneWithDomain(self, rev1, default_domain, "10/29")
        assertIsReverseZoneWithDomain(self, rev2, default_domain, "10/24")
        self.assertEqual(
            {
                node.hostname: HostnameIPMapping(
                    node.system_id,
                    default_ttl,
                    {str(boot_ip.ip)},
                    node.node_type,
                ),
                "%s.%s"
                % (interfaces[0].name, node.hostname): HostnameIPMapping(
                    node.system_id,
                    default_ttl,
                    {str(sip.ip)},
                    node.node_type,
                ),
            },
            fwd._mapping,
        )
        self.assertEqual(
            {
                dnsdata.dnsresource.name: HostnameRRsetMapping(
                    None, {(default_ttl, dnsdata.rrtype, dnsdata.rrdata)}
                )
            }.items(),
            fwd._other_mapping.items(),
        )
        self.assertEqual(
            {
                node.fqdn: HostnameIPMapping(
                    node.system_id,
                    default_ttl,
                    {str(boot_ip.ip)},
                    node.node_type,
                ),
                "%s.%s" % (interfaces[0].name, node.fqdn): HostnameIPMapping(
                    node.system_id,
                    default_ttl,
                    {str(sip.ip)},
                    node.node_type,
                ),
            },
            rev1._mapping,
        )
        self.assertEqual({}, rev2._mapping)

    def test_forward_zone_includes_subnets_with_allow_dns_false(self):
        default_ttl = random.randint(10, 300)
        Config.objects.set_config("default_dns_ttl", default_ttl)
        default_domain = Domain.objects.get_default_domain()
        subnet = factory.make_Subnet(cidr="10.10.0.0/24", allow_dns=False)
        ip = factory.make_StaticIPAddress(subnet=subnet)
        resolver = self.patch(server_address, "resolve_hostname")
        resolver.return_value = {IPAddress(ip.ip)}
        zones = ZoneGenerator(
            [default_domain], subnet, serial=random.randint(0, 65535)
        )
        [forward_zone] = [
            zone for zone in zones if isinstance(zone, DNSForwardZoneConfig)
        ]
        self.assertEqual(
            forward_zone._other_mapping["@"].rrset, {(default_ttl, "A", ip.ip)}
        )

    def rfc2317_network(self, network):
        """Returns the network that rfc2317 glue goes in, if any."""
        net = network
        if net.version == 4 and net.prefixlen > 24:
            net = IPNetwork("%s/24" % net.network)
            net = IPNetwork("%s/24" % net.network)
        if net.version == 6 and net.prefixlen > 124:
            net = IPNetwork("%s/124" % net.network)
            net = IPNetwork("%s/124" % net.network)
        if net != network:
            return net
        return None

    def test_supernet_inherits_rfc2317_net(self):
        domain = Domain.objects.get_default_domain()
        subnet1 = factory.make_Subnet(host_bits=2)
        net1 = IPNetwork(subnet1.cidr)
        if net1.version == 6:
            prefixlen = random.randint(121, 124)
        else:
            prefixlen = random.randint(22, 24)
        parent = IPNetwork(f"{net1.network}/{prefixlen:d}")
        parent = IPNetwork(f"{parent.network}/{prefixlen:d}")
        subnet2 = factory.make_Subnet(cidr=parent)
        net2 = IPNetwork(subnet2.cidr)
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet1,
            vlan=subnet1.vlan,
            fabric=subnet1.vlan.fabric,
            domain=domain,
        )
        boot_iface = node.boot_interface
        factory.make_StaticIPAddress(interface=boot_iface, subnet=subnet1)
        default_ttl = random.randint(10, 300)
        Config.objects.set_config("default_dns_ttl", default_ttl)
        serial = random.randint(0, 65535)
        zones = ZoneGenerator(
            domain,
            [subnet1, subnet2],
            default_ttl=default_ttl,
            serial=serial,
        ).as_list()
        expected = [
            DNSForwardZoneConfig(
                domain.name,
                serial=serial,
                default_ttl=default_ttl,
            ),
        ]
        for net in [net1, net2]:
            if (
                net.version == 6 and net.prefixlen < 124
            ) or net.prefixlen < 24:
                for network in ZoneGenerator._split_large_subnet(net2):
                    expected.append(
                        DNSReverseZoneConfig(domain.name, network=network)
                    )
            elif net.version == 6 and net.prefixlen > 124:
                expected.append(
                    DNSReverseZoneConfig(
                        domain.name, network=IPNetwork(f"{net.network}/124")
                    )
                )
                expected.append(DNSReverseZoneConfig(domain.name, network=net))
            elif net.version == 4 and net.prefixlen > 24:
                expected.append(
                    DNSReverseZoneConfig(
                        domain.name, network=IPNetwork(f"{net.network}/24")
                    )
                )
                expected.append(DNSReverseZoneConfig(domain.name, network=net))
            else:
                expected.append(DNSReverseZoneConfig(domain.name, network=net))
        self.assertCountEqual(
            set([(zone.domain, zone._network) for zone in zones]),
            set((e.domain, e._network) for e in expected),
            f"{subnet1} {subnet2}",
        )
        self.assertEqual(set(), zones[1]._rfc2317_ranges)
        self.assertEqual({net1}, zones[2]._rfc2317_ranges)

    def test_with_many_yields_many_zones(self):
        # This demonstrates ZoneGenerator in all-singing all-dancing mode.
        default_domain = Domain.objects.get_default_domain()
        domains = [default_domain] + [factory.make_Domain() for _ in range(3)]
        for _ in range(3):
            factory.make_Subnet()
        subnets = Subnet.objects.all()
        expected_zones = set()
        for domain in domains:
            expected_zones.add(DNSForwardZoneConfig(domain.name))
        for subnet in subnets:
            networks = ZoneGenerator._split_large_subnet(
                IPNetwork(subnet.cidr)
            )
            for network in networks:
                expected_zones.add(
                    DNSReverseZoneConfig(default_domain.name, network=network)
                )
                if rfc2317_net := self.rfc2317_network(network):
                    expected_zones.add(
                        DNSReverseZoneConfig(
                            default_domain.name,
                            network=IPNetwork(rfc2317_net.cidr),
                        )
                    )
        actual_zones = ZoneGenerator(
            domains, subnets, serial=random.randint(0, 65535)
        ).as_list()
        self.assertCountEqual(
            [(zone.domain, zone._network) for zone in actual_zones],
            [(zone.domain, zone._network) for zone in expected_zones],
        )

    def test_zone_generator_handles_rdns_mode_equal_enabled(self):
        Domain.objects.get_or_create(name="one")
        subnet = factory.make_Subnet(cidr="10.0.0.0/29")
        subnet.rdns_mode = RDNS_MODE.ENABLED
        subnet.save()
        default_domain = Domain.objects.get_default_domain()
        domains = Domain.objects.filter(name="one")
        subnets = Subnet.objects.all()
        fwd1, rev1 = ZoneGenerator(
            domains, subnets, serial=random.randint(0, 65535)
        ).as_list()
        assertIsForwardZoneWithDomain(self, fwd1, "one")
        assertIsReverseZoneWithDomain(self, rev1, default_domain.name, "10/29")

    def test_yields_internal_forward_zones(self):
        default_domain = Domain.objects.get_default_domain()
        subnet = factory.make_Subnet(cidr=str(IPNetwork("10/29").cidr))
        domains = []
        for _ in range(3):
            record = InternalDomainResourseRecord(
                rrtype="A", rrdata=factory.pick_ip_in_Subnet(subnet)
            )
            resource = InternalDomainResourse(
                name=factory.make_name("resource"), records=[record]
            )
            domain = InternalDomain(
                name=factory.make_name("domain"),
                ttl=random.randint(15, 300),
                resources=[resource],
            )
            domains.append(domain)

        def assertFwdRecord(zone, domain):
            resource_name = domain.resources[0].name
            dns_record = domain.resources[0].records[0]
            self.assertEqual(zone._other_mapping.keys(), {resource_name})
            self.assertEqual(
                zone._other_mapping[resource_name].rrset,
                {(domain.ttl, dns_record.rrtype, dns_record.rrdata)},
            )

        fwd1, fwd2, fwd3, rev1, rev2 = ZoneGenerator(
            [],
            [subnet],
            serial=random.randint(0, 65535),
            internal_domains=domains,
        ).as_list()
        assertIsForwardZoneWithDomain(self, fwd1, domains[0].name)
        assertFwdRecord(fwd1, domains[0])
        assertIsForwardZoneWithDomain(self, fwd2, domains[1].name)
        assertFwdRecord(fwd2, domains[1])
        assertIsForwardZoneWithDomain(self, fwd3, domains[2].name)
        assertFwdRecord(fwd3, domains[2])
        assertIsReverseZoneWithDomain(self, rev1, default_domain.name, "10/29")
        assertIsReverseZoneWithDomain(self, rev2, default_domain.name, "10/24")

    def test_configs_are_merged_when_overlapping(self):
        self.patch(warn_loopback)
        default_domain = Domain.objects.get_default_domain()
        subnet1 = factory.make_Subnet(cidr="10.0.1.0/24")
        subnet2 = factory.make_Subnet(cidr="10.0.0.0/21")
        subnet1_ips = [
            factory.make_StaticIPAddress(
                ip=factory.pick_ip_in_Subnet(subnet1), subnet=subnet1
            )
            for _ in range(3)
        ]
        subnet2_ips = [
            factory.make_StaticIPAddress(
                ip=factory.pick_ip_in_Subnet(subnet2), subnet=subnet2
            )
            for _ in range(3)
        ]
        subnet1_records = [
            factory.make_DNSResource(domain=default_domain, ip_addresses=[ip])
            for ip in subnet1_ips
        ]
        subnet2_records = [
            factory.make_DNSResource(domain=default_domain, ip_addresses=[ip])
            for ip in subnet2_ips
        ]
        serial = random.randint(0, 65535)
        dynamic_updates = [
            DynamicDNSUpdate(
                operation="INSERT",
                name=record.name,
                zone=default_domain.name,
                rectype="A",
                ttl=record.address_ttl,
                answer=ip.ip,
            )
            for record in subnet1_records + subnet2_records
            for ip in record.ip_addresses.all()
        ]
        zones = ZoneGenerator(
            [default_domain],
            [subnet1, subnet2],
            serial=serial,
            dynamic_updates=dynamic_updates,
        ).as_list()

        def _generate_mapping_for_network(network, records):
            mapping = {}
            for record in records:
                if ip_set := set(
                    ip.ip
                    for ip in record.ip_addresses.all()
                    if IPAddress(ip.ip) in network
                ):
                    mapping[f"{record.name}.{default_domain.name}"] = (
                        HostnameIPMapping(
                            None,
                            record.address_ttl,
                            ip_set,
                            None,
                            1,
                            None,
                        )
                    )
            return mapping

        expected = [
            DNSForwardZoneConfig(
                default_domain.name,
                mapping={
                    record.name: HostnameIPMapping(
                        None,
                        record.address_ttl,
                        set(record.ip_addresses.all()),
                        None,
                        1,
                        None,
                    )
                    for record in subnet1_records + subnet2_records
                },
                dynamic_updates=dynamic_updates,
            ),
            DNSReverseZoneConfig(
                default_domain.name,
                network=IPNetwork(subnet1.cidr),
                mapping=_generate_mapping_for_network(
                    IPNetwork(subnet1.cidr), subnet1_records + subnet2_records
                ),
                dynamic_updates=[
                    DynamicDNSUpdate.as_reverse_record_update(
                        update, IPNetwork(subnet1.cidr)
                    )
                    for update in dynamic_updates
                    if update.answer_as_ip in IPNetwork(subnet1.cidr)
                ],
            ),
            DNSReverseZoneConfig(
                default_domain.name,
                network=IPNetwork("10.0.0.0/24"),
                mapping=_generate_mapping_for_network(
                    IPNetwork("10.0.0.0/24"), subnet2_records
                ),
                dynamic_updates=[
                    DynamicDNSUpdate.as_reverse_record_update(
                        update, IPNetwork("10.0.0.0/24")
                    )
                    for update in dynamic_updates
                    if update.answer_as_ip in IPNetwork("10.0.0.0/24")
                ],
            ),
            DNSReverseZoneConfig(
                default_domain.name,
                network=IPNetwork("10.0.2.0/24"),
                mapping=_generate_mapping_for_network(
                    IPNetwork("10.0.2.0/24"), subnet2_records
                ),
                dynamic_updates=[
                    DynamicDNSUpdate.as_reverse_record_update(
                        update, IPNetwork("10.0.2.0/24")
                    )
                    for update in dynamic_updates
                    if update.answer_as_ip in IPNetwork("10.0.2.0/24")
                ],
            ),
            DNSReverseZoneConfig(
                default_domain.name,
                network=IPNetwork("10.0.3.0/24"),
                mapping=_generate_mapping_for_network(
                    IPNetwork("10.0.3.0/24"), subnet2_records
                ),
                dynamic_updates=[
                    DynamicDNSUpdate.as_reverse_record_update(
                        update, IPNetwork("10.0.3.0/24")
                    )
                    for update in dynamic_updates
                    if update.answer_as_ip in IPNetwork("10.0.3.0/24")
                ],
            ),
            DNSReverseZoneConfig(
                default_domain.name,
                network=IPNetwork("10.0.4.0/24"),
                mapping=_generate_mapping_for_network(
                    IPNetwork("10.0.4.0/24"), subnet2_records
                ),
                dynamic_updates=[
                    DynamicDNSUpdate.as_reverse_record_update(
                        update, IPNetwork("10.0.4.0/24")
                    )
                    for update in dynamic_updates
                    if update.answer_as_ip in IPNetwork("10.0.4.0/24")
                ],
            ),
            DNSReverseZoneConfig(
                default_domain.name,
                network=IPNetwork("10.0.5.0/24"),
                mapping=_generate_mapping_for_network(
                    IPNetwork("10.0.5.0/24"), subnet2_records
                ),
                dynamic_updates=[
                    DynamicDNSUpdate.as_reverse_record_update(
                        update, IPNetwork("10.0.5.0/24")
                    )
                    for update in dynamic_updates
                    if update.answer_as_ip in IPNetwork("10.0.5.0/24")
                ],
            ),
            DNSReverseZoneConfig(
                default_domain.name,
                network=IPNetwork("10.0.6.0/24"),
                mapping=_generate_mapping_for_network(
                    IPNetwork("10.0.6.0/24"), subnet2_records
                ),
                dynamic_updates=[
                    DynamicDNSUpdate.as_reverse_record_update(
                        update, IPNetwork("10.0.6.0/24")
                    )
                    for update in dynamic_updates
                    if update.answer_as_ip in IPNetwork("10.0.6.0/24")
                ],
            ),
            DNSReverseZoneConfig(
                default_domain.name,
                network=IPNetwork("10.0.7.0/24"),
                mapping=_generate_mapping_for_network(
                    IPNetwork("10.0.7.0/24"), subnet2_records
                ),
                dynamic_updates=[
                    DynamicDNSUpdate.as_reverse_record_update(
                        update, IPNetwork("10.0.7.0/24")
                    )
                    for update in dynamic_updates
                    if update.answer_as_ip in IPNetwork("10.0.7.0/24")
                ],
            ),
        ]

        for i, zone in enumerate(zones):
            self.assertEqual(zone.domain, expected[i].domain)
            self.assertEqual(zone._network, expected[i]._network)
            self.assertCountEqual(
                zone._mapping,
                expected[i]._mapping,
            )
            self.assertCountEqual(
                zone._dynamic_updates, expected[i]._dynamic_updates
            )
            if isinstance(zone, DNSReverseZoneConfig):
                self.assertCountEqual(
                    zone._dynamic_ranges, expected[i]._dynamic_ranges
                )
                self.assertCountEqual(
                    zone._rfc2317_ranges, expected[i]._rfc2317_ranges
                )

    def test_configs_are_merged_when_glue_overlaps(self):
        self.patch(warn_loopback)
        default_domain = Domain.objects.get_default_domain()
        subnet1 = factory.make_Subnet(cidr="10.0.1.0/24")
        subnet2 = factory.make_Subnet(cidr="10.0.1.0/26")
        subnet1_ips = [
            factory.make_StaticIPAddress(
                ip=f"10.0.1.{253 + i}",
                subnet=subnet1,  # avoid allocation collision
            )
            for i in range(3)
        ]
        subnet2_ips = [
            factory.make_StaticIPAddress(
                ip=factory.pick_ip_in_Subnet(subnet2), subnet=subnet2
            )
            for _ in range(3)
        ]
        subnet1_records = [
            factory.make_DNSResource(domain=default_domain, ip_addresses=[ip])
            for ip in subnet1_ips
        ]
        subnet2_records = [
            factory.make_DNSResource(domain=default_domain, ip_addresses=[ip])
            for ip in subnet2_ips
        ]
        serial = random.randint(0, 65535)
        dynamic_updates = [
            DynamicDNSUpdate(
                operation="INSERT",
                name=record.name,
                zone=default_domain.name,
                rectype="A",
                ttl=record.address_ttl,
                answer=ip.ip,
            )
            for record in subnet1_records + subnet2_records
            for ip in record.ip_addresses.all()
        ]
        zones = ZoneGenerator(
            [default_domain],
            [subnet1, subnet2],
            serial=serial,
            dynamic_updates=dynamic_updates,
        ).as_list()

        def _generate_mapping_for_network(network, other_network, records):
            mapping = {}
            for record in records:
                ip_set = set(
                    ip.ip
                    for ip in record.ip_addresses.all()
                    if IPAddress(ip.ip) in network
                    and (
                        IPAddress(ip.ip) not in other_network
                        or other_network.prefixlen < network.prefixlen
                    )
                )
                if len(ip_set) > 0:
                    mapping[f"{record.name}.{default_domain.name}"] = (
                        HostnameIPMapping(
                            None,
                            record.address_ttl,
                            ip_set,
                            None,
                            1,
                            None,
                        )
                    )
            return mapping

        expected = [
            DNSForwardZoneConfig(
                default_domain.name,
                mapping={
                    record.name: HostnameIPMapping(
                        None,
                        record.address_ttl,
                        set(ip.ip for ip in record.ip_addresses.all()),
                        None,
                        1,
                        None,
                    )
                    for record in subnet1_records + subnet2_records
                },
                dynamic_updates=dynamic_updates,
            ),
            DNSReverseZoneConfig(
                default_domain.name,
                network=IPNetwork(subnet2.cidr),
                mapping=_generate_mapping_for_network(
                    IPNetwork(subnet2.cidr),
                    IPNetwork(subnet1.cidr),
                    subnet1_records + subnet2_records,
                ),
                dynamic_updates=[
                    DynamicDNSUpdate.as_reverse_record_update(
                        update, IPNetwork(subnet2.cidr)
                    )
                    for update in dynamic_updates
                    if update.answer_as_ip in IPNetwork(subnet2.cidr)
                ],
            ),
            DNSReverseZoneConfig(
                default_domain.name,
                network=IPNetwork(subnet1.cidr),
                mapping=_generate_mapping_for_network(
                    IPNetwork(subnet1.cidr),
                    IPNetwork(subnet2.cidr),
                    subnet1_records + subnet2_records,
                ),
                dynamic_updates=[
                    DynamicDNSUpdate.as_reverse_record_update(
                        update, IPNetwork(subnet1.cidr)
                    )
                    for update in dynamic_updates
                    if update.answer_as_ip in IPNetwork(subnet1.cidr)
                ],
                rfc2317_ranges=set([IPNetwork(subnet2.cidr)]),
            ),
        ]

        for i, zone in enumerate(zones):
            self.assertEqual(zone.domain, expected[i].domain)
            self.assertEqual(zone._network, expected[i]._network)
            self.assertCountEqual(
                zone._mapping,
                expected[i]._mapping,
            )
            self.assertCountEqual(
                zone._dynamic_updates, expected[i]._dynamic_updates
            )
            if isinstance(zone, DNSReverseZoneConfig):
                self.assertCountEqual(
                    zone._dynamic_ranges, expected[i]._dynamic_ranges
                )
                self.assertCountEqual(
                    zone._rfc2317_ranges, expected[i]._rfc2317_ranges
                )


class TestZoneGeneratorTTL(MAASTransactionServerTestCase):
    """Tests for TTL in :class:ZoneGenerator`."""

    @transactional
    def test_domain_ttl_overrides_global(self):
        global_ttl = random.randint(100, 199)
        Config.objects.set_config("default_dns_ttl", global_ttl)
        subnet = factory.make_Subnet(cidr="10.0.0.0/23")
        domain = factory.make_Domain(ttl=random.randint(200, 299))
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY, subnet=subnet, domain=domain
        )
        boot_iface = node.get_boot_interface()
        [boot_ip] = boot_iface.claim_auto_ips()
        expected_forward = {
            node.hostname: HostnameIPMapping(
                node.system_id, domain.ttl, {boot_ip.ip}, node.node_type
            )
        }
        expected_reverse = {
            node.fqdn: HostnameIPMapping(
                node.system_id, domain.ttl, {boot_ip.ip}, node.node_type
            )
        }
        zones = ZoneGenerator(
            domain,
            subnet,
            default_ttl=global_ttl,
            serial=random.randint(0, 65535),
        ).as_list()
        self.assertEqual(expected_forward, zones[0]._mapping)
        self.assertEqual(expected_reverse, zones[1]._mapping)

    @transactional
    def test_node_ttl_overrides_domain(self):
        global_ttl = random.randint(100, 199)
        Config.objects.set_config("default_dns_ttl", global_ttl)
        subnet = factory.make_Subnet(cidr="10.0.0.0/23")
        domain = factory.make_Domain(ttl=random.randint(200, 299))
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY,
            subnet=subnet,
            domain=domain,
            address_ttl=random.randint(300, 399),
        )
        boot_iface = node.get_boot_interface()
        [boot_ip] = boot_iface.claim_auto_ips()
        expected_forward = {
            node.hostname: HostnameIPMapping(
                node.system_id, node.address_ttl, {boot_ip.ip}, node.node_type
            )
        }
        expected_reverse = {
            node.fqdn: HostnameIPMapping(
                node.system_id, node.address_ttl, {boot_ip.ip}, node.node_type
            )
        }
        zones = ZoneGenerator(
            domain,
            subnet,
            default_ttl=global_ttl,
            serial=random.randint(0, 65535),
        ).as_list()
        self.assertEqual(expected_forward, zones[0]._mapping)
        self.assertEqual(expected_reverse, zones[1]._mapping)

    @transactional
    def test_dnsresource_address_does_not_affect_addresses_when_node_set(self):
        # If a node has the same FQDN as a DNSResource, then we use whatever
        # address_ttl there is on the Node (whether None, or not) rather than
        # that on any DNSResource addresses with the same FQDN.
        global_ttl = random.randint(100, 199)
        Config.objects.set_config("default_dns_ttl", global_ttl)
        subnet = factory.make_Subnet(cidr="10.0.0.0/23")
        domain = factory.make_Domain(ttl=random.randint(200, 299))
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY,
            subnet=subnet,
            domain=domain,
            address_ttl=random.randint(300, 399),
        )
        boot_iface = node.get_boot_interface()
        with post_commit_hooks:
            [boot_ip] = boot_iface.claim_auto_ips()
        dnsrr = factory.make_DNSResource(
            name=node.hostname,
            domain=domain,
            address_ttl=random.randint(400, 499),
        )
        ips = {ip.ip for ip in dnsrr.ip_addresses.all() if ip is not None}
        ips.add(boot_ip.ip)
        expected_forward = {
            node.hostname: HostnameIPMapping(
                node.system_id, node.address_ttl, ips, node.node_type, dnsrr.id
            )
        }
        expected_reverse = {
            node.fqdn: HostnameIPMapping(
                node.system_id, node.address_ttl, ips, node.node_type, dnsrr.id
            )
        }
        zones = ZoneGenerator(
            domain,
            subnet,
            default_ttl=global_ttl,
            serial=random.randint(0, 65535),
        ).as_list()
        self.assertEqual(expected_forward, zones[0]._mapping)
        for zone in zones[1:]:
            if ip_set := set(
                ip
                for ip in expected_reverse[node.fqdn].ips
                if IPAddress(ip) in zone._network
            ):
                expected_rev = {
                    node.fqdn: HostnameIPMapping(
                        node.system_id,
                        node.address_ttl,
                        ip_set,
                        node.node_type,
                        dnsrr.id,
                    )
                }
                self.assertEqual(expected_rev, zone._mapping)

    @transactional
    def test_dnsresource_address_overrides_domain(self):
        # DNSResource.address_ttl _does_, however, override Domain.ttl for
        # addresses that do not have nodes associated with them.
        global_ttl = random.randint(100, 199)
        Config.objects.set_config("default_dns_ttl", global_ttl)
        subnet = factory.make_Subnet(cidr="10.0.0.0/23")
        domain = factory.make_Domain(ttl=random.randint(200, 299))
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY,
            subnet=subnet,
            domain=domain,
            address_ttl=random.randint(300, 399),
        )
        boot_iface = node.get_boot_interface()

        with post_commit_hooks:
            [boot_ip] = boot_iface.claim_auto_ips()
        dnsrr = factory.make_DNSResource(
            domain=domain, address_ttl=random.randint(400, 499)
        )
        node_ips = {boot_ip.ip}
        dnsrr_ips = {
            ip.ip for ip in dnsrr.ip_addresses.all() if ip is not None
        }
        expected_forward = {
            node.hostname: HostnameIPMapping(
                node.system_id, node.address_ttl, node_ips, node.node_type
            ),
            dnsrr.name: HostnameIPMapping(
                None, dnsrr.address_ttl, dnsrr_ips, None, dnsrr.id
            ),
        }
        expected_reverse = {
            node.fqdn: HostnameIPMapping(
                node.system_id,
                node.address_ttl,
                node_ips,
                node.node_type,
                None,
            ),
            dnsrr.fqdn: HostnameIPMapping(
                None, dnsrr.address_ttl, dnsrr_ips, None, dnsrr.id
            ),
        }
        zones = ZoneGenerator(
            domain,
            subnet,
            default_ttl=global_ttl,
            serial=random.randint(0, 65535),
        ).as_list()
        self.assertEqual(expected_forward, zones[0]._mapping)

        for zone in zones[1:]:
            expected = {}
            for expected_label, expected_mapping in expected_reverse.items():
                if ip_set := set(
                    ip for ip in expected_mapping.ips if ip in zone._network
                ):
                    expected[expected_label] = HostnameIPMapping(
                        system_id=expected_mapping.system_id,
                        ttl=expected_mapping.ttl,
                        ips=ip_set,
                        node_type=expected_mapping.node_type,
                        dnsresource_id=expected_mapping.dnsresource_id,
                        user_id=expected_mapping.user_id,
                    )
            self.assertEqual(expected, zone._mapping)

    @transactional
    def test_dnsdata_inherits_global(self):
        # If there is no ttl on the DNSData or Domain, then we get the global
        # value.
        global_ttl = random.randint(100, 199)
        Config.objects.set_config("default_dns_ttl", global_ttl)
        subnet = factory.make_Subnet(cidr="10.0.0.0/23")
        domain = factory.make_Domain()
        dnsrr = factory.make_DNSResource(
            no_ip_addresses=True,
            domain=domain,
            address_ttl=random.randint(400, 499),
        )
        dnsdata = factory.make_DNSData(dnsresource=dnsrr)
        expected_forward = {
            dnsrr.name: HostnameRRsetMapping(
                None, {(global_ttl, dnsdata.rrtype, dnsdata.rrdata)}
            )
        }
        zones = ZoneGenerator(
            domain,
            subnet,
            default_ttl=global_ttl,
            serial=random.randint(0, 65535),
        ).as_list()
        self.assertEqual(expected_forward, zones[0]._other_mapping)
        self.assertEqual({}, zones[0]._mapping)
        self.assertEqual({}, zones[1]._mapping)
        self.assertIsNone(dnsdata.ttl)

    @transactional
    def test_dnsdata_inherits_domain(self):
        # If there is no ttl on the DNSData, but is on Domain, then we get the
        # domain value.
        global_ttl = random.randint(100, 199)
        Config.objects.set_config("default_dns_ttl", global_ttl)
        subnet = factory.make_Subnet(cidr="10.0.0.0/23")
        domain = factory.make_Domain(ttl=random.randint(200, 299))
        dnsrr = factory.make_DNSResource(
            no_ip_addresses=True,
            domain=domain,
            address_ttl=random.randint(400, 499),
        )
        dnsdata = factory.make_DNSData(dnsresource=dnsrr)
        expected_forward = {
            dnsrr.name: HostnameRRsetMapping(
                None, {(domain.ttl, dnsdata.rrtype, dnsdata.rrdata)}
            )
        }
        zones = ZoneGenerator(
            domain,
            subnet,
            default_ttl=global_ttl,
            serial=random.randint(0, 65535),
        ).as_list()
        self.assertEqual(expected_forward, zones[0]._other_mapping)
        self.assertEqual({}, zones[0]._mapping)
        self.assertEqual({}, zones[1]._mapping)
        self.assertIsNone(dnsdata.ttl)

    @transactional
    def test_dnsdata_overrides_domain(self):
        # If DNSData has a ttl, we use that in preference to anything else.
        global_ttl = random.randint(100, 199)
        Config.objects.set_config("default_dns_ttl", global_ttl)
        subnet = factory.make_Subnet(cidr="10.0.0.0/23")
        domain = factory.make_Domain(ttl=random.randint(200, 299))
        dnsrr = factory.make_DNSResource(
            no_ip_addresses=True,
            domain=domain,
            address_ttl=random.randint(400, 499),
        )
        dnsdata = factory.make_DNSData(
            dnsresource=dnsrr, ttl=random.randint(500, 599)
        )
        expected_forward = {
            dnsrr.name: HostnameRRsetMapping(
                None, {(dnsdata.ttl, dnsdata.rrtype, dnsdata.rrdata)}
            )
        }
        zones = ZoneGenerator(
            domain,
            subnet,
            default_ttl=global_ttl,
            serial=random.randint(0, 65535),
        ).as_list()
        self.assertEqual(expected_forward, zones[0]._other_mapping)
        self.assertEqual({}, zones[0]._mapping)
        self.assertEqual({}, zones[1]._mapping)

    @transactional
    def test_domain_ttl_overrides_default_ttl(self):
        # If the domain has a ttl, we use that as the default ttl.
        Config.objects.set_config("default_dns_ttl", 42)
        domain = factory.make_Domain(ttl=84)
        [zone_config] = ZoneGenerator(domains=[domain], subnets=[], serial=123)
        self.assertEqual(domain.name, zone_config.domain)
        self.assertEqual(domain.ttl, zone_config.default_ttl)

    @transactional
    def test_none_domain_ttl_doesnt_override_default_ttl(self):
        # If the domain doesn't hae a ttl, the global default ttl is used.
        Config.objects.set_config("default_dns_ttl", 42)
        domain = factory.make_Domain(ttl=None)
        [zone_config] = ZoneGenerator(domains=[domain], subnets=[], serial=123)
        self.assertEqual(domain.name, zone_config.domain)
        self.assertEqual(42, zone_config.default_ttl)


class TestZoneGeneratorEndToEnd(MAASServerTestCase):
    def _find_most_specific_subnet(
        self, ip: StaticIPAddress, subnets: list[Subnet]
    ):
        networks = []
        for subnet in subnets:
            net = IPNetwork(subnet.cidr)
            if net.prefixlen < 24:
                networks += ZoneGenerator._split_large_subnet(net)
            else:
                networks.append(net)
        sorted_nets = sorted(networks, key=lambda net: -1 * net.prefixlen)
        for net in sorted_nets:
            if IPAddress(ip.ip) in net:
                return net

    def test_ZoneGenerator_generates_config_for_zone_files(self):
        config_path = patch_zone_file_config_path(self)
        default_domain = Domain.objects.get_default_domain()
        domain = factory.make_Domain()
        subnet1 = factory.make_Subnet(cidr="10.0.1.0/24")
        subnet2 = factory.make_Subnet(cidr="10.0.0.0/22")
        subnet3 = factory.make_Subnet(cidr="10.0.1.0/27")
        subnet1_ips = [
            factory.make_StaticIPAddress(
                ip=factory.pick_ip_in_Subnet(subnet1), subnet=subnet1
            )
            for _ in range(3)
        ]
        subnet2_ips = [
            factory.make_StaticIPAddress(
                ip=factory.pick_ip_in_Subnet(
                    subnet2, but_not=list(subnet1.get_ipranges_in_use())
                ),
                subnet=subnet2,
            )
            for _ in range(3)
        ]
        subnet3_ips = [
            factory.make_StaticIPAddress(
                ip=factory.pick_ip_in_Subnet(
                    subnet3,
                    but_not=list(subnet1.get_ipranges_in_use())
                    + list(subnet2.get_ipranges_in_use()),
                ),
                subnet=subnet3,
            )
            for _ in range(3)
        ]
        subnet1_records = [
            factory.make_DNSResource(
                domain=random.choice((default_domain, domain)),
                ip_addresses=[ip],
            )
            for ip in subnet1_ips
        ]
        subnet2_records = [
            factory.make_DNSResource(
                domain=random.choice((default_domain, domain)),
                ip_addresses=[ip],
            )
            for ip in subnet2_ips
        ]
        subnet3_records = [
            factory.make_DNSResource(
                domain=random.choice((default_domain, domain)),
                ip_addresses=[ip],
            )
            for ip in subnet3_ips
        ]
        all_records = subnet1_records + subnet2_records + subnet3_records
        zones = ZoneGenerator(
            [default_domain, domain],
            [subnet1, subnet2, subnet3],
            serial=random.randint(0, 65535),
        ).as_list()
        for zone in zones:
            zone.write_config()

        # check forward zones
        with open(
            os.path.join(config_path, f"zone.{default_domain.name}"), "r"
        ) as zf:
            default_domain_contents = zf.read()

        with open(os.path.join(config_path, f"zone.{domain.name}"), "r") as zf:
            domain_contents = zf.read()

        for record in all_records:
            if record.domain == default_domain:
                contents = default_domain_contents
            else:
                contents = domain_contents

            self.assertIn(
                f"{record.name} 30 IN A {record.ip_addresses.first().ip}",
                contents,
            )

        # check reverse zones
        for record in all_records:
            ip = record.ip_addresses.first()
            subnet = self._find_most_specific_subnet(
                ip, [subnet1, subnet2, subnet3]
            )
            rev_subnet = ".".join(str(subnet.network).split(".")[2::-1])
            if subnet.prefixlen > 24:
                rev_subnet = f"{str(subnet.network).split('.')[-1]}-{subnet.prefixlen}.{rev_subnet}"
            with open(
                os.path.join(config_path, f"zone.{rev_subnet}.in-addr.arpa"),
                "r",
            ) as zf:
                contents = zf.read()
                self.assertIn(
                    f"{ip.ip.split('.')[-1]} 30 IN PTR {record.fqdn}",
                    contents,
                    f"{subnet} {ip.ip}",
                )
