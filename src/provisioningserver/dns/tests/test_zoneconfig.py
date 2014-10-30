# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for BIND zone config generation."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from collections import (
    Iterable,
    Sequence,
    )
import os.path
import random

from maastesting.factory import factory
from maastesting.matchers import MockNotCalled
from maastesting.testcase import MAASTestCase
from netaddr import (
    IPAddress,
    IPNetwork,
    IPRange,
    )
from provisioningserver.dns.config import (
    get_dns_config_dir,
    SRVRecord,
    )
from provisioningserver.dns.testing import patch_dns_config_path
from provisioningserver.dns.zoneconfig import (
    DNSForwardZoneConfig,
    DNSReverseZoneConfig,
    )
from testtools.matchers import (
    Contains,
    ContainsAll,
    Equals,
    FileContains,
    HasLength,
    IsInstance,
    MatchesAll,
    MatchesStructure,
    Not,
    )
from twisted.python.filepath import FilePath


class TestDNSForwardZoneConfig(MAASTestCase):
    """Tests for DNSForwardZoneConfig."""

    def make_srv_record(self, service=None, port=None, target=None,
                        priority=None, weight=None):
        if service is None:
            service = '.'.join(factory.make_name('_') for _ in range(2))
        if port is None:
            port = factory.pick_port()
        if target is None:
            target = factory.make_hostname()
        if priority is None:
            priority = factory.pick_port()
        if weight is None:
            weight = factory.pick_port()
        return SRVRecord(
            service=service, port=port, target=target,
            priority=priority, weight=weight)

    def get_srv_item_output(self, srv_record):
        return '%s %s %s %s.' % (
            srv_record.priority,
            srv_record.weight,
            srv_record.port,
            srv_record.target,
            )

    def test_fields(self):
        domain = factory.make_string()
        serial = random.randint(1, 200)
        hostname = factory.make_string()
        network = factory.make_ipv4_network()
        ip = factory.pick_ip_in_network(network)
        mapping = {hostname: [ip]}
        dns_zone_config = DNSForwardZoneConfig(
            domain, serial=serial, mapping=mapping)
        self.assertThat(
            dns_zone_config,
            MatchesStructure.byEquality(
                domain=domain,
                serial=serial,
                _mapping=mapping,
                )
            )

    def test_computes_dns_config_file_paths(self):
        domain = factory.make_name('zone')
        dns_zone_config = DNSForwardZoneConfig(domain)
        self.assertEqual(
            os.path.join(get_dns_config_dir(), 'zone.%s' % domain),
            dns_zone_config.target_path)

    def test_get_a_mapping_returns_ipv4_mapping(self):
        name = factory.make_string()
        network = IPNetwork('192.12.0.1/30')
        dns_ip = factory.pick_ip_in_network(network)
        ipv4_mapping = {
            factory.make_name('host'): factory.make_ipv4_address(),
            factory.make_name('host'): factory.make_ipv4_address(),
        }
        ipv6_mapping = {
            factory.make_name('host'): factory.make_ipv6_address(),
            factory.make_name('host'): factory.make_ipv6_address(),
        }
        combined_mapping = {
            hostname: [ip]
            for hostname, ip in (ipv4_mapping.items() + ipv6_mapping.items())
            }
        expected = [('%s.' % name, dns_ip)] + ipv4_mapping.items()
        self.assertItemsEqual(
            expected,
            DNSForwardZoneConfig.get_A_mapping(combined_mapping, name, dns_ip))

    def test_get_aaaa_mapping_returns_ipv6_mapping(self):
        name = factory.make_string()
        network = IPNetwork('192.12.0.1/30')
        dns_ip = factory.pick_ip_in_network(network)
        ipv4_mapping = {
            factory.make_name('host'): factory.make_ipv4_address(),
            factory.make_name('host'): factory.make_ipv4_address(),
        }
        ipv6_mapping = {
            factory.make_name('host'): factory.make_ipv6_address(),
            factory.make_name('host'): factory.make_ipv6_address(),
        }
        combined_mapping = {
            hostname: [ip]
            for hostname, ip in (ipv4_mapping.items() + ipv6_mapping.items())
            }
        self.assertItemsEqual(
            ipv6_mapping.items(),
            DNSForwardZoneConfig.get_AAAA_mapping(
                combined_mapping, name, dns_ip))

    def test_get_srv_mapping_returns_iterator(self):
        srv = self.make_srv_record()
        self.assertThat(
            DNSForwardZoneConfig.get_srv_mapping([srv]),
            MatchesAll(
                IsInstance(Iterable), Not(IsInstance(Sequence))))

    def test_get_srv_mapping_returns_correct_format(self):
        srv = self.make_srv_record()
        self.assertItemsEqual([
            (srv.service, self.get_srv_item_output(srv)),
            ],
            DNSForwardZoneConfig.get_srv_mapping([srv]))

    def test_get_srv_mapping_handles_ip_address_target(self):
        target = factory.make_ipv4_address()
        srv = self.make_srv_record(target=target)
        item = self.get_srv_item_output(srv)
        item = item.rstrip('.')
        self.assertItemsEqual([
            (srv.service, item),
            ],
            DNSForwardZoneConfig.get_srv_mapping([srv]))

    def test_get_srv_mapping_returns_multiple(self):
        srvs = [self.make_srv_record() for _ in range(3)]
        entries = []
        for srv in srvs:
            entries.append((srv.service, self.get_srv_item_output(srv)))
        self.assertItemsEqual(
            entries, DNSForwardZoneConfig.get_srv_mapping(srvs))

    def test_writes_dns_zone_config(self):
        target_dir = patch_dns_config_path(self)
        domain = factory.make_string()
        network = factory.make_ipv4_network()
        dns_ip = factory.pick_ip_in_network(network)
        ipv4_hostname = factory.make_name('host')
        ipv4_ip = factory.pick_ip_in_network(network)
        ipv6_hostname = factory.make_name('host')
        ipv6_ip = factory.make_ipv6_address()
        mapping = {
            ipv4_hostname: [ipv4_ip],
            ipv6_hostname: [ipv6_ip],
        }
        expected_generate_directives = (
            DNSForwardZoneConfig.get_GENERATE_directives(network))
        srv = self.make_srv_record()
        dns_zone_config = DNSForwardZoneConfig(
            domain, serial=random.randint(1, 100),
            mapping=mapping, dns_ip=dns_ip, srv_mapping=[srv],
            dynamic_ranges=[IPRange(network.first, network.last)])
        dns_zone_config.write_config()
        self.assertThat(
            os.path.join(target_dir, 'zone.%s' % domain),
            FileContains(
                matcher=ContainsAll(
                    [
                        '%s IN SRV %s' % (
                            srv.service, self.get_srv_item_output(srv)),
                        '%s IN A %s' % (ipv4_hostname, ipv4_ip),
                        '%s IN AAAA %s' % (ipv6_hostname, ipv6_ip),
                    ] +
                    [
                        '$GENERATE %s %s IN A %s' % (
                            iterator_values, reverse_dns, hostname)
                        for iterator_values, reverse_dns, hostname in
                        expected_generate_directives
                    ]
                )
            )
        )

    def test_writes_dns_zone_config_with_NS_record(self):
        target_dir = patch_dns_config_path(self)
        dns_ip = factory.make_ipv4_address()
        dns_zone_config = DNSForwardZoneConfig(
            factory.make_string(), serial=random.randint(1, 100),
            dns_ip=dns_ip)
        dns_zone_config.write_config()
        self.assertThat(
            os.path.join(target_dir, 'zone.%s' % dns_zone_config.domain),
            FileContains(
                matcher=ContainsAll(
                    [
                        'IN  NS  %s.' % dns_zone_config.domain,
                        '%s. IN A %s' % (dns_zone_config.domain, dns_ip),
                    ])))

    def test_ignores_generate_directives_for_v6_dynamic_ranges(self):
        patch_dns_config_path(self)
        domain = factory.make_string()
        network = factory.make_ipv4_network()
        dns_ip = factory.pick_ip_in_network(network)
        ipv4_hostname = factory.make_name('host')
        ipv4_ip = factory.pick_ip_in_network(network)
        ipv6_hostname = factory.make_name('host')
        ipv6_ip = factory.make_ipv6_address()
        ipv6_network = factory.make_ipv6_network()
        dynamic_range = IPRange(ipv6_network.first, ipv6_network.last)
        mapping = {
            ipv4_hostname: [ipv4_ip],
            ipv6_hostname: [ipv6_ip],
        }
        srv = self.make_srv_record()
        dns_zone_config = DNSForwardZoneConfig(
            domain, serial=random.randint(1, 100),
            mapping=mapping, dns_ip=dns_ip, srv_mapping=[srv],
            dynamic_ranges=[dynamic_range])
        get_generate_directives = self.patch(
            dns_zone_config, 'get_GENERATE_directives')
        dns_zone_config.write_config()
        self.assertThat(get_generate_directives, MockNotCalled())

    def test_config_file_is_world_readable(self):
        patch_dns_config_path(self)
        dns_zone_config = DNSForwardZoneConfig(
            factory.make_string(), serial=random.randint(1, 100),
            dns_ip=factory.make_ipv4_address())
        dns_zone_config.write_config()
        filepath = FilePath(dns_zone_config.target_path)
        self.assertTrue(filepath.getPermissions().other.read)


