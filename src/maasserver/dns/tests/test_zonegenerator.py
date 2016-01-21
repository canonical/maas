# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `ZoneGenerator` and supporting cast."""

__all__ = []

import random
import socket
from urllib.parse import urlparse

from maasserver import server_address
from maasserver.dns import zonegenerator
from maasserver.dns.zonegenerator import (
    DNSException,
    get_dns_search_paths,
    get_dns_server_address,
    get_hostname_ip_mapping,
    lazydict,
    warn_loopback,
    WARNING_MESSAGE,
    ZoneGenerator,
)
from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
)
from maasserver.models import (
    Config,
    Domain,
    interface as interface_module,
    NodeGroup,
    Subnet,
)
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.factory import factory as maastesting_factory
from maastesting.fakemethod import FakeMethod
from maastesting.matchers import (
    MockAnyCall,
    MockCalledOnceWith,
    MockNotCalled,
)
from mock import (
    ANY,
    call,
    Mock,
)
from netaddr import (
    IPNetwork,
    IPRange,
)
from provisioningserver.dns.zoneconfig import (
    DNSForwardZoneConfig,
    DNSReverseZoneConfig,
)
from provisioningserver.utils.enum import map_enum
from testtools import TestCase
from testtools.matchers import (
    Equals,
    IsInstance,
    MatchesAll,
    MatchesSetwise,
    MatchesStructure,
)


class TestGetDNSServerAddress(MAASServerTestCase):

    def test_get_dns_server_address_resolves_hostname(self):
        url = maastesting_factory.make_simple_http_url()
        self.useFixture(RegionConfigurationFixture(maas_url=url))
        ip = factory.make_ipv4_address()
        resolver = self.patch(server_address, 'resolve_hostname')
        resolver.return_value = {ip}

        hostname = urlparse(url).hostname
        result = get_dns_server_address()
        self.assertEqual(ip, result)
        self.expectThat(resolver, MockAnyCall(hostname, 4))
        self.expectThat(resolver, MockAnyCall(hostname, 6))

    def test_get_dns_server_address_passes_on_IPv4_IPv6_selection(self):
        ipv4 = factory.pick_bool()
        ipv6 = factory.pick_bool()
        patch = self.patch(zonegenerator, 'get_maas_facing_server_address')
        patch.return_value = factory.make_ipv4_address()

        get_dns_server_address(ipv4=ipv4, ipv6=ipv6)

        self.assertThat(patch, MockCalledOnceWith(ANY, ipv4=ipv4, ipv6=ipv6))

    def test_get_dns_server_address_raises_if_hostname_doesnt_resolve(self):
        url = maastesting_factory.make_simple_http_url()
        self.useFixture(RegionConfigurationFixture(maas_url=url))
        self.patch(
            zonegenerator, 'get_maas_facing_server_address',
            FakeMethod(failure=socket.error))
        self.assertRaises(DNSException, get_dns_server_address)

    def test_get_dns_server_address_logs_warning_if_ip_is_localhost(self):
        logger = self.patch(zonegenerator, 'logger')
        self.patch(
            zonegenerator, 'get_maas_facing_server_address',
            Mock(return_value='127.0.0.1'))
        get_dns_server_address()
        self.assertEqual(
            call(WARNING_MESSAGE % '127.0.0.1'),
            logger.warning.call_args)

    def test_get_dns_server_address_uses_nodegroup_maas_url(self):
        ip = factory.make_ipv4_address()
        resolver = self.patch(server_address, 'resolve_hostname')
        resolver.return_value = {ip}
        hostname = factory.make_hostname()
        maas_url = 'http://%s' % hostname
        nodegroup = factory.make_NodeGroup(maas_url=maas_url)
        result = get_dns_server_address(nodegroup)
        self.expectThat(ip, Equals(result))
        self.expectThat(resolver, MockAnyCall(hostname, 4))
        self.expectThat(resolver, MockAnyCall(hostname, 6))


class TestGetDNSSearchPaths(MAASServerTestCase):

    def test__returns_all_nodegroup_names(self):
        nodegroup_master = NodeGroup.objects.ensure_master()
        dns_search_names = [
            factory.make_name("dns")
            for _ in range(3)
        ]
        for name in dns_search_names:
            factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED, name=name)
        # Create some with empty names.
        for _ in range(3):
            factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED, name="")
        # Create some not enabled.
        for _ in range(3):
            factory.make_NodeGroup(status=NODEGROUP_STATUS.DISABLED, name="")
        self.assertItemsEqual(
            [nodegroup_master.name] + dns_search_names, get_dns_search_paths())


