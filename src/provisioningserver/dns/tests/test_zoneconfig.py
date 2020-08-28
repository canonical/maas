# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for BIND zone config generation."""

__all__ = []

from itertools import chain
import os.path
import random

from netaddr import IPAddress, IPNetwork, IPRange
from testtools.matchers import (
    Contains,
    ContainsAll,
    Equals,
    FileContains,
    HasLength,
    MatchesStructure,
)
from twisted.python.filepath import FilePath

from maastesting.factory import factory
from maastesting.matchers import MockNotCalled
from maastesting.testcase import MAASTestCase
from provisioningserver.dns.config import get_dns_config_dir
from provisioningserver.dns.testing import patch_dns_config_path
from provisioningserver.dns.zoneconfig import (
    DNSForwardZoneConfig,
    DNSReverseZoneConfig,
    DomainInfo,
)


class HostnameIPMapping:
    """This is used to return address information for a host in a way that
    keeps life simple for the callers."""

    def __init__(self, system_id=None, ttl=None, ips=frozenset()):
        self.system_id = system_id
        self.ttl = ttl
        self.ips = ips.copy()

    def __repr__(self):
        return "HostnameIPMapping(%r, %r, %r, %r)" % (
            self.system_id,
            self.ttl,
            self.ips,
            self.node_type,
        )

    def __eq__(self, other):
        return self.__dict__ == other.__dict__


class HostnameRRsetMapping:
    """This is used to return non-address information for a hostname in a way
    that keeps life simple for the allers.  Rrset is a set of (ttl, rrtype,
    rrdata) tuples."""

    def __init__(self, system_id=None, rrset=frozenset()):
        self.system_id = system_id
        self.rrset = rrset.copy()

    def __repr__(self):
        return "HostnameRRSetMapping(%r, %r, %r)" % (
            self.system_id,
            self.rrset,
            self.node_type,
        )

    def __eq__(self, other):
        return self.__dict__ == other.__dict__


