# Copyright 2012-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from argparse import ArgumentParser
import random
import time

from django.conf import settings
import dns.resolver
from netaddr import IPAddress, IPNetwork
from testtools.matchers import (
    Contains,
    Equals,
    FileContains,
    HasLength,
    MatchesSetwise,
    MatchesStructure,
)

from maasserver.config import RegionConfiguration
from maasserver.dns import config as dns_config_module
from maasserver.dns.config import (
    current_zone_serial,
    dns_force_reload,
    dns_update_all_zones,
    forward_domains_to_forwarded_zones,
    get_internal_domain,
    get_resource_name_for_subnet,
    get_reverse_zone_for_answer,
    get_trusted_acls,
    get_trusted_networks,
    get_upstream_dns,
    process_dns_update_notify,
)
from maasserver.dns.zonegenerator import InternalDomainResourseRecord
from maasserver.enum import IPADDRESS_TYPE, NODE_STATUS
from maasserver.listener import PostgresListenerService
from maasserver.models import Config, Domain
from maasserver.models.dnspublication import DNSPublication
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from provisioningserver.dns.commands import get_named_conf, setup_dns
from provisioningserver.dns.config import (
    compose_config_path,
    DNSConfig,
    DynamicDNSUpdate,
)
from provisioningserver.dns.testing import (
    patch_dns_config_path,
    patch_dns_rndc_port,
    patch_zone_file_config_path,
)
from provisioningserver.testing.bindfixture import allocate_ports, BINDServer
from provisioningserver.testing.tests.test_bindfixture import dig_call
from provisioningserver.utils.twisted import retries

RELOAD_TIMEOUT = 30


class TestDNSUtilities(MAASServerTestCase):
    def make_listener_without_delay(self):
        listener = PostgresListenerService()
        self.patch(listener, "HANDLE_NOTIFY_DELAY", 0)
        return listener

    def test_current_zone_serial_returns_serial_of_latest_publication(self):
        publication = DNSPublication(source=factory.make_name("source"))
        publication.save()
        self.assertEqual(publication.serial, int(current_zone_serial()))

    def test_dns_force_reload_saves_new_publication(self):
        # A 'sys_dns' signal is also sent, but that is a side-effect of
        # inserting into the DNS publications table, and is tested as part of
        # the system triggers code.
        self.assertThat(
            DNSPublication.objects.get_most_recent(),
            MatchesStructure.byEquality(source="Initial publication"),
        )
        dns_force_reload()
        self.assertThat(
            DNSPublication.objects.get_most_recent(),
            MatchesStructure.byEquality(source="Force reload"),
        )

    def test_forward_domains_to_forwarded_zones(self):
        name1 = factory.make_name("domain")
        name2 = factory.make_name("other")
        domain1 = factory.make_Domain(name=name1)
        domain2 = factory.make_Domain(name=name2)
        ip1 = factory.make_ip_address()
        ip2 = factory.make_ip_address()
        fwd_srvr1 = factory.make_ForwardDNSServer(
            ip_address=ip1, domains=[domain1]
        )
        fwd_srvr2 = factory.make_ForwardDNSServer(
            ip_address=ip2, domains=[domain2]
        )
        fwd_zones = forward_domains_to_forwarded_zones(
            Domain.objects.get_forward_domains()
        )
        self.assertCountEqual(
            fwd_zones,
            [
                (name1, [(fwd_srvr1.ip_address, fwd_srvr1.port)]),
                (name2, [(fwd_srvr2.ip_address, fwd_srvr2.port)]),
            ],
        )