class TestWarnLoopback(MAASServerTestCase):
    def test_warn_loopback_warns_about_IPv4_loopback(self):
        logger = self.patch(zonegenerator, 'logger')
        loopback = '127.0.0.1'
        warn_loopback(loopback)
        self.assertThat(
            logger.warning, MockCalledOnceWith(WARNING_MESSAGE % loopback))

    def test_warn_loopback_warns_about_any_IPv4_loopback(self):
        logger = self.patch(zonegenerator, 'logger')
        loopback = '127.254.100.99'
        warn_loopback(loopback)
        self.assertThat(logger.warning, MockCalledOnceWith(ANY))

    def test_warn_loopback_warns_about_IPv6_loopback(self):
        logger = self.patch(zonegenerator, 'logger')
        loopback = '::1'
        warn_loopback(loopback)
        self.assertThat(logger.warning, MockCalledOnceWith(ANY))

    def test_warn_loopback_does_not_warn_about_sensible_IPv4(self):
        logger = self.patch(zonegenerator, 'logger')
        warn_loopback('10.1.2.3')
        self.assertThat(logger.warning, MockNotCalled())

    def test_warn_loopback_does_not_warn_about_sensible_IPv6(self):
        logger = self.patch(zonegenerator, 'logger')
        warn_loopback('1::9')
        self.assertThat(logger.warning, MockNotCalled())


class TestLazyDict(TestCase):
    """Tests for `lazydict`."""

    def test_empty_initially(self):
        self.assertEqual({}, lazydict(Mock()))

    def test_populates_on_demand(self):
        value = factory.make_name('value')
        value_dict = lazydict(lambda key: value)
        key = factory.make_name('key')
        retrieved_value = value_dict[key]
        self.assertEqual(value, retrieved_value)
        self.assertEqual({key: value}, value_dict)

    def test_remembers_elements(self):
        value_dict = lazydict(lambda key: factory.make_name('value'))
        key = factory.make_name('key')
        self.assertEqual(value_dict[key], value_dict[key])

    def test_holds_one_value_per_key(self):
        value_dict = lazydict(lambda key: key)
        key1 = factory.make_name('key')
        key2 = factory.make_name('key')

        value1 = value_dict[key1]
        value2 = value_dict[key2]

        self.assertEqual((key1, key2), (value1, value2))
        self.assertEqual({key1: key1, key2: key2}, value_dict)


class TestGetHostnameIPMapping(MAASServerTestCase):
    """Test for `get_hostname_ip_mapping`."""

    def test_get_hostname_ip_mapping_containts_both_static_and_dynamic(self):
        self.patch_autospec(interface_module, "update_host_maps")
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            name=Domain.objects.get_default_domain().name)
        node1 = factory.make_Node_with_Interface_on_Subnet(
            nodegroup=nodegroup, disable_ipv4=False)
        boot_interface = node1.get_boot_interface()
        [static_ip] = boot_interface.claim_static_ips()
        ngi = static_ip.subnet.nodegroupinterface_set.first()
        node2 = factory.make_Node(nodegroup=nodegroup, disable_ipv4=False)
        node2_nic = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node2)
        dynamic_ips = IPRange(ngi.ip_range_low, ngi.ip_range_high)
        dynamic_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=str(dynamic_ips[0]),
            subnet=static_ip.subnet, interface=node2_nic)
        ttl = random.randint(10, 300)
        Config.objects.set_config('default_dns_ttl', ttl)

        expected_mapping = {
            "%s.maas" % node1.hostname: (ttl, [static_ip.ip]),
            "%s.maas" % node2.hostname: (ttl, [dynamic_ip.ip]),
        }
        self.assertEqual(
            expected_mapping,
            get_hostname_ip_mapping(Domain.objects.get_default_domain()))


def forward_zone(domain):
    """Create a matcher for a :class:`DNSForwardZoneConfig`.

    Returns a matcher which asserts that the test value is a
    `DNSForwardZoneConfig` with the given domain.
    """
    return MatchesAll(
        IsInstance(DNSForwardZoneConfig),
        MatchesStructure.byEquality(domain=domain))