class TestDNSForwardZoneConfig(MAASTestCase):
    """Tests for DNSForwardZoneConfig."""

    def test_fields(self):
        domain = factory.make_string()
        serial = random.randint(1, 200)
        hostname = factory.make_string()
        network = factory.make_ipv4_network()
        ip = factory.pick_ip_in_network(network)
        default_ttl = random.randint(10, 300)
        mapping = {hostname: [ip]}
        dns_zone_config = DNSForwardZoneConfig(
            domain, serial=serial, default_ttl=default_ttl, mapping=mapping
        )
        self.assertThat(
            dns_zone_config,
            MatchesStructure.byEquality(
                domain=domain,
                serial=serial,
                _mapping=mapping,
                default_ttl=default_ttl,
            ),
        )

    def test_computes_dns_config_file_paths(self):
        domain = factory.make_name("zone")
        dns_zone_config = DNSForwardZoneConfig(domain)
        self.assertEqual(
            os.path.join(get_dns_config_dir(), "zone.%s" % domain),
            dns_zone_config.zone_info[0].target_path,
        )

    def test_get_a_mapping_returns_ipv4_mapping(self):
        ttl = random.randint(10, 300)
        ns_ttl = random.randint(10, 300)
        ipv4_mapping = {
            factory.make_name("host"): HostnameIPMapping(
                None, ttl, [factory.make_ipv4_address()]
            ),
            factory.make_name("host"): HostnameIPMapping(
                None, ttl, [factory.make_ipv4_address()]
            ),
        }
        ipv6_mapping = {
            factory.make_name("host"): HostnameIPMapping(
                None, ttl, [factory.make_ipv6_address()]
            ),
            factory.make_name("host"): HostnameIPMapping(
                None, ttl, [factory.make_ipv6_address()]
            ),
        }
        combined_mapping = {
            hostname: value
            for hostname, value in chain(
                ipv4_mapping.items(), ipv6_mapping.items()
            )
        }
        expected = [
            (n, info.ttl, ip)
            for n, info in ipv4_mapping.items()
            for ip in info.ips
        ]
        expect = [(n, t, ip) for n, t, ip in expected]
        actual = DNSForwardZoneConfig.get_A_mapping(combined_mapping, ns_ttl)
        self.assertItemsEqual(expect, actual)

    def test_get_aaaa_mapping_returns_ipv6_mapping(self):
        ttl = random.randint(10, 300)
        ns_ttl = random.randint(10, 300)
        ipv4_mapping = {
            factory.make_name("host"): HostnameIPMapping(
                None, ttl, {factory.make_ipv4_address()}
            ),
            factory.make_name("host"): HostnameIPMapping(
                None, ttl, {factory.make_ipv4_address()}
            ),
        }
        ipv6_mapping = {
            factory.make_name("host"): HostnameIPMapping(
                None, ttl, {factory.make_ipv6_address()}
            ),
            factory.make_name("host"): HostnameIPMapping(
                None, ttl, {factory.make_ipv6_address()}
            ),
        }
        combined_mapping = {
            hostname: value
            for hostname, value in chain(
                ipv4_mapping.items(), ipv6_mapping.items()
            )
        }
        self.assertItemsEqual(
            [
                (n, info.ttl, ip)
                for n, info in ipv6_mapping.items()
                for ip in info.ips
            ],
            DNSForwardZoneConfig.get_AAAA_mapping(combined_mapping, ns_ttl),
        )

    def test_handles_slash_32_dynamic_range(self):
        target_dir = patch_dns_config_path(self)
        domain = factory.make_string()
        network = factory.make_ipv4_network()
        ipv4_hostname = factory.make_name("host")
        ipv4_ip = factory.pick_ip_in_network(network)
        range_ip = factory.pick_ip_in_network(network, but_not={ipv4_ip})
        ipv6_hostname = factory.make_name("host")
        ipv6_ip = factory.make_ipv6_address()
        ttl = random.randint(10, 300)
        mapping = {
            ipv4_hostname: HostnameIPMapping(None, ttl, {ipv4_ip}),
            ipv6_hostname: HostnameIPMapping(None, ttl, {ipv6_ip}),
        }
        dynamic_range = IPRange(IPAddress(range_ip), IPAddress(range_ip))
        expected_generate_directives = (
            DNSForwardZoneConfig.get_GENERATE_directives(dynamic_range)
        )
        other_mapping = {
            ipv4_hostname: HostnameRRsetMapping(None, {(ttl, "MX", "10 bar")})
        }
        dns_zone_config = DNSForwardZoneConfig(
            domain,
            serial=random.randint(1, 100),
            other_mapping=other_mapping,
            default_ttl=ttl,
            mapping=mapping,
            dynamic_ranges=[dynamic_range],
        )
        dns_zone_config.write_config()
        self.assertThat(
            os.path.join(target_dir, "zone.%s" % domain),
            FileContains(
                matcher=ContainsAll(
                    [
                        "$TTL %d" % ttl,
                        "%s %d IN A %s" % (ipv4_hostname, ttl, ipv4_ip),
                        "%s %d IN AAAA %s" % (ipv6_hostname, ttl, ipv6_ip),
                        "%s %d IN MX 10 bar" % (ipv4_hostname, ttl),
                    ]
                    + [
                        "$GENERATE %s %s IN A %s"
                        % (iterator_values, reverse_dns, hostname)
                        for iterator_values, reverse_dns, hostname in expected_generate_directives
                    ]
                )
            ),
        )

    def test_writes_dns_zone_config(self):
        target_dir = patch_dns_config_path(self)
        domain = factory.make_string()
        network = factory.make_ipv4_network()
        ipv4_hostname = factory.make_name("host")
        ipv4_ip = factory.pick_ip_in_network(network)
        ipv6_hostname = factory.make_name("host")
        ipv6_ip = factory.make_ipv6_address()
        ttl = random.randint(10, 300)
        mapping = {
            ipv4_hostname: HostnameIPMapping(None, ttl, {ipv4_ip}),
            ipv6_hostname: HostnameIPMapping(None, ttl, {ipv6_ip}),
        }
        expected_generate_directives = (
            DNSForwardZoneConfig.get_GENERATE_directives(network)
        )
        other_mapping = {
            ipv4_hostname: HostnameRRsetMapping(None, {(ttl, "MX", "10 bar")})
        }
        dns_zone_config = DNSForwardZoneConfig(
            domain,
            serial=random.randint(1, 100),
            other_mapping=other_mapping,
            default_ttl=ttl,
            mapping=mapping,
            dynamic_ranges=[IPRange(network.first, network.last)],
        )
        dns_zone_config.write_config()
        self.assertThat(
            os.path.join(target_dir, "zone.%s" % domain),
            FileContains(
                matcher=ContainsAll(
                    [
                        "$TTL %d" % ttl,
                        "%s %d IN A %s" % (ipv4_hostname, ttl, ipv4_ip),
                        "%s %d IN AAAA %s" % (ipv6_hostname, ttl, ipv6_ip),
                        "%s %d IN MX 10 bar" % (ipv4_hostname, ttl),
                    ]
                    + [
                        "$GENERATE %s %s IN A %s"
                        % (iterator_values, reverse_dns, hostname)
                        for iterator_values, reverse_dns, hostname in expected_generate_directives
                    ]
                )
            ),
        )

    def test_writes_dns_zone_config_with_NS_record(self):
        target_dir = patch_dns_config_path(self)
        addr_ttl = random.randint(10, 100)
        ns_host_name = factory.make_name("ns")
        dns_zone_config = DNSForwardZoneConfig(
            factory.make_string(),
            serial=random.randint(1, 100),
            ns_host_name=ns_host_name,
            ipv4_ttl=addr_ttl,
            ipv6_ttl=addr_ttl,
        )
        dns_zone_config.write_config()
        self.assertThat(
            os.path.join(target_dir, "zone.%s" % dns_zone_config.domain),
            FileContains(matcher=ContainsAll(["30 IN NS %s." % ns_host_name])),
        )

    def test_ignores_generate_directives_for_v6_dynamic_ranges(self):
        patch_dns_config_path(self)
        domain = factory.make_string()
        network = factory.make_ipv4_network()
        ipv4_hostname = factory.make_name("host")
        ipv4_ip = factory.pick_ip_in_network(network)
        ipv6_hostname = factory.make_name("host")
        ipv6_ip = factory.make_ipv6_address()
        ipv6_network = factory.make_ipv6_network()
        dynamic_range = IPRange(ipv6_network.first, ipv6_network.last)
        ttl = random.randint(10, 300)
        mapping = {
            ipv4_hostname: HostnameIPMapping(None, ttl, {ipv4_ip}),
            ipv6_hostname: HostnameIPMapping(None, ttl, {ipv6_ip}),
        }
        dns_zone_config = DNSForwardZoneConfig(
            domain,
            serial=random.randint(1, 100),
            mapping=mapping,
            default_ttl=ttl,
            dynamic_ranges=[dynamic_range],
        )
        get_generate_directives = self.patch(
            dns_zone_config, "get_GENERATE_directives"
        )
        dns_zone_config.write_config()
        self.assertThat(get_generate_directives, MockNotCalled())

    def test_config_file_is_world_readable(self):
        patch_dns_config_path(self)
        dns_zone_config = DNSForwardZoneConfig(
            factory.make_string(), serial=random.randint(1, 100)
        )
        dns_zone_config.write_config()
        filepath = FilePath(dns_zone_config.zone_info[0].target_path)
        self.assertTrue(filepath.getPermissions().other.read)


