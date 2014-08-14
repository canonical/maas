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

from celery.app import app_or_default
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from netaddr import (
    IPAddress,
    IPNetwork,
    )
from provisioningserver.dns.config import SRVRecord
from provisioningserver.dns.zoneconfig import (
    DNSForwardZoneConfig,
    DNSReverseZoneConfig,
    )
from testtools.matchers import (
    Contains,
    ContainsAll,
    FileContains,
    IsInstance,
    MatchesAll,
    MatchesStructure,
    Not,
    )
from twisted.python.filepath import FilePath


celery_conf = app_or_default().conf


def patch_dns_config_path(testcase):
    """Set the DNS config dir to a temporary directory, and return its path."""
    config_dir = testcase.make_dir()
    testcase.patch(celery_conf, 'DNS_CONFIG_DIR', config_dir)
    return config_dir


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
        network = factory.getRandomNetwork()
        ip = factory.pick_ip_in_network(network)
        mapping = {hostname: ip}
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
            os.path.join(celery_conf.DNS_CONFIG_DIR, 'zone.%s' % domain),
            dns_zone_config.target_path)

    def test_get_a_mapping_returns_ipv4_mapping(self):
        name = factory.make_string()
        network = IPNetwork('192.12.0.1/30')
        dns_ip = factory.pick_ip_in_network(network)
        ipv4_mapping = {
            factory.make_name('host'): factory.getRandomIPAddress(),
            factory.make_name('host'): factory.getRandomIPAddress(),
        }
        mapping = {
            factory.make_name('host'): factory.make_ipv6_address(),
            factory.make_name('host'): factory.make_ipv6_address(),
        }
        mapping.update(ipv4_mapping)
        expected = [('%s.' % name, dns_ip)] + ipv4_mapping.items()
        self.assertItemsEqual(
            expected,
            DNSForwardZoneConfig.get_A_mapping(mapping, name, dns_ip))

    def test_get_aaaa_mapping_returns_ipv6_mapping(self):
        name = factory.make_string()
        network = IPNetwork('192.12.0.1/30')
        dns_ip = factory.pick_ip_in_network(network)
        ipv6_mapping = {
            factory.make_name('host'): factory.make_ipv6_address(),
            factory.make_name('host'): factory.make_ipv6_address(),
        }
        mapping = {
            factory.make_name('host'): factory.getRandomIPAddress(),
            factory.make_name('host'): factory.getRandomIPAddress(),
        }
        mapping.update(ipv6_mapping)
        self.assertItemsEqual(
            ipv6_mapping.items(),
            DNSForwardZoneConfig.get_AAAA_mapping(mapping, name, dns_ip))

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
        target = factory.getRandomIPAddress()
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
        network = factory.getRandomNetwork()
        dns_ip = factory.pick_ip_in_network(network)
        ipv4_hostname = factory.make_name('host')
        ipv4_ip = factory.pick_ip_in_network(network)
        ipv6_hostname = factory.make_name('host')
        ipv6_ip = factory.make_ipv6_address()
        mapping = {
            ipv4_hostname: ipv4_ip,
            ipv6_hostname: ipv6_ip,
        }
        srv = self.make_srv_record()
        dns_zone_config = DNSForwardZoneConfig(
            domain, serial=random.randint(1, 100),
            mapping=mapping, dns_ip=dns_ip, srv_mapping=[srv])
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
                    ]
                )
            )
        )

    def test_writes_dns_zone_config_with_NS_record(self):
        target_dir = patch_dns_config_path(self)
        dns_ip = factory.getRandomIPAddress()
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

    def test_config_file_is_world_readable(self):
        patch_dns_config_path(self)
        dns_zone_config = DNSForwardZoneConfig(
            factory.make_string(), serial=random.randint(1, 100),
            dns_ip=factory.getRandomIPAddress())
        dns_zone_config.write_config()
        filepath = FilePath(dns_zone_config.target_path)
        self.assertTrue(filepath.getPermissions().other.read)


class TestDNSReverseZoneConfig(MAASTestCase):
    """Tests for DNSReverseZoneConfig."""

    def test_fields(self):
        domain = factory.make_string()
        serial = random.randint(1, 200)
        network = factory.getRandomNetwork()
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
            os.path.join(celery_conf.DNS_CONFIG_DIR, reverse_file_name),
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
        mapping = {
            factory.make_string(): factory.pick_ip_in_network(network),
            factory.make_string(): factory.pick_ip_in_network(network),
        }
        expected = [
            (IPAddress(ip).reverse_dns, '%s.%s.' % (hostname, name))
            for hostname, ip in mapping.items()
        ]
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
        mapping = in_network_mapping
        extra_mapping = {
            factory.make_string(): '192.50.0.2',
            factory.make_string(): '192.70.0.2',
        }
        mapping.update(extra_mapping)
        self.assertItemsEqual(
            expected,
            DNSReverseZoneConfig.get_PTR_mapping(mapping, name, network))

    def test_writes_dns_zone_config_with_NS_record(self):
        target_dir = patch_dns_config_path(self)
        network = factory.getRandomNetwork()
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
        dns_zone_config = DNSReverseZoneConfig(
            domain, serial=random.randint(1, 100), network=network)
        dns_zone_config.write_config()
        reverse_file_name = 'zone.168.192.in-addr.arpa'
        expected = Contains(
            'IN  NS  %s' % domain)
        self.assertThat(
            os.path.join(target_dir, reverse_file_name),
            FileContains(matcher=expected))

    def test_reverse_config_file_is_world_readable(self):
        patch_dns_config_path(self)
        dns_zone_config = DNSReverseZoneConfig(
            factory.make_string(), serial=random.randint(1, 100),
            network=factory.getRandomNetwork())
        dns_zone_config.write_config()
        filepath = FilePath(dns_zone_config.target_path)
        self.assertTrue(filepath.getPermissions().other.read)