class TestDNSServer(MAASServerTestCase):
    """A base class to perform real-world DNS-related tests.

    The class starts a BINDServer for every test and provides a set of
    helper methods to perform DNS queries.

    Because of the overhead added by starting and stopping the DNS
    server, new tests in this class and its descendants are expensive.
    """

    def setUp(self):
        super().setUp()
        # Ensure there's an initial DNS publication. Outside of tests this is
        # guaranteed by a migration.
        DNSPublication(source="Initial").save()
        # Allow test-local changes to configuration.
        self.useFixture(RegionConfigurationFixture())
        # Immediately make DNS changes as they're needed.
        self.patch(dns_config_module, "DNS_DEFER_UPDATES", False)
        # Create a DNS server.
        self.bind = self.useFixture(BINDServer())
        # Use the dnspython resolver for at least some queries.
        self.resolver = dns.resolver.Resolver()
        self.resolver.nameservers = ["127.0.0.1"]
        self.resolver.port = self.bind.config.port
        patch_dns_config_path(self, self.bind.config.homedir)
        # Use a random port for rndc.
        patch_dns_rndc_port(self, allocate_ports("localhost")[0])
        patch_zone_file_config_path(self, config_dir=self.bind.config.zonedir)
        # This simulates what should happen when the package is
        # installed:
        # Create MAAS-specific DNS configuration files.
        parser = ArgumentParser()
        setup_dns.add_arguments(parser)
        setup_dns.run(parser.parse_args([]))
        # Register MAAS-specific DNS configuration files with the
        # system's BIND instance.
        parser = ArgumentParser()
        get_named_conf.add_arguments(parser)
        get_named_conf.run(
            parser.parse_args(
                ["--edit", "--config-path", self.bind.config.conf_file]
            )
        )
        # Reload BIND.
        self.bind.runner.rndc("reload")

    def create_node_with_static_ip(self, domain=None, subnet=None):
        if domain is None:
            domain = Domain.objects.get_default_domain()
        if subnet is None:
            network = factory.make_ipv4_network()
            subnet = factory.make_Subnet(cidr=str(network.cidr))
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.READY, domain=domain
        )
        nic = node.get_boot_interface()
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=nic,
        )
        return node, static_ip

    def create_rack_with_static_ip(self, subnet=None):
        if subnet is None:
            network = factory.make_ipv4_network()
            subnet = factory.make_Subnet(cidr=str(network.cidr))
        rack = factory.make_RackController(interface=True)
        nic = rack.get_boot_interface()
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=nic,
        )
        return rack, static_ip

    def dns_wait_soa(self, fqdn, removing=False):
        # Get the serial number for the zone containing the FQDN by asking DNS
        # nicely for the SOA for the FQDN.  If it's top-of-zone, we get an
        # answer, if it's not, we get the SOA in authority.

        if not fqdn.endswith("."):
            fqdn = fqdn + "."

        for elapsed, remaining, wait in retries(15, 0.02):
            query_name = fqdn

            # Loop until we have a value for serial, be that numeric or None.
            serial = undefined = object()
            while serial is undefined:
                try:
                    ans = self.resolver.resolve(
                        query_name, "SOA", raise_on_no_answer=False
                    )
                except dns.resolver.NXDOMAIN:
                    if removing:
                        # The zone has gone; we're done.
                        return
                    elif "." in query_name:
                        # Query the parent domain for the SOA record.
                        # For most things, this will be the correct DNS zone.
                        # In the case of SRV records, we'll actually need to
                        # strip more, hence the loop.
                        query_name = query_name.split(".", 1)[1]
                    else:
                        # We've hit the root zone; no SOA found.
                        serial = None
                except dns.resolver.NoNameservers:
                    # No DNS service as yet.
                    serial = None
                else:
                    # If we got here, then we either have (1) a situation where
                    # the LHS exists in the DNS, but no SOA RR exists for that
                    # LHS (because it's a node with an A or AAAA RR, and not
                    # the domain...) or (2) an answer to our SOA query.
                    # Either way, we get exactly one SOA in the reply: in the
                    # first case, it's in the Authority section, in the second,
                    # it's in the Answer section.
                    rrset = (
                        ans.rrset
                        if ans.rrset is not None
                        else ans.response.authority[0]
                    )
                    # items are tracked as a dict where the key is the item and
                    # value is None. Future versions provide a pop() method
                    # directly on the rrset to get the item
                    serial = rrset.items.popitem()[0].serial

            if serial == DNSPublication.objects.get_most_recent().serial:
                # The zone is up-to-date; we're done.
                return
            else:
                time.sleep(wait)

        self.fail("Timed-out waiting for %s to update." % fqdn)

    def dig_resolve(self, fqdn, version=4, removing=False):
        """Resolve `fqdn` using dig.  Returns a list of results."""
        # Using version=6 has two effects:
        # - it changes the type of query from 'A' to 'AAAA';
        # - it forces dig to only use IPv6 query transport.
        self.dns_wait_soa(fqdn, removing)
        record_type = "AAAA" if version == 6 else "A"
        commands = [fqdn, "+short", "-%i" % version, record_type]
        output = dig_call(port=self.bind.config.port, commands=commands)
        return output.split("\n")

    def dig_reverse_resolve(self, ip, version=4, removing=False):
        """Reverse resolve `ip` using dig.  Returns a list of results."""
        self.dns_wait_soa(IPAddress(ip).reverse_dns, removing)
        output = dig_call(
            port=self.bind.config.port,
            commands=["-x", ip, "+short", "-%i" % version],
        )
        return output.split("\n")

    def assertDNSMatches(self, hostname, domain, ip, version=-1, reverse=True):
        # A forward lookup on the hostname returns the IP address.
        if version == -1:
            version = IPAddress(ip).version
        fqdn = f"{hostname}.{domain}"
        # Give BIND enough time to process the rndc request.
        # XXX 2016-03-01 lamont bug=1550540 We should really query DNS for the
        # SOA that we (can) know to be the correct one, and wait for that
        # before we do the actual DNS lookup.  For now, rely on the fact that
        # all of our tests go from having no answer for forward and/or reverse,
        # to having the expected answer, and just wait for a non-empty return,
        # or timeout (15 seconds because of slow jenkins sometimes.)
        forward_lookup_result = self.dig_resolve(fqdn, version=version)
        self.assertThat(
            forward_lookup_result,
            Contains(ip),
            "Failed to resolve '%s' (results: '%s')."
            % (fqdn, ",".join(forward_lookup_result)),
        )
        # A reverse lookup on the IP address returns the hostname.
        if reverse:
            reverse_lookup_result = self.dig_reverse_resolve(
                ip, version=version
            )
            self.assertThat(
                reverse_lookup_result,
                Contains("%s." % fqdn),
                "Failed to reverse resolve '%s' missing '%s' "
                "(results: '%s')."
                % (ip, "%s." % fqdn, ",".join(reverse_lookup_result)),
            )