class TestDNSReverseZoneConfig(MAASTestCase):
    """Tests for DNSReverseZoneConfig."""

    def test_fields(self):
        domain = factory.make_string()
        serial = random.randint(1, 200)
        network = factory.make_ipv4_network()
        dns_zone_config = DNSReverseZoneConfig(
            domain, serial=serial, network=network
        )
        self.assertThat(
            dns_zone_config,
            MatchesStructure.byEquality(
                domain=domain, serial=serial, _network=network
            ),
        )

    def test_computes_dns_config_file_paths(self):
        domain = factory.make_name("zone")
        reverse_file_name = [
            "zone.%d.168.192.in-addr.arpa" % i for i in range(4)
        ]
        dns_zone_config = DNSReverseZoneConfig(
            domain, network=IPNetwork("192.168.0.0/22")
        )
        for i in range(4):
            self.assertEqual(
                os.path.join(get_dns_config_dir(), reverse_file_name[i]),
                dns_zone_config.zone_info[i].target_path,
            )

    def test_computes_dns_config_file_paths_for_small_network(self):
        domain = factory.make_name("zone")
        reverse_file_name = "zone.192-27.0.168.192.in-addr.arpa"
        dns_zone_config = DNSReverseZoneConfig(
            domain, network=IPNetwork("192.168.0.192/27")
        )
        self.assertEqual(1, len(dns_zone_config.zone_info))
        self.assertEqual(
            os.path.join(get_dns_config_dir(), reverse_file_name),
            dns_zone_config.zone_info[0].target_path,
        )

    def test_reverse_zone_file(self):
        # DNSReverseZoneConfig calculates the reverse zone file name
        # correctly for IPv4 and IPv6 networks.
        # As long as the network size ends on a "nice" boundary (multiple of
        # 8 for IPv4, multiple of 4 for IPv6), then there will be one reverse
        # zone for the subnet.  When it isn't, then there will be 2-128
        # individual reverse zones for the subnet.
        # A special case is the small subnet (less than 256 hosts for IPv4,
        # less than 16 hosts for IPv6), in which case, we follow RFC2317 with
        # the modern adjustment of using '-' instead of '/'.
        zn = "%d.0.0.0.0.0.0.0.0.0.0.0.4.0.1.f.1.0.8.a.b.0.1.0.0.2.ip6.arpa"
        expected = [
            # IPv4 networks.
            # /22 ==> 4 /24 reverse zones
            (
                IPNetwork("192.168.0.1/22"),
                [
                    DomainInfo(
                        IPNetwork("192.168.%d.0/24" % i),
                        "%d.168.192.in-addr.arpa" % i,
                    )
                    for i in range(4)
                ],
            ),
            # /24 ==> 1 reverse zone
            (
                IPNetwork("192.168.0.1/24"),
                [
                    DomainInfo(
                        IPNetwork("192.168.0.0/24"), "0.168.192.in-addr.arpa"
                    )
                ],
            ),
            # /29 ==> 1 reverse zones, per RFC2317
            (
                IPNetwork("192.168.0.241/29"),
                [
                    DomainInfo(
                        IPNetwork("192.168.0.240/29"),
                        "240-29.0.168.192.in-addr.arpa",
                    )
                ],
            ),
            # IPv6 networks.
            # /32, 48, 56, 64 ==> 1 reverse zones
            (
                IPNetwork("3ffe:801::/32"),
                [
                    DomainInfo(
                        IPNetwork("3ffe:801::32"), "1.0.8.0.e.f.f.3.ip6.arpa"
                    )
                ],
            ),
            (
                IPNetwork("2001:db8:0::/48"),
                [
                    DomainInfo(
                        IPNetwork("2001:db8:0::/48"),
                        "0.0.0.0.8.b.d.0.1.0.0.2.ip6.arpa",
                    )
                ],
            ),
            (
                IPNetwork("2001:ba8:1f1:400::/56"),
                [
                    DomainInfo(
                        IPNetwork("2001:ba8:1f1:400::/56"),
                        "4.0.1.f.1.0.8.a.b.0.1.0.0.2.ip6.arpa",
                    )
                ],
            ),
            (
                IPNetwork("2610:8:6800:1::/64"),
                [
                    DomainInfo(
                        IPNetwork("2610:8:6800:1::/64"),
                        "1.0.0.0.0.0.8.6.8.0.0.0.0.1.6.2.ip6.arpa",
                    )
                ],
            ),
            # /2 with hex digits ==> 4 /4 reverse zones
            (
                IPNetwork("8000::/2"),
                [
                    DomainInfo(IPNetwork("8000::/4"), "8.ip6.arpa"),
                    DomainInfo(IPNetwork("9000::/4"), "9.ip6.arpa"),
                    DomainInfo(IPNetwork("a000::/4"), "a.ip6.arpa"),
                    DomainInfo(IPNetwork("b000::/4"), "b.ip6.arpa"),
                ],
            ),
            # /103 ==> 2 /104 reverse zones
            (
                IPNetwork("2001:ba8:1f1:400::/103"),
                [
                    DomainInfo(
                        IPNetwork("2001:ba8:1f1:400:0:0:%d00:0000/104" % i),
                        zn % i,
                    )
                    for i in range(2)
                ],
            ),
            # /125 ==> 1 reverse zone, based on RFC2317
            (
                IPNetwork("2001:ba8:1f1:400::/125"),
                [
                    DomainInfo(
                        IPNetwork("2001:ba8:1f1:400::/125"),
                        "0-125.%s"
                        % (IPAddress("2001:ba8:1f1:400::").reverse_dns[2:-1]),
                    )
                ],
            ),
        ]
        results = []
        for network, _ in expected:
            domain = factory.make_name("zone")
            dns_zone_config = DNSReverseZoneConfig(domain, network=network)
            results.append((network, dns_zone_config.zone_info))
        # Make sure we have the right number of elements.
        self.assertEqual(len(expected), len(results))
        # And that the zone names chosen for each element are correct.
        for net in range(len(expected)):
            for zi in range(len(expected[net][1])):
                self.assertItemsEqual(
                    expected[net][1][zi].zone_name,
                    results[net][1][zi].zone_name,
                )

    def test_get_ptr_mapping(self):
        name = factory.make_string()
        network = IPNetwork("192.12.0.1/30")
        hosts = {
            factory.make_string(): factory.pick_ip_in_network(network),
            factory.make_string(): factory.pick_ip_in_network(network),
        }
        expected = [
            (
                IPAddress(ip).reverse_dns.split(".")[0],
                30,
                "%s.%s." % (hostname, name),
            )
            for hostname, ip in hosts.items()
        ]
        mapping = {
            "%s.%s" % (hostname, name): HostnameIPMapping(None, 30, {ip})
            for hostname, ip in hosts.items()
        }
        self.assertItemsEqual(
            expected, DNSReverseZoneConfig.get_PTR_mapping(mapping, network)
        )

    def test_get_ptr_mapping_drops_IPs_not_in_network(self):
        name = factory.make_string()
        network = IPNetwork("192.12.0.1/30")
        in_network_mapping = {
            factory.make_string(): factory.pick_ip_in_network(network),
            factory.make_string(): factory.pick_ip_in_network(network),
        }
        expected = [
            (
                IPAddress(ip).reverse_dns.split(".")[0],
                30,
                "%s.%s." % (hostname, name),
            )
            for hostname, ip in in_network_mapping.items()
        ]
        mapping = {
            "%s.%s" % (hostname, name): HostnameIPMapping(None, 30, [ip])
            for hostname, ip in in_network_mapping.items()
        }
        extra_mapping = {
            factory.make_string(): HostnameIPMapping(None, 30, ["192.50.0.2"]),
            factory.make_string(): HostnameIPMapping(None, 30, ["192.70.0.2"]),
        }
        mapping.update(extra_mapping)
        self.assertItemsEqual(
            expected, DNSReverseZoneConfig.get_PTR_mapping(mapping, network)
        )

    def test_writes_dns_zone_config_with_NS_record(self):
        target_dir = patch_dns_config_path(self)
        network = factory.make_ipv4_network()
        ns_host_name = factory.make_name("ns")
        dns_zone_config = DNSReverseZoneConfig(
            factory.make_string(),
            serial=random.randint(1, 100),
            ns_host_name=ns_host_name,
            network=network,
        )
        dns_zone_config.write_config()
        for zone_name in [zi.zone_name for zi in dns_zone_config.zone_info]:
            self.assertThat(
                os.path.join(target_dir, "zone.%s" % zone_name),
                FileContains(matcher=Contains("30 IN NS %s." % ns_host_name)),
            )

    def test_writes_reverse_dns_zone_config(self):
        target_dir = patch_dns_config_path(self)
        domain = factory.make_string()
        ns_host_name = factory.make_name("ns")
        network = IPNetwork("192.168.0.1/22")
        dynamic_network = IPNetwork("192.168.0.1/28")
        dns_zone_config = DNSReverseZoneConfig(
            domain,
            serial=random.randint(1, 100),
            network=network,
            ns_host_name=ns_host_name,
            dynamic_ranges=[
                IPRange(dynamic_network.first, dynamic_network.last)
            ],
        )
        dns_zone_config.write_config()
        for sub in range(4):
            reverse_file_name = "zone.%d.168.192.in-addr.arpa" % sub
            expected_GEN_direct = dns_zone_config.get_GENERATE_directives(
                dynamic_network,
                domain,
                DomainInfo(
                    IPNetwork("192.168.%d.0/24" % sub),
                    "%d.168.192.in-addr.arpa" % sub,
                ),
            )
            expected = ContainsAll(
                ["30 IN NS %s." % ns_host_name]
                + [
                    "$GENERATE %s %s IN PTR %s"
                    % (iterator_values, reverse_dns, hostname)
                    for iterator_values, reverse_dns, hostname in expected_GEN_direct
                ]
            )
            self.assertThat(
                os.path.join(target_dir, reverse_file_name),
                FileContains(matcher=expected),
            )

    def test_writes_reverse_dns_zone_config_for_small_network(self):
        target_dir = patch_dns_config_path(self)
        domain = factory.make_string()
        ns_host_name = factory.make_name("ns")
        network = IPNetwork("192.168.0.1/26")
        dynamic_network = IPNetwork("192.168.0.1/28")
        dns_zone_config = DNSReverseZoneConfig(
            domain,
            serial=random.randint(1, 100),
            network=network,
            ns_host_name=ns_host_name,
            dynamic_ranges=[
                IPRange(dynamic_network.first, dynamic_network.last)
            ],
        )
        dns_zone_config.write_config()
        reverse_zone_name = "0-26.0.168.192.in-addr.arpa"
        reverse_file_name = "zone.0-26.0.168.192.in-addr.arpa"
        expected_GEN_direct = dns_zone_config.get_GENERATE_directives(
            dynamic_network, domain, DomainInfo(network, reverse_zone_name)
        )
        expected = ContainsAll(
            ["30 IN NS %s." % ns_host_name]
            + [
                "$GENERATE %s %s IN PTR %s"
                % (iterator_values, reverse_dns, hostname)
                for iterator_values, reverse_dns, hostname in expected_GEN_direct
            ]
        )
        self.assertThat(
            os.path.join(target_dir, reverse_file_name),
            FileContains(matcher=expected),
        )

    def test_ignores_generate_directives_for_v6_dynamic_ranges(self):
        patch_dns_config_path(self)
        domain = factory.make_string()
        network = IPNetwork("192.168.0.1/22")
        dynamic_network = IPNetwork("%s/64" % factory.make_ipv6_address())
        dns_zone_config = DNSReverseZoneConfig(
            domain,
            serial=random.randint(1, 100),
            network=network,
            dynamic_ranges=[
                IPRange(dynamic_network.first, dynamic_network.last)
            ],
        )
        get_generate_directives = self.patch(
            dns_zone_config, "get_GENERATE_directives"
        )
        dns_zone_config.write_config()
        self.assertThat(get_generate_directives, MockNotCalled())

    def test_reverse_config_file_is_world_readable(self):
        patch_dns_config_path(self)
        dns_zone_config = DNSReverseZoneConfig(
            factory.make_string(),
            serial=random.randint(1, 100),
            network=factory.make_ipv4_network(),
        )
        dns_zone_config.write_config()
        for tgt in [zi.target_path for zi in dns_zone_config.zone_info]:
            filepath = FilePath(tgt)
            self.assertTrue(filepath.getPermissions().other.read)