class TestDNSReverseZoneConfig(MAASTestCase):
    """Tests for DNSReverseZoneConfig."""

    def test_fields(self):
        domain = factory.make_string()
        serial = random.randint(1, 200)
        network = factory.make_ipv4_network()
        dns_zone_config = DNSReverseZoneConfig(
            domain, serial=serial, network=network)
        self.assertThat(
            dns_zone_config,
            MatchesStructure.byEquality(
                domain=domain,
                serial=serial,
                _network=network,
                )
            )

    def test_computes_dns_config_file_paths(self):
        domain = factory.make_name('zone')
        reverse_file_name = 'zone.168.192.in-addr.arpa'
        dns_zone_config = DNSReverseZoneConfig(
            domain, network=IPNetwork("192.168.0.0/22"))
        self.assertEqual(
            os.path.join(get_dns_config_dir(), reverse_file_name),
            dns_zone_config.target_path)

    def test_reverse_zone_file(self):
        # DNSReverseZoneConfig calculates the reverse zone file name
        # correctly for IPv4 and IPv6 networks.
        expected = [
            # IPv4 networks.
            (IPNetwork('192.168.0.1/22'), '168.192.in-addr.arpa'),
            (IPNetwork('192.168.0.1/24'), '0.168.192.in-addr.arpa'),
            # IPv6 networks.
            (IPNetwork('3ffe:801::/32'), '1.0.8.0.e.f.f.3.ip6.arpa'),
            (IPNetwork('2001:db8:0::/48'), '0.0.0.0.8.b.d.0.1.0.0.2.ip6.arpa'),
            (
                IPNetwork('2001:ba8:1f1:400::/56'),
                '4.0.1.f.1.0.8.a.b.0.1.0.0.2.ip6.arpa'
            ),
            (
                IPNetwork('2610:8:6800:1::/64'),
                '1.0.0.0.0.0.8.6.8.0.0.0.0.1.6.2.ip6.arpa',
            ),
            (
                IPNetwork('2001:ba8:1f1:400::/103'),
                '0.0.0.0.0.0.0.0.0.0.0.4.0.1.f.1.0.8.a.b.0.1.0.0.2.ip6.arpa',
            ),

        ]
        results = []
        for network, _ in expected:
            domain = factory.make_name('zone')
            dns_zone_config = DNSReverseZoneConfig(domain, network=network)
            results.append((network, dns_zone_config.zone_name))
        self.assertEqual(expected, results)

    def test_get_ptr_mapping(self):
        name = factory.make_string()
        network = IPNetwork('192.12.0.1/30')
        hosts = {
            factory.make_string(): factory.pick_ip_in_network(network),
            factory.make_string(): factory.pick_ip_in_network(network),
        }
        expected = [
            (IPAddress(ip).reverse_dns, '%s.%s.' % (hostname, name))
            for hostname, ip in hosts.items()
        ]
        mapping = {
            hostname: [ip]
            for hostname, ip in hosts.items()
            }
        self.assertItemsEqual(
            expected,
            DNSReverseZoneConfig.get_PTR_mapping(mapping, name, network))

    def test_get_ptr_mapping_drops_IPs_not_in_network(self):
        name = factory.make_string()
        network = IPNetwork('192.12.0.1/30')
        in_network_mapping = {
            factory.make_string(): factory.pick_ip_in_network(network),
            factory.make_string(): factory.pick_ip_in_network(network),
        }
        expected = [
            (IPAddress(ip).reverse_dns, '%s.%s.' % (hostname, name))
            for hostname, ip in in_network_mapping.items()
        ]
        mapping = {
            hostname: [ip]
            for hostname, ip in in_network_mapping.items()
            }
        extra_mapping = {
            factory.make_string(): ['192.50.0.2'],
            factory.make_string(): ['192.70.0.2'],
        }
        mapping.update(extra_mapping)
        self.assertItemsEqual(
            expected,
            DNSReverseZoneConfig.get_PTR_mapping(mapping, name, network))

    def test_writes_dns_zone_config_with_NS_record(self):
        target_dir = patch_dns_config_path(self)
        network = factory.make_ipv4_network()
        dns_zone_config = DNSReverseZoneConfig(
            factory.make_string(), serial=random.randint(1, 100),
            network=network)
        dns_zone_config.write_config()
        self.assertThat(
            os.path.join(
                target_dir, 'zone.%s' % dns_zone_config.zone_name),
            FileContains(
                matcher=Contains('IN  NS  %s.' % dns_zone_config.domain)))

    def test_writes_reverse_dns_zone_config(self):
        target_dir = patch_dns_config_path(self)
        domain = factory.make_string()
        network = IPNetwork('192.168.0.1/22')
        dynamic_network = IPNetwork('192.168.0.1/28')
        dns_zone_config = DNSReverseZoneConfig(
            domain, serial=random.randint(1, 100), network=network,
            dynamic_ranges=[
                IPRange(dynamic_network.first, dynamic_network.last)])
        dns_zone_config.write_config()
        reverse_file_name = 'zone.168.192.in-addr.arpa'
        expected_generate_directives = dns_zone_config.get_GENERATE_directives(
            dynamic_network, domain)
        expected = ContainsAll(
            [
                'IN  NS  %s' % domain
            ] +
            [
                '$GENERATE %s %s IN PTR %s' % (
                    iterator_values, reverse_dns, hostname)
                for iterator_values, reverse_dns, hostname in
                expected_generate_directives
            ])
        self.assertThat(
            os.path.join(target_dir, reverse_file_name),
            FileContains(matcher=expected))

    def test_ignores_generate_directives_for_v6_dynamic_ranges(self):
        patch_dns_config_path(self)
        domain = factory.make_string()
        network = IPNetwork('192.168.0.1/22')
        dynamic_network = IPNetwork("%s/64" % factory.make_ipv6_address())
        dns_zone_config = DNSReverseZoneConfig(
            domain, serial=random.randint(1, 100), network=network,
            dynamic_ranges=[
                IPRange(dynamic_network.first, dynamic_network.last)])
        get_generate_directives = self.patch(
            dns_zone_config, 'get_GENERATE_directives')
        dns_zone_config.write_config()
        self.assertThat(get_generate_directives, MockNotCalled())

    def test_reverse_config_file_is_world_readable(self):
        patch_dns_config_path(self)
        dns_zone_config = DNSReverseZoneConfig(
            factory.make_string(), serial=random.randint(1, 100),
            network=factory.make_ipv4_network())
        dns_zone_config.write_config()
        filepath = FilePath(dns_zone_config.target_path)
        self.assertTrue(filepath.getPermissions().other.read)