class TestDNSConfigModifications(TestDNSServer):
    def test_dns_update_all_zones_loads_full_dns_config(self):
        self.patch(settings, "DNS_CONNECT", True)
        node, static = self.create_node_with_static_ip()
        dns_update_all_zones(reload_timeout=RELOAD_TIMEOUT)
        self.assertDNSMatches(node.hostname, node.domain.name, static.ip)

    def test_dns_update_all_zones_includes_internal_domain(self):
        self.patch(settings, "DNS_CONNECT", True)
        rack, static = self.create_rack_with_static_ip()
        factory.make_RegionRackRPCConnection(rack)
        dns_update_all_zones(reload_timeout=RELOAD_TIMEOUT)
        resource_name = get_resource_name_for_subnet(static.subnet)
        self.assertDNSMatches(
            resource_name,
            Config.objects.get_config("maas_internal_domain"),
            static.ip,
            reverse=False,
        )

    def test_dns_update_all_zones_includes_multiple_racks(self):
        self.patch(settings, "DNS_CONNECT", True)
        rack1, static1 = self.create_rack_with_static_ip()
        factory.make_RegionRackRPCConnection(rack1)
        rack2, static2 = self.create_rack_with_static_ip(subnet=static1.subnet)
        factory.make_RegionRackRPCConnection(rack2)
        dns_update_all_zones(reload_timeout=RELOAD_TIMEOUT)
        resource_name = get_resource_name_for_subnet(static1.subnet)
        self.assertDNSMatches(
            resource_name,
            Config.objects.get_config("maas_internal_domain"),
            static1.ip,
            reverse=False,
        )
        self.assertDNSMatches(
            resource_name,
            Config.objects.get_config("maas_internal_domain"),
            static2.ip,
            reverse=False,
        )

    def test_dns_update_all_zones_passes_reload_retry_parameter(self):
        self.patch(settings, "DNS_CONNECT", True)
        bind_reload_with_retries = self.patch_autospec(
            dns_config_module, "bind_reload_with_retries"
        )
        dns_update_all_zones(reload_retry=True)
        self.assertThat(
            bind_reload_with_retries, MockCalledOnceWith(timeout=2)
        )

    def test_dns_update_all_zones_passes_upstream_dns_parameter(self):
        self.patch(settings, "DNS_CONNECT", True)
        random_ip = factory.make_ipv4_address()
        Config.objects.set_config("upstream_dns", random_ip)
        bind_write_options = self.patch_autospec(
            dns_config_module, "bind_write_options"
        )
        dns_update_all_zones(reload_retry=RELOAD_TIMEOUT)
        self.assertThat(
            bind_write_options,
            MockCalledOnceWith(
                dnssec_validation="auto", upstream_dns=[random_ip]
            ),
        )

    def test_dns_update_all_zones_writes_trusted_networks_parameter(self):
        self.patch(settings, "DNS_CONNECT", True)
        trusted_network = factory.make_ipv4_address()
        get_trusted_networks_patch = self.patch(
            dns_config_module, "get_trusted_networks"
        )
        get_trusted_networks_patch.return_value = [trusted_network]
        dns_update_all_zones(reload_retry=RELOAD_TIMEOUT)
        self.assertThat(
            compose_config_path(DNSConfig.target_file_name),
            FileContains(matcher=Contains(trusted_network)),
        )

    def test_dns_update_all_zones_writes_trusted_networks_params_extra(self):
        self.patch(settings, "DNS_CONNECT", True)
        extra_trusted_network = factory.make_ipv6_network()
        get_trusted_acls_patch = self.patch(
            dns_config_module, "get_trusted_acls"
        )
        get_trusted_acls_patch.return_value = [extra_trusted_network.cidr]
        dns_update_all_zones(reload_retry=RELOAD_TIMEOUT)
        self.assertThat(
            compose_config_path(DNSConfig.target_file_name),
            FileContains(matcher=Contains(str(extra_trusted_network))),
        )

    def test_dns_config_has_NS_record(self):
        self.patch(settings, "DNS_CONNECT", True)
        ip = factory.make_ipv4_address()
        with RegionConfiguration.open_for_update() as config:
            config.maas_url = "http://%s/" % ip
        domain = factory.make_Domain()
        node, static = self.create_node_with_static_ip(domain=domain)
        dns_update_all_zones(reload_retry=RELOAD_TIMEOUT)
        # Creating the domain triggered writing the zone file and updating the
        # DNS.
        self.dns_wait_soa(domain.name)
        # Get the NS record for the zone 'domain.name'.
        ns_record = dig_call(
            port=self.bind.config.port, commands=[domain.name, "NS", "+short"]
        )
        self.assertGreater(len(ns_record), 0, "No NS record for domain.name.")
        # Resolve that hostname.
        self.dns_wait_soa(ns_record)
        ip_of_ns_record = dig_call(
            port=self.bind.config.port, commands=[ns_record, "+short"]
        )
        self.assertEqual(ip, ip_of_ns_record)

    def test_dns_update_all_zones_returns_serial_and_domains(self):
        self.patch(settings, "DNS_CONNECT", True)
        domain = factory.make_Domain()
        # These domains should not show up. Just to test we create them.
        for _ in range(3):
            factory.make_Domain(authoritative=False)
        node, static = self.create_node_with_static_ip(domain=domain)
        fake_serial = random.randint(1, 1000)
        self.patch(
            dns_config_module, "current_zone_serial"
        ).return_value = fake_serial
        serial, reloaded, domains = dns_update_all_zones(
            reload_timeout=RELOAD_TIMEOUT
        )
        self.assertEqual(fake_serial, serial)
        self.assertTrue(reloaded)
        self.assertThat(
            domains,
            MatchesSetwise(
                *[
                    Equals(domain.name)
                    for domain in Domain.objects.filter(authoritative=True)
                ]
            ),
        )

    def test_dns_update_all_zones_does_not_reload_if_it_does_not_need_to(self):
        self.patch(settings, "DNS_CONNECT", True)
        domain = factory.make_Domain()
        # These domains should not show up. Just to test we create them.
        for _ in range(3):
            factory.make_Domain(authoritative=False)
        node, static = self.create_node_with_static_ip(domain=domain)
        fake_serial = random.randint(1, 1000)
        self.patch(
            dns_config_module, "current_zone_serial"
        ).return_value = fake_serial
        reload_call = self.patch(dns_config_module, "bind_reload")
        serial1, reloaded, _ = dns_update_all_zones(
            reload_timeout=RELOAD_TIMEOUT
        )
        self.assertTrue(reloaded)
        factory.make_DNSResource(domain=domain)
        _, _, _ = dns_update_all_zones(  # should be a dynamic update
            reload_timeout=RELOAD_TIMEOUT
        )
        reload_call.assert_called_once()