class TestDNSReverseZoneConfig_GetGenerateDirectives(MAASTestCase):
    """Tests for `DNSReverseZoneConfig.get_GENERATE_directives()`."""

    def test_excplicitly(self):
        # The other tests in this TestCase rely on
        # get_expected_generate_directives(), which is quite dense. Here
        # we test get_GENERATE_directives() explicitly.
        ip_range = IPRange("192.168.0.55", "192.168.2.128")
        expected_directives = [
            ("55-255", "$.0.168.192.in-addr.arpa.", "192-168-0-$.domain."),
            ("0-255", "$.1.168.192.in-addr.arpa.", "192-168-1-$.domain."),
            ("0-128", "$.2.168.192.in-addr.arpa.", "192-168-2-$.domain."),
        ]
        self.assertItemsEqual(
            expected_directives,
            DNSReverseZoneConfig.get_GENERATE_directives(
                ip_range,
                domain="domain",
                zone_info=DomainInfo(
                    IPNetwork("192.168.0.0/16"), "168.192.in-addr.arpa"
                ),
            ),
        )

    def get_expected_generate_directives(self, network, domain):
        ip_parts = network.network.format().split(".")
        relevant_ip_parts = ip_parts[:-2]

        first_address = IPAddress(network.first).format()
        first_address_parts = first_address.split(".")

        if network.size < 256:
            last_address = IPAddress(network.last).format()
            iterator_low = int(first_address_parts[-1])
            iterator_high = last_address.split(".")[-1]
        else:
            iterator_low = 0
            iterator_high = 255

        second_octet_offset = int(first_address_parts[-2])
        expected_generate_directives = []
        directives_needed = network.size // 256

        if directives_needed == 0:
            directives_needed = 1
        for num in range(directives_needed):
            expected_address_base = "%s-%s" % tuple(relevant_ip_parts)
            expected_address = "%s-%s-$" % (
                expected_address_base,
                num + second_octet_offset,
            )
            relevant_ip_parts.reverse()
            expected_rdns_base = "%s.%s.in-addr.arpa." % tuple(
                relevant_ip_parts
            )
            if network.size >= 256:
                expected_rdns_template = "$.%s.%s" % (
                    num + second_octet_offset,
                    expected_rdns_base,
                )
            else:
                expected_rdns_template = "$"
            expected_generate_directives.append(
                (
                    "%s-%s" % (iterator_low, iterator_high),
                    expected_rdns_template,
                    "%s.%s." % (expected_address, domain),
                )
            )
            relevant_ip_parts.reverse()
        return expected_generate_directives

    def test_returns_single_entry_for_slash_24_network(self):
        network = IPNetwork("%s/24" % factory.make_ipv4_address())
        reverse = ".".join(IPAddress(network).reverse_dns.split(".")[1:-1])
        domain = factory.make_string()
        expected_generate_directives = self.get_expected_generate_directives(
            network, domain
        )
        directives = DNSReverseZoneConfig.get_GENERATE_directives(
            network, domain, DomainInfo(network, reverse)
        )
        self.expectThat(directives, HasLength(1))
        self.assertItemsEqual(expected_generate_directives, directives)

    def test_returns_single_entry_for_tiny_network(self):
        network = IPNetwork("%s/28" % factory.make_ipv4_address())
        reverse = IPAddress(network).reverse_dns.split(".")
        reverse = ".".join(["%s-28" % reverse[0]] + reverse[1:-1])
        domain = factory.make_string()

        expected_generate_directives = self.get_expected_generate_directives(
            network, domain
        )
        directives = DNSReverseZoneConfig.get_GENERATE_directives(
            network, domain, DomainInfo(network, reverse)
        )
        self.expectThat(directives, HasLength(1))
        self.assertItemsEqual(expected_generate_directives, directives)

    def test_returns_single_entry_for_weird_small_range(self):
        ip_range = IPRange("10.0.0.1", "10.0.0.255")
        domain = factory.make_string()
        directives = DNSReverseZoneConfig.get_GENERATE_directives(
            ip_range,
            domain,
            DomainInfo(IPNetwork("10.0.0.0/24"), "0.0.10.in-addr.arpa"),
        )
        self.expectThat(directives, HasLength(1))

    # generate 2 zones, rather than 1 zone with 2 GENERATEs.
    def test_returns_256_entries_for_slash_16_network(self):
        network = IPNetwork(factory.make_ipv4_network(slash=16))
        reverse = IPAddress(network.first).reverse_dns.split(".")[2:-1]
        reverse = ".".join(reverse)
        domain = factory.make_string()

        expected_generate_directives = self.get_expected_generate_directives(
            network, domain
        )
        directives = DNSReverseZoneConfig.get_GENERATE_directives(
            network, domain, DomainInfo(network, reverse)
        )
        self.expectThat(directives, HasLength(256))
        self.assertItemsEqual(expected_generate_directives, directives)

    def test_ignores_network_larger_than_slash_16(self):
        network = IPNetwork("%s/15" % factory.make_ipv4_address())
        self.assertEqual(
            [],
            DNSReverseZoneConfig.get_GENERATE_directives(
                network,
                factory.make_string(),
                DomainInfo(network, "do not care"),
            ),
        )

    def test_ignores_networks_that_span_slash_16s(self):
        # If the upper and lower bounds of a range span two /16 networks
        # (but contain between them no more than 65536 addresses),
        # get_GENERATE_directives() will return early
        ip_range = IPRange("10.0.0.55", "10.1.0.54")
        directives = DNSReverseZoneConfig.get_GENERATE_directives(
            ip_range,
            factory.make_string(),
            DomainInfo(IPNetwork("10.0.0.0/15"), "do not care"),
        )
        self.assertEqual([], directives)

    def test_sorts_output_by_hostname(self):
        network = IPNetwork("10.0.0.1/23")
        domain = factory.make_string()

        expected_hostname = "10-0-%s-$." + domain + "."
        expected_rdns = "$.%s.0.10.in-addr.arpa."

        directives = list(
            DNSReverseZoneConfig.get_GENERATE_directives(
                network,
                domain,
                DomainInfo(IPNetwork("10.0.0.0/24"), "0.0.10.in-addr.arpa"),
            )
        )
        self.expectThat(
            directives[0],
            Equals(("0-255", expected_rdns % "0", expected_hostname % "0")),
        )

        expected_hostname = "10-0-%s-$." + domain + "."
        expected_rdns = "$.%s.0.10.in-addr.arpa."
        directives = list(
            DNSReverseZoneConfig.get_GENERATE_directives(
                network,
                domain,
                DomainInfo(IPNetwork("10.0.1.0/24"), "1.0.10.in-addr.arpa"),
            )
        )
        self.expectThat(
            directives[0],
            Equals(("0-255", expected_rdns % "1", expected_hostname % "1")),
        )