class TestDNSReverseZoneConfig_GetGenerateDirectives(MAASTestCase):
    """Tests for `DNSReverseZoneConfig.get_GENERATE_directives()`."""

    def test_excplicitly(self):
        # The other tests in this TestCase rely on
        # get_expected_generate_directives(), which is quite dense. Here
        # we test get_GENERATE_directives() explicitly.
        ip_range = IPRange('192.168.0.55', '192.168.2.128')
        expected_directives = [
            ("55-255", "$.0.168.192.in-addr.arpa.", "192-168-0-$.domain."),
            ("0-255", "$.1.168.192.in-addr.arpa.", "192-168-1-$.domain."),
            ("0-128", "$.2.168.192.in-addr.arpa.", "192-168-2-$.domain."),
            ]
        self.assertItemsEqual(
            expected_directives,
            DNSReverseZoneConfig.get_GENERATE_directives(
                ip_range, domain="domain"))

    def get_expected_generate_directives(self, network, domain):
        ip_parts = network.network.format().split('.')
        relevant_ip_parts = ip_parts[:-2]

        first_address = IPAddress(network.first).format()
        first_address_parts = first_address.split(".")

        if network.size < 256:
            last_address = IPAddress(network.last).format()
            iterator_low = int(first_address_parts[-1])
            iterator_high = last_address.split('.')[-1]
        else:
            iterator_low = 0
            iterator_high = 255

        second_octet_offset = int(first_address_parts[-2])
        expected_generate_directives = []
        directives_needed = network.size / 256

        if directives_needed == 0:
            directives_needed = 1
        for num in range(directives_needed):
            expected_address_base = "%s-%s" % tuple(relevant_ip_parts)
            expected_address = "%s-%s-$" % (
                expected_address_base, num + second_octet_offset)
            relevant_ip_parts.reverse()
            expected_rdns_base = (
                "%s.%s.in-addr.arpa." % tuple(relevant_ip_parts))
            expected_rdns_template = "$.%s.%s" % (
                num + second_octet_offset, expected_rdns_base)
            expected_generate_directives.append(
                (
                    "%s-%s" % (iterator_low, iterator_high),
                    expected_rdns_template,
                    "%s.%s." % (expected_address, domain)
                ))
            relevant_ip_parts.reverse()
        return expected_generate_directives

    def test_returns_single_entry_for_slash_24_network(self):
        network = IPNetwork("%s/24" % factory.make_ipv4_address())
        domain = factory.make_string()
        expected_generate_directives = self.get_expected_generate_directives(
            network, domain)
        directives = DNSReverseZoneConfig.get_GENERATE_directives(
            network, domain)
        self.expectThat(directives, HasLength(1))
        self.assertItemsEqual(expected_generate_directives, directives)

    def test_returns_single_entry_for_tiny_network(self):
        network = IPNetwork("%s/28" % factory.make_ipv4_address())
        domain = factory.make_string()

        expected_generate_directives = self.get_expected_generate_directives(
            network, domain)
        directives = DNSReverseZoneConfig.get_GENERATE_directives(
            network, domain)
        self.expectThat(directives, HasLength(1))
        self.assertItemsEqual(expected_generate_directives, directives)

    def test_returns_single_entry_for_weird_small_range(self):
        ip_range = IPRange('10.0.0.1', '10.0.0.255')
        domain = factory.make_string()
        directives = DNSReverseZoneConfig.get_GENERATE_directives(
            ip_range, domain)
        self.expectThat(directives, HasLength(1))

    def test_dtrt_for_larger_networks(self):
        # For every other network size that we're not explicitly
        # testing here,
        # DNSReverseZoneConfig.get_GENERATE_directives() will return
        # one GENERATE directive for every 255 addresses in the network.
        for prefixlen in range(23, 17):
            network = IPNetwork(
                "%s/%s" % (factory.make_ipv4_address(), prefixlen))
            domain = factory.make_string()
            directives = DNSReverseZoneConfig.get_GENERATE_directives(
                network, domain)
            self.expectThat(directives, HasLength(network.size / 256))

    def test_returns_two_entries_for_slash_23_network(self):
        network = IPNetwork(factory.make_ipv4_network(slash=23))
        domain = factory.make_string()

        expected_generate_directives = self.get_expected_generate_directives(
            network, domain)
        directives = DNSReverseZoneConfig.get_GENERATE_directives(
            network, domain)
        self.expectThat(directives, HasLength(2))
        self.assertItemsEqual(expected_generate_directives, directives)

    def test_ignores_network_larger_than_slash_16(self):
        network = IPNetwork("%s/15" % factory.make_ipv4_address())
        self.assertEqual(
            [],
            DNSReverseZoneConfig.get_GENERATE_directives(
                network, factory.make_string()))

    def test_ignores_networks_that_span_slash_16s(self):
        # If the upper and lower bounds of a range span two /16 networks
        # (but contain between them no more than 65536 addresses),
        # get_GENERATE_directives() will return early
        ip_range = IPRange('10.0.0.55', '10.1.0.54')
        directives = DNSReverseZoneConfig.get_GENERATE_directives(
            ip_range, factory.make_string())
        self.assertEqual([], directives)

    def test_sorts_output_by_hostname(self):
        network = IPNetwork("10.0.0.1/23")
        domain = factory.make_string()

        expected_hostname = "10-0-%s-$." + domain + "."
        expected_rdns = "$.%s.0.10.in-addr.arpa."

        directives = list(DNSReverseZoneConfig.get_GENERATE_directives(
            network, domain))
        self.expectThat(
            directives[0], Equals(
                ("0-255", expected_rdns % "0", expected_hostname % "0")))
        self.expectThat(
            directives[1], Equals(
                ("0-255", expected_rdns % "1", expected_hostname % "1")))