class TestDNSDynamicIPAddresses(TestDNSServer):
    """Allocated nodes with IP addresses in the dynamic range get a DNS
    record.
    """

    def test_bind_configuration_includes_dynamic_ips_of_deployed_nodes(self):
        self.patch(settings, "DNS_CONNECT", True)
        subnet = factory.make_ipv4_Subnet_with_IPRanges()
        node = factory.make_Node(interface=True, status=NODE_STATUS.DEPLOYED)
        nic = node.get_boot_interface()
        # Get an IP in the dynamic range.
        dynamic_range = subnet.get_dynamic_ranges()[0]
        ip = factory.pick_ip_in_IPRange(dynamic_range)
        ip_obj = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            ip=ip,
            subnet=subnet,
            interface=nic,
        )
        dns_update_all_zones(reload_timeout=RELOAD_TIMEOUT)
        self.assertDNSMatches(node.hostname, node.domain.name, ip_obj.ip)


class TestDNSResource(TestDNSServer):
    """Tests for DNSResource records."""

    def test_dnsresources_are_in_the_dns(self):
        self.patch(settings, "DNS_CONNECT", True)
        domain = factory.make_Domain()
        subnet = factory.make_ipv4_Subnet_with_IPRanges()
        dynamic_range = subnet.get_dynamic_ranges()[0]
        ip = factory.pick_ip_in_IPRange(dynamic_range)
        ip_obj = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, ip=ip, subnet=subnet
        )
        rrname = factory.make_name("label")
        dnsrr = factory.make_DNSResource(
            name=rrname, domain=domain, ip_addresses=[ip_obj]
        )
        dns_update_all_zones(reload_timeout=RELOAD_TIMEOUT)
        self.assertDNSMatches(dnsrr.name, domain.name, ip_obj.ip)