def reverse_zone(domain, network):
    """Create a matcher for a :class:`DNSReverseZoneConfig`.

    Returns a matcher which asserts that the test value is a
    :class:`DNSReverseZoneConfig` with the given domain and network.
    """
    network = network if network is None else IPNetwork(network)
    return MatchesAll(
        IsInstance(DNSReverseZoneConfig),
        MatchesStructure.byEquality(
            domain=domain, _network=network))


class TestZoneGenerator(MAASServerTestCase):
    """Tests for :class:`ZoneGenerator`."""

    def make_node_group(self, **kwargs):
        """Create an accepted nodegroup with a managed interface."""
        return factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS, **kwargs)

    def test_get_forward_domains_returns_empty_for_unknown_domain(self):
        self.assertEqual(
            set(),
            ZoneGenerator._get_forward_domains(
                factory.make_name('domain')))

    def test_get_forward_domains_empty_for_no_domains(self):
        self.assertEqual(set(), ZoneGenerator._get_forward_domains([]))

    def test_get_forward_domains_returns_dns_managed_domains(self):
        domainname = factory.make_name('domain')
        factory.make_Domain(domainname)
        self.make_node_group(name=domainname)
        domain = Domain.objects.get(name=domainname)
        self.assertEqual(
            {domain},
            ZoneGenerator._get_forward_domains([domainname]))

    def test_get_forward_domains_includes_multiple_domains(self):
        domains = [factory.make_Domain() for _ in range(3)]
        self.assertEqual(
            set(domains),
            ZoneGenerator._get_forward_domains(
                [domain.name for domain in domains]))

    def test_get_forward_domains_ignores_non_authoritative_domains(self):
        domain = factory.make_name('domain')
        factory.make_Domain(name=domain, authoritative=False)
        self.assertEqual(
            set(),
            ZoneGenerator._get_forward_domains([domain]))

    def test_get_forward_domains_ignores_other_domains(self):
        domains = [factory.make_Domain() for _ in range(2)]
        self.assertEqual(
            {domains[0]},
            ZoneGenerator._get_forward_domains([domains[0].name]))

    def test_get_reverse_nodegroups_returns_only_dns_managed_nodegroups(self):
        nodegroups = {
            management: factory.make_NodeGroup(
                status=NODEGROUP_STATUS.ENABLED, management=management)
            for management in map_enum(NODEGROUPINTERFACE_MANAGEMENT).values()
            }
        self.assertEqual(
            {nodegroups[NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS]},
            ZoneGenerator._get_reverse_nodegroups(nodegroups.values()))

    def test_get_reverse_nodegroups_ignores_other_nodegroups(self):
        nodegroups = [self.make_node_group() for _ in range(3)]
        self.assertEqual(
            {nodegroups[0]},
            ZoneGenerator._get_reverse_nodegroups(nodegroups[:1]))

    def test_get_reverse_nodegroups_ignores_unaccepted_nodegroups(self):
        nodegroups = {
            status: factory.make_NodeGroup(
                status=status,
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
            for status in map_enum(NODEGROUP_STATUS).values()
            }
        self.assertEqual(
            {nodegroups[NODEGROUP_STATUS.ENABLED]},
            ZoneGenerator._get_reverse_nodegroups(nodegroups.values()))

    def test_get_networks_returns_network(self):
        nodegroup = self.make_node_group()
        [interface] = nodegroup.get_managed_interfaces()
        networks_dict = ZoneGenerator._get_networks()
        retrieved_interface = networks_dict[nodegroup]
        self.assertEqual(
            [
                (
                    interface.network,
                    (interface.ip_range_low, interface.ip_range_high)
                )
            ],
            retrieved_interface)

    def test_get_networks_returns_multiple_networks(self):
        nodegroups = [self.make_node_group() for _ in range(3)]
        networks_dict = ZoneGenerator._get_networks()
        for nodegroup in nodegroups:
            [interface] = nodegroup.get_managed_interfaces()
            self.assertEqual(
                [
                    (
                        interface.network,
                        (interface.ip_range_low, interface.ip_range_high),
                    ),
                ],
                networks_dict[nodegroup])

    def test_get_networks_returns_managed_networks(self):
        nodegroups = [
            factory.make_NodeGroup(
                status=NODEGROUP_STATUS.ENABLED, management=management)
            for management in map_enum(NODEGROUPINTERFACE_MANAGEMENT).values()
            ]
        networks_dict = ZoneGenerator._get_networks()
        # Force lazydict to evaluate for all these nodegroups.
        for nodegroup in nodegroups:
            networks_dict[nodegroup]
        self.assertEqual(
            {
                nodegroup: [
                    (
                        interface.network,
                        (interface.ip_range_low, interface.ip_range_high),
                    )
                    for interface in nodegroup.get_managed_interfaces()
                    ]
                for nodegroup in nodegroups
            },
            networks_dict)

    def test_with_no_nodegroups_yields_nothing(self):
        self.useFixture(RegionConfigurationFixture())
        self.assertEqual(
            [],
            ZoneGenerator((), (), serial_generator=Mock()).as_list())

    def test_defaults_ttl(self):
        self.useFixture(RegionConfigurationFixture())
        zonegen = ZoneGenerator((), (), serial_generator=Mock())
        self.assertEqual(
            Config.objects.get_config('default_dns_ttl'),
            zonegen.default_ttl)
        self.assertEqual([], zonegen.as_list())

    def test_accepts_default_ttl(self):
        self.useFixture(RegionConfigurationFixture())
        default_ttl = random.randint(10, 1000)
        zonegen = ZoneGenerator(
            (), (), default_ttl=default_ttl, serial_generator=Mock())
        self.assertEqual(default_ttl, zonegen.default_ttl)

    def test_with_one_nodegroup_yields_forward_and_reverse_zone(self):
        self.useFixture(RegionConfigurationFixture())
        factory.make_Domain(name='henry')
        nodegroup = self.make_node_group(
            name="henry", network=IPNetwork("10/29"))
        domain = Domain.objects.get(name="henry")
        default_domain = Domain.objects.get_default_domain().name
        subnet = Subnet.objects.get(
            nodegroupinterface__nodegroup=nodegroup)
        zones = ZoneGenerator(
            domain, subnet, serial_generator=Mock()).as_list()
        self.assertThat(
            zones, MatchesSetwise(
                forward_zone("henry"),
                reverse_zone(default_domain, "10/29")))

    def test_with_one_nodegroup_with_node_yields_fwd_and_rev_zone(self):
        self.useFixture(RegionConfigurationFixture())
        factory.make_Domain(name='henry')
        nodegroup = self.make_node_group(
            name="henry", network=IPNetwork("10/29"))
        domain = Domain.objects.get(name="henry")
        default_domain = Domain.objects.get_default_domain().name
        subnet = Subnet.objects.get(
            nodegroupinterface__nodegroup=nodegroup)
        factory.make_Node_with_Interface_on_Subnet(
            nodegroup=nodegroup, subnet=subnet, vlan=subnet.vlan,
            fabric=subnet.vlan.fabric)
        zones = ZoneGenerator(
            domain, subnet, serial_generator=Mock()).as_list()
        self.assertThat(
            zones, MatchesSetwise(
                forward_zone("henry"),
                reverse_zone(default_domain, "10/29")))

    def test_returns_interface_ips_but_no_nulls(self):
        self.useFixture(RegionConfigurationFixture())
        default_domain = Domain.objects.get_default_domain().name
        domain = factory.make_Domain(name='henry')
        nodegroup = self.make_node_group(
            name=domain.name, network=IPNetwork("10/29"))
        subnet = Subnet.objects.get(
            nodegroupinterface__nodegroup=nodegroup)
        subnet.gateway_ip = IPNetwork(subnet.cidr).ip + 1
        # Create a node with two interfaces, with NULL ips
        node = factory.make_Node_with_Interface_on_Subnet(
            nodegroup=nodegroup, subnet=subnet, vlan=subnet.vlan,
            fabric=subnet.vlan.fabric, domain=domain, interface_count=3,
            disable_ipv4=False)
        dnsdata = factory.make_DNSData(domain=domain)
        boot_iface = node.boot_interface
        interfaces = list(node.interface_set.all().exclude(id=boot_iface.id))
        # Now go add IP addresses to the boot interface, and one other
        boot_ip = factory.make_StaticIPAddress(
            interface=boot_iface, subnet=subnet)
        sip = factory.make_StaticIPAddress(
            interface=interfaces[0], subnet=subnet)
        default_ttl = random.randint(10, 300)
        zones = ZoneGenerator(
            domain, subnet, default_ttl=default_ttl,
            serial_generator=Mock()).as_list()
        self.assertThat(
            zones, MatchesSetwise(
                forward_zone("henry"),
                reverse_zone(default_domain, "10/29")))
        self.assertEqual(
            {node.hostname: (30, ['%s' % boot_ip.ip])}, zones[0]._mapping)
        self.assertEqual(
            {dnsdata.dnsresource.name: (default_ttl, [
                "%s %s" % (dnsdata.resource_type, dnsdata.resource_data)])},
            zones[0]._other_mapping)
        self.assertItemsEqual({
            node.fqdn: (30, ['%s' % boot_ip.ip]),
            '%s.%s' % (interfaces[0].name, node.fqdn): (
                default_ttl, ['%s' % sip.ip]),
            '%s.%s' % (boot_iface.name, node.fqdn): (
                default_ttl, ['%s' % boot_ip.ip])},
            zones[1]._mapping)

    def test_two_managed_interfaces_yields_one_forward_two_reverse_zones(self):
        self.useFixture(RegionConfigurationFixture())
        nodegroup = self.make_node_group()
        factory.make_NodeGroupInterface(
            nodegroup=nodegroup,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        [interface1, interface2] = nodegroup.get_managed_interfaces()
        default_domain = Domain.objects.get_default_domain().name

        factory.make_Domain(name=nodegroup.name)
        expected_zones = [
            forward_zone(nodegroup.name),
            reverse_zone(default_domain, interface1.network),
            reverse_zone(default_domain, interface2.network),
            ]
        domain = Domain.objects.get(name=nodegroup.name)
        subnet = Subnet.objects.filter(
            nodegroupinterface__nodegroup=nodegroup)
        self.assertThat(
            ZoneGenerator(
                domain, subnet, serial_generator=Mock()).as_list(),
            MatchesSetwise(*expected_zones))

    def test_with_many_nodegroups_yields_many_zones(self):
        # This demonstrates ZoneGenerator in all-singing all-dancing mode.
        self.useFixture(RegionConfigurationFixture())
        Domain.objects.get_or_create(name="one")
        Domain.objects.get_or_create(name="two")
        nodegroups = [
            self.make_node_group(name="one", network=IPNetwork("10/29")),
            self.make_node_group(name="one", network=IPNetwork("11/29")),
            self.make_node_group(name="two", network=IPNetwork("20/29")),
            self.make_node_group(name="two", network=IPNetwork("21/29")),
            ]
        # Other nodegroups.
        self.make_node_group(name="one", network=IPNetwork("12/29")),
        self.make_node_group(name="two", network=IPNetwork("22/29")),
        default_domain = Domain.objects.get_default_domain()
        domains = Domain.objects.filter(name__in=("one", "two"))
        subnets = Subnet.objects.filter(
            nodegroupinterface__nodegroup__in=nodegroups)
        expected_zones = (
            # For the forward zones, all nodegroups sharing a domain name,
            # even those not passed into ZoneGenerator, are consolidated into
            # a single forward zone description.
            forward_zone("one"),
            forward_zone("two"),
            # For the reverse zones, a single reverse zone description is
            # generated for each nodegroup passed in, in network order.
            reverse_zone(default_domain.name, "10/29"),
            reverse_zone(default_domain.name, "11/29"),
            reverse_zone(default_domain.name, "20/29"),
            reverse_zone(default_domain.name, "21/29"),
            )
        self.assertThat(
            ZoneGenerator(domains, subnets, serial_generator=Mock()).as_list(),
            MatchesSetwise(*expected_zones))


class TestZoneGeneratorTTL(MAASServerTestCase):
    """Tests for TTL in :class:ZoneGenerator`."""

    def test_domain_ttl_overrides_global(self):
        self.patch_autospec(interface_module, "update_host_maps")
        global_ttl = random.randint(100, 199)
        Config.objects.set_config('default_dns_ttl', global_ttl)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        subnet = factory.make_Subnet(cidr="10.0.0.0/23")
        domain = factory.make_Domain(ttl=random.randint(200, 299))
        node = factory.make_Node_with_Interface_on_Subnet(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            disable_ipv4=False,
            nodegroup=nodegroup, status=NODE_STATUS.READY, subnet=subnet,
            domain=domain)
        boot_iface = node.get_boot_interface()
        [boot_ip] = boot_iface.claim_static_ips()
        expected_forward = {node.hostname: (domain.ttl, [boot_ip.ip])}
        expected_reverse = {
            node.fqdn: (domain.ttl, [boot_ip.ip]),
            "%s.%s" % (boot_iface.name, node.fqdn): (domain.ttl, [boot_ip.ip])}
        zones = ZoneGenerator(
            domain, subnet, default_ttl=global_ttl,
            serial_generator=Mock()).as_list()
        self.assertItemsEqual(
            expected_forward.items(), zones[0]._mapping.items())
        self.assertItemsEqual(
            expected_reverse.items(), zones[1]._mapping.items())

    def test_node_ttl_overrides_domain(self):
        self.patch_autospec(interface_module, "update_host_maps")
        global_ttl = random.randint(100, 199)
        Config.objects.set_config('default_dns_ttl', global_ttl)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        subnet = factory.make_Subnet(cidr="10.0.0.0/23")
        domain = factory.make_Domain(ttl=random.randint(200, 299))
        node = factory.make_Node_with_Interface_on_Subnet(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            disable_ipv4=False,
            nodegroup=nodegroup, status=NODE_STATUS.READY, subnet=subnet,
            domain=domain, address_ttl=random.randint(300, 399))
        boot_iface = node.get_boot_interface()
        [boot_ip] = boot_iface.claim_static_ips()
        expected_forward = {node.hostname: (node.address_ttl, [boot_ip.ip])}
        expected_reverse = {
            node.fqdn: (node.address_ttl, [boot_ip.ip]),
            "%s.%s" % (boot_iface.name, node.fqdn):
            (node.address_ttl, [boot_ip.ip])}
        zones = ZoneGenerator(
            domain, subnet, default_ttl=global_ttl,
            serial_generator=Mock()).as_list()
        self.assertItemsEqual(
            expected_forward.items(), zones[0]._mapping.items())
        self.assertItemsEqual(
            expected_reverse.items(), zones[1]._mapping.items())

    def test_dnsresource_address_does_not_affect_addresses_when_node_set(self):
        # If a node has the same FQDN as a DNSResource, then we use whatever
        # address_ttl there is on the Node (whether None, or not) rather than
        # that on any DNSResource addresses with the same FQDN.
        self.patch_autospec(interface_module, "update_host_maps")
        global_ttl = random.randint(100, 199)
        Config.objects.set_config('default_dns_ttl', global_ttl)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        subnet = factory.make_Subnet(cidr="10.0.0.0/23")
        domain = factory.make_Domain(ttl=random.randint(200, 299))
        node = factory.make_Node_with_Interface_on_Subnet(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            disable_ipv4=False,
            nodegroup=nodegroup, status=NODE_STATUS.READY, subnet=subnet,
            domain=domain, address_ttl=random.randint(300, 399))
        boot_iface = node.get_boot_interface()
        [boot_ip] = boot_iface.claim_static_ips()
        dnsrr = factory.make_DNSResource(
            name=node.hostname, domain=domain,
            address_ttl=random.randint(400, 499))
        ips = [boot_ip.ip] + [
            ip.ip for ip in dnsrr.ip_addresses.all() if ip is not None]
        expected_forward = {node.hostname: (node.address_ttl, ips)}
        expected_reverse = {
            node.fqdn: (node.address_ttl, ips),
            "%s.%s" % (boot_iface.name, node.fqdn):
            (node.address_ttl, [boot_ip.ip])}
        zones = ZoneGenerator(
            domain, subnet, default_ttl=global_ttl,
            serial_generator=Mock()).as_list()
        self.assertItemsEqual(
            expected_forward.items(), zones[0]._mapping.items())
        self.assertItemsEqual(
            expected_reverse.items(), zones[1]._mapping.items())

    def test_dnsresource_address_overrides_domain(self):
        # DNSResource.address_ttl _does_, however, override Domain.ttl for
        # addresses that do not have nodes associated with them.
        self.patch_autospec(interface_module, "update_host_maps")
        global_ttl = random.randint(100, 199)
        Config.objects.set_config('default_dns_ttl', global_ttl)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        subnet = factory.make_Subnet(cidr="10.0.0.0/23")
        domain = factory.make_Domain(ttl=random.randint(200, 299))
        node = factory.make_Node_with_Interface_on_Subnet(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            disable_ipv4=False,
            nodegroup=nodegroup, status=NODE_STATUS.READY, subnet=subnet,
            domain=domain, address_ttl=random.randint(300, 399))
        boot_iface = node.get_boot_interface()
        [boot_ip] = boot_iface.claim_static_ips()
        dnsrr = factory.make_DNSResource(
            domain=domain, address_ttl=random.randint(400, 499))
        node_ips = [boot_ip.ip]
        dnsrr_ips = [
            ip.ip for ip in dnsrr.ip_addresses.all() if ip is not None]
        expected_forward = {
            node.hostname: (node.address_ttl, node_ips),
            dnsrr.name: (dnsrr.address_ttl, dnsrr_ips),
            }
        expected_reverse = {
            node.fqdn: (node.address_ttl, node_ips),
            dnsrr.fqdn: (dnsrr.address_ttl, dnsrr_ips),
            "%s.%s" % (boot_iface.name, node.fqdn):
            (node.address_ttl, [boot_ip.ip])}
        zones = ZoneGenerator(
            domain, subnet, default_ttl=global_ttl,
            serial_generator=Mock()).as_list()
        self.assertItemsEqual(
            expected_forward.items(), zones[0]._mapping.items())
        self.assertItemsEqual(
            expected_reverse.items(), zones[1]._mapping.items())

    def test_dnsdata_inherits_global(self):
        # If there is no ttl on the DNSData or Domain, then we get the global
        # value.
        self.patch_autospec(interface_module, "update_host_maps")
        global_ttl = random.randint(100, 199)
        Config.objects.set_config('default_dns_ttl', global_ttl)
        subnet = factory.make_Subnet(cidr="10.0.0.0/23")
        domain = factory.make_Domain()
        dnsrr = factory.make_DNSResource(
            no_ip_addresses=True,
            domain=domain, address_ttl=random.randint(400, 499))
        dnsdata = factory.make_DNSData(dnsresource=dnsrr)
        expected_forward = {dnsrr.name: (global_ttl, [str(dnsdata)])}
        zones = ZoneGenerator(
            domain, subnet, default_ttl=global_ttl,
            serial_generator=Mock()).as_list()
        self.assertItemsEqual(
            expected_forward.items(), zones[0]._other_mapping.items())
        self.assertItemsEqual([], zones[0]._mapping.items())
        self.assertItemsEqual([], zones[1]._mapping.items())
        self.assertEqual(None, dnsdata.ttl)

    def test_dnsdata_inherits_domain(self):
        # If there is no ttl on the DNSData, but is on Domain, then we get the
        # domain value.
        self.patch_autospec(interface_module, "update_host_maps")
        global_ttl = random.randint(100, 199)
        Config.objects.set_config('default_dns_ttl', global_ttl)
        subnet = factory.make_Subnet(cidr="10.0.0.0/23")
        domain = factory.make_Domain(ttl=random.randint(200, 299))
        dnsrr = factory.make_DNSResource(
            no_ip_addresses=True,
            domain=domain, address_ttl=random.randint(400, 499))
        dnsdata = factory.make_DNSData(dnsresource=dnsrr)
        expected_forward = {dnsrr.name: (domain.ttl, [str(dnsdata)])}
        zones = ZoneGenerator(
            domain, subnet, default_ttl=global_ttl,
            serial_generator=Mock()).as_list()
        self.assertItemsEqual(
            expected_forward.items(), zones[0]._other_mapping.items())
        self.assertItemsEqual([], zones[0]._mapping.items())
        self.assertItemsEqual([], zones[1]._mapping.items())
        self.assertEqual(None, dnsdata.ttl)

    def test_dnsdata_overrides_domain(self):
        # If DNSData has a ttl, we use that in preference to anything else.
        self.patch_autospec(interface_module, "update_host_maps")
        global_ttl = random.randint(100, 199)
        Config.objects.set_config('default_dns_ttl', global_ttl)
        subnet = factory.make_Subnet(cidr="10.0.0.0/23")
        domain = factory.make_Domain(ttl=random.randint(200, 299))
        dnsrr = factory.make_DNSResource(
            no_ip_addresses=True,
            domain=domain, address_ttl=random.randint(400, 499))
        dnsdata = factory.make_DNSData(
            dnsresource=dnsrr, ttl=random.randint(500, 599))
        expected_forward = {dnsrr.name: (dnsdata.ttl, [str(dnsdata)])}
        zones = ZoneGenerator(
            domain, subnet, default_ttl=global_ttl,
            serial_generator=Mock()).as_list()
        self.assertItemsEqual(
            expected_forward.items(), zones[0]._other_mapping.items())
        self.assertItemsEqual([], zones[0]._mapping.items())
        self.assertItemsEqual([], zones[1]._mapping.items())