class TestDNSForwardZoneConfig_GetGenerateDirectives(MAASTestCase):
    """Tests for `DNSForwardZoneConfig.get_GENERATE_directives()`."""

    def test_excplicitly(self):
        # The other tests in this TestCase rely on
        # get_expected_generate_directives(), which is quite dense. Here
        # we test get_GENERATE_directives() explicitly.
        ip_range = IPRange('192.168.0.55', '192.168.2.128')
        expected_directives = [
            ("55-255", "192-168-0-$", "192.168.0.$"),
            ("0-255", "192-168-1-$", "192.168.1.$"),
            ("0-128", "192-168-2-$", "192.168.2.$"),
            ]
        self.assertItemsEqual(
            expected_directives,
            DNSForwardZoneConfig.get_GENERATE_directives(ip_range))

    def get_expected_generate_directives(self, network):
        ip_parts = network.network.format().split('.')
        ip_parts[-1] = "$"
        expected_hostname = "%s" % "-".join(ip_parts)
        expected_address = ".".join(ip_parts)

        first_address = IPAddress(network.first).format()
        first_address_parts = first_address.split(".")
        last_address = IPAddress(network.last).format()
        last_address_parts = last_address.split(".")

        if network.size < 256:
            iterator_low = int(first_address_parts[-1])
            if iterator_low == 0:
                iterator_low = 1
            iterator_high = last_address_parts[-1]
        else:
            iterator_low = 0
            iterator_high = 255

        expected_iterator_values = "%s-%s" % (iterator_low, iterator_high)

        directives_needed = network.size / 256
        if directives_needed == 0:
            directives_needed = 1
        expected_directives = []
        for num in range(directives_needed):
            ip_parts[-2] = unicode(num + int(ip_parts[-2]))
            expected_address = ".".join(ip_parts)
            expected_hostname = "%s" % "-".join(ip_parts)
            expected_directives.append(
                (
                    expected_iterator_values,
                    expected_hostname,
                    expected_address
                ))
        return expected_directives

    def test_returns_single_entry_for_slash_24_network(self):
        network = IPNetwork("%s/24" % factory.make_ipv4_address())
        expected_directives = self.get_expected_generate_directives(network)
        directives = DNSForwardZoneConfig.get_GENERATE_directives(
            network)
        self.expectThat(directives, HasLength(1))
        self.assertItemsEqual(expected_directives, directives)

    def test_returns_single_entry_for_tiny_network(self):
        network = IPNetwork("%s/31" % factory.make_ipv4_address())

        expected_directives = self.get_expected_generate_directives(network)
        directives = DNSForwardZoneConfig.get_GENERATE_directives(
            network)
        self.assertEqual(1, len(expected_directives))
        self.assertItemsEqual(expected_directives, directives)

    def test_returns_two_entries_for_slash_23_network(self):
        network = IPNetwork("%s/23" % factory.make_ipv4_address())

        expected_directives = self.get_expected_generate_directives(network)
        directives = DNSForwardZoneConfig.get_GENERATE_directives(
            network)
        self.assertEqual(2, len(expected_directives))
        self.assertItemsEqual(expected_directives, directives)

    def test_dtrt_for_larger_networks(self):
        # For every other network size that we're not explicitly
        # testing here,
        # DNSForwardZoneConfig.get_GENERATE_directives() will return
        # one GENERATE directive for every 255 addresses in the network.
        for prefixlen in range(23, 16):
            network = IPNetwork(
                "%s/%s" % (factory.make_ipv4_address(), prefixlen))
            directives = DNSForwardZoneConfig.get_GENERATE_directives(
                network)
            self.assertIsEqual(network.size / 256, len(directives))

    def test_ignores_network_larger_than_slash_16(self):
        network = IPNetwork("%s/15" % factory.make_ipv4_address())
        self.assertEqual(
            [],
            DNSForwardZoneConfig.get_GENERATE_directives(network))

    def test_ignores_networks_that_span_slash_16s(self):
        # If the upper and lower bounds of a range span two /16 networks
        # (but contain between them no more than 65536 addresses),
        # get_GENERATE_directives() will return early
        ip_range = IPRange('10.0.0.55', '10.1.0.54')
        directives = DNSForwardZoneConfig.get_GENERATE_directives(
            ip_range)
        self.assertEqual([], directives)

    def test_sorts_output(self):
        network = IPNetwork("10.0.0.0/23")

        expected_hostname = "10-0-%s-$"
        expected_address = "10.0.%s.$"

        directives = list(DNSForwardZoneConfig.get_GENERATE_directives(
            network))
        self.expectThat(len(directives), Equals(2))
        self.expectThat(
            directives[0], Equals(
                ("0-255", expected_hostname % "0", expected_address % "0")))
        self.expectThat(
            directives[1], Equals(
                ("0-255", expected_hostname % "1", expected_address % "1")))