class TestIPv6DNS(TestDNSServer):
    def test_bind_configuration_includes_ipv6_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        network = factory.make_ipv6_network(slash=random.randint(118, 125))
        subnet = factory.make_Subnet(cidr=str(network.cidr))
        node, static = self.create_node_with_static_ip(subnet=subnet)
        dns_update_all_zones(reload_timeout=RELOAD_TIMEOUT)
        self.assertDNSMatches(
            node.hostname, node.domain.name, static.ip, version=6
        )


class TestGetUpstreamDNS(MAASServerTestCase):
    """Test for maasserver/dns/config.py:get_upstream_dns()"""

    def test_returns_empty_list_if_not_set(self):
        self.assertEqual([], get_upstream_dns())

    def test_returns_list_of_one_address_if_set(self):
        address = factory.make_ip_address()
        Config.objects.set_config("upstream_dns", address)
        self.assertEqual([address], get_upstream_dns())

    def test_returns_list_if_space_separated_ips(self):
        addresses = [factory.make_ip_address() for _ in range(3)]
        Config.objects.set_config("upstream_dns", " ".join(addresses))
        self.assertEqual(addresses, get_upstream_dns())


class TestGetTrustedAcls(MAASServerTestCase):
    """Test for maasserver/dns/config.py:get_trusted_acls()"""

    def setUp(self):
        super().setUp()
        self.useFixture(RegionConfigurationFixture())

    def test_returns_empty_string_if_no_networks(self):
        self.assertEqual([], get_trusted_acls())

    def test_returns_single_network(self):
        subnet = factory.make_ipv6_network()
        Config.objects.set_config("dns_trusted_acl", str(subnet))
        expected = [str(subnet)]
        self.assertEqual(expected, get_trusted_acls())

    def test_returns_many_networks(self):
        subnets = [
            str(factory.make_ipv4_network())
            for _ in range(random.randint(1, 5))
        ]
        actual_subnets = " ".join(subnets)
        Config.objects.set_config("dns_trusted_acl", str(actual_subnets))
        expected = [subnet for subnet in subnets]
        # Note: This test was seen randomly failing because the networks were
        # in an unexpected order...
        self.assertCountEqual(expected, get_trusted_acls())


class TestGetTrustedNetworks(MAASServerTestCase):
    """Test for maasserver/dns/config.py:get_trusted_networks()"""

    def setUp(self):
        super().setUp()
        self.useFixture(RegionConfigurationFixture())

    def test_returns_empty_string_if_no_networks(self):
        self.assertEqual([], get_trusted_networks())

    def test_returns_single_network(self):
        subnet = factory.make_Subnet()
        expected = [str(subnet.cidr)]
        self.assertEqual(expected, get_trusted_networks())

    def test_returns_no_networks_if_not_allow_dns(self):
        factory.make_Subnet(allow_dns=False)
        subnet_allowed = factory.make_Subnet(allow_dns=True)
        expected = [str(subnet_allowed.cidr)]
        self.assertEqual(expected, get_trusted_networks())

    def test_returns_many_networks(self):
        subnets = [factory.make_Subnet() for _ in range(random.randint(1, 5))]
        expected = [str(subnet.cidr) for subnet in subnets]
        # Note: This test was seen randomly failing because the networks were
        # in an unexpected order...
        self.assertCountEqual(expected, get_trusted_networks())