class TestDNSForwardZoneConfig_GetGenerateDirectives(MAASTestCase):
    """Tests for `DNSForwardZoneConfig.get_GENERATE_directives()`."""

    def test_excplicitly(self):
        # The other tests in this TestCase rely on
        # get_expected_generate_directives(), which is quite dense. Here
        # we test get_GENERATE_directives() explicitly.
        ip_range = IPRange("192.168.0.55", "192.168.2.128")
        expected_directives = [
            ("55-255", "192-168-0-$", "192.168.0.$"),
            ("0-255", "192-168-1-$", "192.168.1.$"),
            ("0-128", "192-168-2-$", "192.168.2.$"),
        ]
        self.assertItemsEqual(
            expected_directives,
            DNSForwardZoneConfig.get_GENERATE_directives(ip_range),
        )

    def get_expected_generate_directives(self, network):
        ip_parts = network.network.format().split(".")
        ip_parts[-1] = "$"
        expected_hostname = "%s" % "-".join(ip_parts)
        expected_address = ".".join(ip_parts)

        first_address = IPAddress(network.first).format()
        first_address_parts = first_address.split(".")
        last_address = IPAddress(network.last).format()
        last_address_parts = last_address.split(".")

        if network.size < 256:
            iterator_low = int(first_address_parts[-1])
            iterator_high = int(last_address_parts[-1])
        else:
            iterator_low = 0
            iterator_high = 255

        expected_iterator_values = "%s-%s" % (iterator_low, iterator_high)

        directives_needed = network.size // 256
        if directives_needed == 0:
            directives_needed = 1
        expected_directives = []
        for num in range(directives_needed):
            ip_parts[-2] = str(num + int(ip_parts[-2]))
            expected_address = ".".join(ip_parts)
            expected_hostname = "%s" % "-".join(ip_parts)
            expected_directives.append(
                (expected_iterator_values, expected_hostname, expected_address)
            )
        return expected_directives

    def test_returns_single_entry_for_slash_24_network(self):
        network = IPNetwork("%s/24" % factory.make_ipv4_address())
        expected_directives = self.get_expected_generate_directives(network)
        directives = DNSForwardZoneConfig.get_GENERATE_directives(network)
        self.expectThat(directives, HasLength(1))
        self.assertItemsEqual(expected_directives, directives)

    def test_returns_single_entry_for_tiny_network(self):
        network = IPNetwork("%s/31" % factory.make_ipv4_address())

        expected_directives = self.get_expected_generate_directives(network)
        directives = DNSForwardZoneConfig.get_GENERATE_directives(network)
        self.assertEqual(1, len(expected_directives))
        self.assertItemsEqual(expected_directives, directives)

    def test_returns_two_entries_for_slash_23_network(self):
        network = IPNetwork("%s/23" % factory.make_ipv4_address())

        expected_directives = self.get_expected_generate_directives(network)
        directives = DNSForwardZoneConfig.get_GENERATE_directives(network)
        self.assertEqual(2, len(expected_directives))
        self.assertItemsEqual(expected_directives, directives)

    def test_dtrt_for_larger_networks(self):
        # For every other network size that we're not explicitly
        # testing here,
        # DNSForwardZoneConfig.get_GENERATE_directives() will return
        # one GENERATE directive for every 255 addresses in the network.
        for prefixlen in range(23, 16):
            network = IPNetwork(
                "%s/%s" % (factory.make_ipv4_address(), prefixlen)
            )
            directives = DNSForwardZoneConfig.get_GENERATE_directives(network)
            self.assertIsEqual(network.size / 256, len(directives))

    def test_ignores_network_larger_than_slash_16(self):
        network = IPNetwork("%s/15" % factory.make_ipv4_address())
        self.assertEqual(
            [], DNSForwardZoneConfig.get_GENERATE_directives(network)
        )

    def test_ignores_networks_that_span_slash_16s(self):
        # If the upper and lower bounds of a range span two /16 networks
        # (but contain between them no more than 65536 addresses),
        # get_GENERATE_directives() will return early
        ip_range = IPRange("10.0.0.55", "10.1.0.54")
        directives = DNSForwardZoneConfig.get_GENERATE_directives(ip_range)
        self.assertEqual([], directives)

    def test_sorts_output(self):
        network = IPNetwork("10.0.0.0/23")

        expected_hostname = "10-0-%s-$"
        expected_address = "10.0.%s.$"

        directives = list(
            DNSForwardZoneConfig.get_GENERATE_directives(network)
        )
        self.expectThat(len(directives), Equals(2))
        self.expectThat(
            directives[0],
            Equals(("0-255", expected_hostname % "0", expected_address % "0")),
        )
        self.expectThat(
            directives[1],
            Equals(("0-255", expected_hostname % "1", expected_address % "1")),
        )