class TestGetInternalDomain(MAASServerTestCase):
    """Test for maasserver/dns/config.py:get_internal_domain()"""

    def test_uses_maas_internal_domain_config(self):
        internal_domain = factory.make_name("internal")
        Config.objects.set_config("maas_internal_domain", internal_domain)
        domain = get_internal_domain()
        self.assertEqual(internal_domain, domain.name)

    def test_doesnt_add_disconnected_rack(self):
        rack = factory.make_RackController()
        # No `RegionRackRPCConnection` is being created so the rack is
        # disconnected.
        nic = rack.get_boot_interface()
        network = factory.make_ipv4_network()
        subnet = factory.make_Subnet(cidr=str(network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=nic,
        )
        domain = get_internal_domain()
        self.assertEqual(0, len(domain.resources))

    def test_adds_connected_rack_ipv4(self):
        rack = factory.make_RackController()
        factory.make_RegionRackRPCConnection(rack)
        nic = rack.get_boot_interface()
        network = factory.make_ipv4_network()
        subnet = factory.make_Subnet(cidr=str(network.cidr))
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=nic,
        )
        domain = get_internal_domain()
        self.assertEqual(
            get_resource_name_for_subnet(subnet), domain.resources[0].name
        )
        self.assertEqual(
            InternalDomainResourseRecord(rrtype="A", rrdata=static_ip.ip),
            domain.resources[0].records[0],
        )

    def test_adds_connected_rack_ipv6(self):
        rack = factory.make_RackController()
        factory.make_RegionRackRPCConnection(rack)
        nic = rack.get_boot_interface()
        network = factory.make_ipv6_network()
        subnet = factory.make_Subnet(cidr=str(network.cidr))
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=nic,
        )
        domain = get_internal_domain()
        self.assertEqual(
            get_resource_name_for_subnet(subnet), domain.resources[0].name
        )
        self.assertEqual(
            InternalDomainResourseRecord(rrtype="AAAA", rrdata=static_ip.ip),
            domain.resources[0].records[0],
        )

    def test_adds_connected_multiple_racks_ipv4(self):
        rack1 = factory.make_RackController()
        factory.make_RegionRackRPCConnection(rack1)
        rack2 = factory.make_RackController()
        factory.make_RegionRackRPCConnection(rack2)
        network = factory.make_ipv4_network()
        subnet = factory.make_Subnet(cidr=str(network.cidr))
        static_ip1 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=rack1.get_boot_interface(),
        )
        static_ip2 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=rack2.get_boot_interface(),
        )
        domain = get_internal_domain()
        self.assertEqual(
            get_resource_name_for_subnet(subnet), domain.resources[0].name
        )
        self.assertThat(
            domain.resources[0].records,
            MatchesSetwise(
                Equals(
                    InternalDomainResourseRecord(
                        rrtype="A", rrdata=static_ip1.ip
                    )
                ),
                Equals(
                    InternalDomainResourseRecord(
                        rrtype="A", rrdata=static_ip2.ip
                    )
                ),
            ),
        )

    def test_adds_connected_multiple_racks_ipv6(self):
        rack1 = factory.make_RackController()
        factory.make_RegionRackRPCConnection(rack1)
        rack2 = factory.make_RackController()
        factory.make_RegionRackRPCConnection(rack2)
        network = factory.make_ipv6_network()
        subnet = factory.make_Subnet(cidr=str(network.cidr))
        static_ip1 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=rack1.get_boot_interface(),
        )
        static_ip2 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=rack2.get_boot_interface(),
        )
        domain = get_internal_domain()
        self.assertEqual(
            get_resource_name_for_subnet(subnet), domain.resources[0].name
        )
        self.assertThat(
            domain.resources[0].records,
            MatchesSetwise(
                Equals(
                    InternalDomainResourseRecord(
                        rrtype="AAAA", rrdata=static_ip1.ip
                    )
                ),
                Equals(
                    InternalDomainResourseRecord(
                        rrtype="AAAA", rrdata=static_ip2.ip
                    )
                ),
            ),
        )

    def test_prefers_static_ip_over_dhcp(self):
        rack = factory.make_RackController()
        factory.make_RegionRackRPCConnection(rack)
        nic = rack.get_boot_interface()
        network = factory.make_ipv4_network()
        subnet = factory.make_Subnet(cidr=str(network.cidr))
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=nic,
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=nic,
        )
        domain = get_internal_domain()
        self.assertThat(domain.resources, HasLength(1))
        self.assertEqual(
            get_resource_name_for_subnet(subnet), domain.resources[0].name
        )
        self.assertEqual(
            InternalDomainResourseRecord(rrtype="A", rrdata=static_ip.ip),
            domain.resources[0].records[0],
        )


class TestGetResourceNameForSubnet(MAASServerTestCase):
    """Test for maasserver/dns/config.py:get_resource_name_for_subnet()"""

    scenarios = (
        ("10.0.0.0/8", {"cidr": "10.0.0.0/8", "result": "10-0-0-0--8"}),
        (
            "192.168.1.0/24",
            {"cidr": "192.168.1.0/24", "result": "192-168-1-0--24"},
        ),
        (
            "2001:db8:0::/64",
            {"cidr": "2001:db8:0::/64", "result": "2001-db8----64"},
        ),
    )

    def test_returns_valid(self):
        subnet = factory.make_Subnet(cidr=self.cidr)
        self.assertEqual(self.result, get_resource_name_for_subnet(subnet))


class TestProcessDNSUpdateNotify(MAASServerTestCase):
    def test_insert(self):
        domain = factory.make_Domain()
        resource = factory.make_DNSResource(domain=domain)
        ip = resource.ip_addresses.first().ip
        message = f"INSERT {domain.name} {resource.name} A {resource.address_ttl if resource.address_ttl else 60} {ip}"
        result, _ = process_dns_update_notify(message)
        self.assertCountEqual(
            [
                DynamicDNSUpdate(
                    operation="INSERT",
                    zone=domain.name,
                    rev_zone=get_reverse_zone_for_answer(ip),
                    name=f"{resource.name}.{domain.name}",
                    ttl=resource.address_ttl if resource.address_ttl else 60,
                    answer=ip,
                    rectype="A" if IPAddress(ip).version == 4 else "AAAA",
                )
            ],
            result,
        )

    def test_delete_without_ip(self):
        domain = factory.make_Domain()
        resource = factory.make_DNSResource(domain=domain)
        message = f"DELETE {domain.name} {resource.name} A"
        result, _ = process_dns_update_notify(message)
        self.assertCountEqual(
            [
                DynamicDNSUpdate(
                    operation="DELETE",
                    zone=domain.name,
                    name=f"{resource.name}.{domain.name}",
                    rectype="A",
                )
            ],
            result,
        )

    def test_delete_with_ip(self):
        domain = factory.make_Domain()
        resource = factory.make_DNSResource(domain=domain)
        ip = resource.ip_addresses.first().ip
        message = f"DELETE {domain.name} {resource.name} A {ip}"
        result, _ = process_dns_update_notify(message)
        self.assertCountEqual(
            [
                DynamicDNSUpdate(
                    operation="DELETE",
                    zone=domain.name,
                    name=f"{resource.name}.{domain.name}",
                    answer=ip,
                    rectype="A" if IPAddress(ip).version == 4 else "AAAA",
                )
            ],
            result,
        )

    def test_update(self):
        domain = factory.make_Domain()
        resource = factory.make_DNSResource(domain=domain)
        ip = resource.ip_addresses.first().ip
        message = f"UPDATE {domain.name} {resource.name} A {resource.address_ttl if resource.address_ttl else 60} {ip}"
        result, _ = process_dns_update_notify(message)
        self.assertCountEqual(
            [
                DynamicDNSUpdate(
                    operation="DELETE",
                    zone=domain.name,
                    rev_zone=get_reverse_zone_for_answer(ip),
                    name=f"{resource.name}.{domain.name}",
                    answer=ip,
                    rectype="A" if IPAddress(ip).version == 4 else "AAAA",
                ),
                DynamicDNSUpdate(
                    operation="INSERT",
                    zone=domain.name,
                    rev_zone=get_reverse_zone_for_answer(ip),
                    name=f"{resource.name}.{domain.name}",
                    ttl=resource.address_ttl if resource.address_ttl else 60,
                    answer=ip,
                    rectype="A" if IPAddress(ip).version == 4 else "AAAA",
                ),
            ],
            result,
        )

    def test_delete_ip(self):
        domain = factory.make_Domain()
        resource = factory.make_DNSResource(domain=domain)
        ip = resource.ip_addresses.first().ip
        subnet = factory.make_Subnet()
        ip2 = factory.make_StaticIPAddress(
            subnet=subnet, ip=subnet.get_next_ip_for_allocation()[0]
        )
        resource.ip_addresses.add(ip2)
        message = f"DELETE-IP {domain.name} {resource.name} A {resource.address_ttl if resource.address_ttl else 60} {ip}"
        resource.ip_addresses.first().delete()
        result, _ = process_dns_update_notify(message)
        self.assertCountEqual(
            [
                DynamicDNSUpdate(
                    operation="DELETE",
                    zone=domain.name,
                    name=f"{resource.name}.{domain.name}",
                    rectype="A",
                ),
                DynamicDNSUpdate(
                    operation="DELETE",
                    zone=domain.name,
                    name=f"{resource.name}.{domain.name}",
                    rectype="AAAA",
                ),
                DynamicDNSUpdate(
                    operation="INSERT",
                    zone=domain.name,
                    rev_zone=get_reverse_zone_for_answer(ip2.ip),
                    name=f"{resource.name}.{domain.name}",
                    rectype="A" if IPAddress(ip2.ip).version == 4 else "AAAA",
                    answer=ip2.ip,
                ),
            ],
            result,
        )

    def test_delete_iface_ip(self):
        domain = factory.make_Domain()
        node = factory.make_Node_with_Interface_on_Subnet()
        iface = node.current_config.interface_set.first()
        ip1 = iface.ip_addresses.first()
        ip2 = factory.make_StaticIPAddress(interface=iface)
        ip1.delete()
        message = f"DELETE-IFACE-IP {domain.name} {node.hostname} A {domain.ttl if domain.ttl else 60} {iface.id}"
        result, _ = process_dns_update_notify(message)
        self.assertCountEqual(
            [
                DynamicDNSUpdate(
                    operation="DELETE",
                    zone=domain.name,
                    name=f"{node.hostname}.{domain.name}",
                    rectype="A",
                ),
                DynamicDNSUpdate(
                    operation="DELETE",
                    zone=domain.name,
                    name=f"{node.hostname}.{domain.name}",
                    rectype="AAAA",
                ),
                DynamicDNSUpdate(
                    operation="INSERT",
                    zone=domain.name,
                    rev_zone=get_reverse_zone_for_answer(ip2.ip),
                    name=f"{node.hostname}.{domain.name}",
                    rectype="A" if IPAddress(ip2.ip).version == 4 else "AAAA",
                    answer=ip2.ip,
                ),
            ],
            result,
        )

    def test_insert_reverse_glue_zone(self):
        domain = factory.make_Domain()
        subnet = factory.make_Subnet(cidr="192.168.1.64/26")
        ip = subnet.get_next_ip_for_allocation()[0]
        resource = factory.make_DNSResource(domain=domain, ip=ip)
        message = f"INSERT {domain.name} {resource.name} A {resource.address_ttl if resource.address_ttl else 60} {ip}"
        zone = get_reverse_zone_for_answer(ip)
        result, _ = process_dns_update_notify(message)
        ip_split = ip.split(".")
        self.assertCountEqual(
            [
                DynamicDNSUpdate(
                    operation="INSERT",
                    zone=zone,
                    name=".".join([ip_split[-1], zone]),
                    ttl=resource.address_ttl if resource.address_ttl else 60,
                    subnet=subnet.cidr,
                    answer=f"{resource.name}.{domain.name}",
                    rectype="PTR",
                    ip=str(ip),
                )
            ],
            [
                DynamicDNSUpdate.as_reverse_record_update(
                    res, IPNetwork(subnet.cidr)
                )
                for res in result
            ],
        )


class TestGetReverseZoneForUpdate(MAASServerTestCase):
    def test_get_reverse_zone_for_answer_v4_24(self):
        subnet = factory.make_Subnet(cidr="192.168.1.0/24")
        ip = subnet.get_next_ip_for_allocation()[0]
        rev_zone = get_reverse_zone_for_answer(ip)
        self.assertEqual("1.168.192.in-addr.arpa", rev_zone)

    def test_get_reverse_zone_for_update_v4_26(self):
        subnet = factory.make_Subnet(cidr="192.168.1.0/26")
        ip = subnet.get_next_ip_for_allocation()[0]
        rev_zone = get_reverse_zone_for_answer(ip)
        self.assertEqual("0-26.1.168.192.in-addr.arpa", rev_zone)

    def test_get_reverse_zone_for_update_v6_64(self):
        subnet = factory.make_Subnet(cidr="de:ad:be:ef:ca::/64")
        ip = subnet.get_next_ip_for_allocation()[0]
        rev_zone = get_reverse_zone_for_answer(ip)
        self.assertEqual("f.e.0.0.e.b.0.0.d.a.0.0.e.d.0.0.ip6.arpa", rev_zone)

    def test_get_reverse_zone_for_update_v6_65(self):
        subnet = factory.make_Subnet(cidr="de:ad:be:ef:ca::/65")
        ip = subnet.get_next_ip_for_allocation()[0]
        rev_zone = get_reverse_zone_for_answer(ip)
        self.assertEqual(
            "0.f.e.0.0.e.b.0.0.d.a.0.0.e.d.0.0.ip6.arpa", rev_zone
        )
