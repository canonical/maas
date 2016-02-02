# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test DNS module."""

__all__ = []

import random
import time

from django.conf import settings
from django.core.management import call_command
from maasserver import locks
from maasserver.config import RegionConfiguration
from maasserver.dns import config as dns_config_module
from maasserver.dns.config import (
    consolidator,
    dns_add_domains,
    dns_add_subnets,
    dns_add_zones_now,
    dns_update_all_zones,
    dns_update_all_zones_now,
    dns_update_by_node,
    dns_update_domains,
    dns_update_subnets,
    dns_update_zones_now,
    get_trusted_networks,
    get_upstream_dns,
    is_dns_enabled,
    next_zone_serial,
    zone_serial,
)
from maasserver.enum import (
    IPADDRESS_TYPE,
    NODE_STATUS,
)
from maasserver.models import (
    Config,
    Domain,
)
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit_hooks
from maastesting.fakemethod import FakeMethod
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from mock import (
    ANY,
    sentinel,
)
from netaddr import (
    IPAddress,
    IPNetwork,
)
from provisioningserver.dns.config import (
    compose_config_path,
    DNSConfig,
)
from provisioningserver.dns.testing import (
    patch_dns_config_path,
    patch_dns_rndc_port,
)
from provisioningserver.dns.zoneconfig import DomainConfigBase
from provisioningserver.testing.bindfixture import (
    allocate_ports,
    BINDServer,
)
from provisioningserver.testing.tests.test_bindfixture import dig_call
from testtools.matchers import (
    Contains,
    FileContains,
    HasLength,
    Is,
    IsInstance,
    MatchesStructure,
    Not,
)
from twisted.internet.defer import Deferred


def get_expected_names(node, ip):
    expected_names = [
        "%s.%s." % (iface.name, node.fqdn)
        for iface in node.interface_set.filter(ip_addresses__id=ip.id)
    ]
    expected_names.append("%s." % node.fqdn)
    return expected_names


class TestDNSUtilities(MAASServerTestCase):

    def test_zone_serial_parameters(self):
        self.assertThat(
            zone_serial,
            MatchesStructure.byEquality(
                maxvalue=2 ** 32 - 1,
                minvalue=1,
                increment=1,
                )
            )

    def test_next_zone_serial_returns_sequence(self):
        zone_serial.create_if_not_exists()
        initial = int(next_zone_serial())
        self.assertSequenceEqual(
            ['%0.10d' % i for i in range(initial + 1, initial + 11)],
            [next_zone_serial() for _ in range(initial, initial + 10)])


class Thing:
    def __init__(self, id, authoritative):
        self.id = id
        self.authoritative = authoritative

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)


class TestDeferringChangesPostCommit(MAASServerTestCase):
    """
    Tests for several functions that, by default, defer work until after a
    successful commit.
    """

    scenarios = (
        ("dns_add_domains", {
            "now_function": dns_add_zones_now,
            "calling_function": dns_add_domains,
            "args": [[Thing(555, True)]],
            "now_args": [[Thing(555, True)], []],
            "kwargs": {},
        }),
        ("dns_add_subnets", {
            "now_function": dns_add_zones_now,
            "calling_function": dns_add_subnets,
            "args": [[Thing(555, True)]],
            "now_args": [[], [Thing(555, True)]],
            "kwargs": {},
        }),
        ("dns_update_domains", {
            "now_function": dns_update_zones_now,
            "calling_function": dns_update_domains,
            "args": [[Thing(555, True)]],
            "now_args": [[Thing(555, True)], []],
            "kwargs": {},
        }),
        ("dns_update_subnets", {
            "now_function": dns_update_zones_now,
            "calling_function": dns_update_subnets,
            "args": [[Thing(555, True)]],
            "now_args": [[], [Thing(555, True)]],
            "kwargs": {},
        }),
        ("dns_update_all_zones", {
            "now_function": dns_update_all_zones_now,
            "calling_function": dns_update_all_zones,
            "args": [],
            "now_args": [],
            "kwargs": {
                "reload_retry": factory.pick_bool(),
                "force": factory.pick_bool(),
            },
        }),
    )

    def patch_now_function(self):
        return self.patch(dns_config_module, self.now_function.__name__)

    def test__defers_by_default(self):
        self.patch(settings, "DNS_CONNECT", True)
        func = self.patch_now_function()
        result = self.calling_function(*self.args, **self.kwargs)
        self.assertThat(result, IsInstance(Deferred))
        self.assertThat(func, MockNotCalled())
        post_commit_hooks.fire()
        self.assertThat(
            func, MockCalledOnceWith(*self.now_args, **self.kwargs))

    def test__does_nothing_if_DNS_CONNECT_is_False(self):
        self.patch(settings, "DNS_CONNECT", False)
        func = self.patch_now_function()
        result = self.calling_function(*self.args, **self.kwargs)
        self.assertThat(result, Is(None))
        self.assertThat(func, MockNotCalled())
        post_commit_hooks.fire()
        self.assertThat(func, MockNotCalled())

    def test__calls_immediately_if_defer_is_False(self):
        self.patch(settings, "DNS_CONNECT", True)
        self.patch(dns_config_module, "DNS_DEFER_UPDATES", False)
        func = self.patch_now_function()
        func.return_value = sentinel.okay_now
        result = self.calling_function(*self.args, **self.kwargs)
        self.assertThat(result, Is(sentinel.okay_now))
        self.assertThat(
            func, MockCalledOnceWith(*self.now_args, **self.kwargs))
        self.assertThat(post_commit_hooks.hooks, HasLength(0))


class TestDeferringChangesPostCommit_by_node(MAASServerTestCase):
    """Tests for dns_update_by_node."""

    def test__defers_by_default(self):
        self.patch(settings, "DNS_CONNECT", True)
        dns_add_zones_now = self.patch_autospec(
            dns_config_module, "dns_add_zones_now")
        dns_update_zones_now = self.patch_autospec(
            dns_config_module, "dns_update_zones_now")
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, domain=Domain.objects.get_default_domain())
        node.save()
        node.hostname = factory.make_name('hostname')
        # The above will have created all sorts of things: confirm that
        # triggering causes dns_add_zones_now to be called.
        self.assertThat(dns_add_zones_now, MockNotCalled())
        post_commit_hooks.fire()
        self.assertEqual(1, dns_add_zones_now.call_count)

        # Now trigger an update by node, and confirm that we defer.
        dns_update_by_node(node)
        self.assertThat(dns_update_zones_now, MockNotCalled())
        post_commit_hooks.fire()
        self.assertThat(
            dns_update_zones_now, MockCalledOnceWith(
                [node.domain], [subnet]))

    def test__does_nothing_if_DNS_CONNECT_is_False(self):
        self.patch(settings, "DNS_CONNECT", False)
        dns_add_zones_now = self.patch_autospec(
            dns_config_module, "dns_add_zones_now")
        dns_update_zones_now = self.patch_autospec(
            dns_config_module, "dns_update_zones_now")
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, domain=Domain.objects.get_default_domain())
        node.save()
        node.hostname = factory.make_name('hostname')
        self.assertThat(dns_add_zones_now, MockNotCalled())
        post_commit_hooks.fire()
        self.assertEqual(0, dns_add_zones_now.call_count)

        # Now trigger an update by node, and confirm that we do nothing.
        dns_update_by_node(node)
        self.assertThat(dns_update_zones_now, MockNotCalled())
        post_commit_hooks.fire()
        self.assertThat(dns_update_zones_now, MockNotCalled())

    def test__calls_immediately_if_defer_is_False(self):
        self.patch(settings, "DNS_CONNECT", True)
        self.patch(dns_config_module, "DNS_DEFER_UPDATES", False)
        dns_add_zones_now = self.patch_autospec(
            dns_config_module, "dns_add_zones_now")
        dns_update_zones_now = self.patch_autospec(
            dns_config_module, "dns_update_zones_now")
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, domain=Domain.objects.get_default_domain())
        node.save()
        node.hostname = factory.make_name('hostname')
        # It turns out that all the above causes 2 calls to dns_add_zones_now.
        self.assertEqual(2, dns_add_zones_now.call_count)
        self.assertThat(post_commit_hooks.hooks, HasLength(0))
        # Now make sure that dns_update_zones_now gets called once and only
        # once.
        self.assertThat(dns_update_zones_now, MockNotCalled())
        dns_update_by_node(node)
        self.assertEqual(1, dns_update_zones_now.call_count)
        self.assertThat(post_commit_hooks.hooks, HasLength(0))


class TestConsolidatingChanges(MAASServerTestCase):
    """Tests for `Changes` and `ChangeConsolidator`."""

    def setUp(self):
        super(TestConsolidatingChanges, self).setUp()
        self.useFixture(RegionConfigurationFixture())

    def test__zone_changes_applied_while_holding_dns_lock(self):

        def check_dns_is_locked(reload_retry, force):
            self.assertTrue(locks.dns.is_locked(), "locks.dns isn't locked")
            return False  # Prevent dns_update_zones_now from continuing.

        dns_update_all_zones_now = self.patch_autospec(
            dns_config_module, "dns_update_all_zones_now")
        dns_update_all_zones_now.side_effect = check_dns_is_locked

        consolidator.update_all_zones()
        post_commit_hooks.fire()
        self.assertThat(
            dns_update_all_zones_now, MockCalledOnceWith(
                reload_retry=ANY, force=ANY))

    def test__added_zones_applied_post_commit(self):
        dns_add_zones_now = self.patch_autospec(
            dns_config_module, "dns_add_zones_now")
        domain1 = factory.make_Domain()
        consolidator.add_domains(domain1)
        domain2 = factory.make_Domain()
        consolidator.add_domains(domain2)
        self.assertThat(dns_add_zones_now, MockNotCalled())
        post_commit_hooks.fire()
        self.assertThat(dns_add_zones_now, MockCalledOnceWith(ANY, ANY))
        # There's no guaranteed ordering, so we must extract and compare.
        domains = dns_add_zones_now.call_args[0]
        self.assertItemsEqual([domain1, domain2], domains[0])
        self.assertItemsEqual([], domains[1])

    def test__added_domains_are_consolidated(self):
        dns_add_zones_now = self.patch_autospec(
            dns_config_module, "dns_add_zones_now")
        domain = factory.make_Domain()
        consolidator.add_domains(domain)
        consolidator.add_domains(domain)
        consolidator.add_domains([domain, domain])
        post_commit_hooks.fire()
        self.assertThat(dns_add_zones_now, MockCalledOnceWith([domain], []))

    def test__updated_zones_applied_post_commit(self):
        dns_update_zones_now = self.patch_autospec(
            dns_config_module, "dns_update_zones_now")
        domain1 = factory.make_Domain()
        consolidator.update_domains(domain1)
        domain2 = factory.make_Domain()
        consolidator.update_domains(domain2)
        self.assertThat(dns_update_zones_now, MockNotCalled())
        post_commit_hooks.fire()
        self.assertThat(dns_update_zones_now, MockCalledOnceWith(ANY, ANY))
        # There's no guaranteed ordering, so we must extract and compare.
        domains = dns_update_zones_now.call_args[0]
        self.assertItemsEqual([domain1, domain2], domains[0])
        self.assertItemsEqual([], domains[1])

    def test__updated_zones_are_consolidated(self):
        dns_update_zones_now = self.patch_autospec(
            dns_config_module, "dns_update_zones_now")
        domain = factory.make_Domain()
        consolidator.update_domains(domain)
        consolidator.update_domains(domain)
        consolidator.update_domains([domain, domain])
        post_commit_hooks.fire()
        self.assertThat(dns_update_zones_now, MockCalledOnceWith([domain], []))

    def test__added_zones_supersede_updated_zones(self):
        dns_add_zones_now = self.patch_autospec(
            dns_config_module, "dns_add_zones_now")
        dns_update_zones_now = self.patch_autospec(
            dns_config_module, "dns_update_zones_now")
        domain = factory.make_Domain()
        consolidator.add_domains(domain)
        consolidator.update_domains(domain)
        post_commit_hooks.fire()
        self.assertThat(dns_add_zones_now, MockCalledOnceWith([domain], []))
        self.assertThat(dns_update_zones_now, MockNotCalled())

    def test__update_all_zones_does_just_that(self):
        dns_update_all_zones_now = self.patch_autospec(
            dns_config_module, "dns_update_all_zones_now")
        consolidator.update_all_zones()
        self.assertThat(dns_update_all_zones_now, MockNotCalled())
        post_commit_hooks.fire()
        self.assertThat(
            dns_update_all_zones_now, MockCalledOnceWith(
                reload_retry=False, force=False))

    def test__update_all_zones_combines_flags_with_or(self):
        dns_update_all_zones_now = self.patch_autospec(
            dns_config_module, "dns_update_all_zones_now")
        consolidator.update_all_zones(False, True)
        consolidator.update_all_zones(True, False)
        post_commit_hooks.fire()
        self.assertThat(
            dns_update_all_zones_now, MockCalledOnceWith(
                reload_retry=True, force=True))

    def test__update_all_zones_supersedes_individual_add_and_update(self):
        dns_add_zones_now = self.patch_autospec(
            dns_config_module, "dns_add_zones_now")
        dns_update_zones_now = self.patch_autospec(
            dns_config_module, "dns_update_zones_now")
        dns_update_all_zones_now = self.patch_autospec(
            dns_config_module, "dns_update_all_zones_now")
        domain = factory.make_Domain()
        consolidator.add_domains(domain)
        consolidator.update_domains(domain)
        consolidator.update_all_zones()
        post_commit_hooks.fire()
        self.assertThat(dns_add_zones_now, MockNotCalled())
        self.assertThat(dns_update_zones_now, MockNotCalled())
        self.assertThat(
            dns_update_all_zones_now, MockCalledOnceWith(
                reload_retry=False, force=False))

    # A pair of matchers to check that a `Changes` object is empty, or not.
    changes_are_empty = MatchesStructure.byEquality(
        hook=None, domains_to_add=[], domains_to_update=[],
        subnets_to_add=[], subnets_to_update=[],
        update_all_zones=False, update_all_zones_reload_retry=False,
        update_all_zones_force=False)
    changes_are_not_empty = Not(changes_are_empty)

    def test__changes_are_reset_post_commit(self):
        self.patch_autospec(dns_config_module, "dns_update_all_zones_now")

        # The changes start empty.
        self.assertThat(consolidator.changes, self.changes_are_empty)

        domain = factory.make_Domain()
        subnet = factory.make_Subnet()
        consolidator.add_domains(domain)
        consolidator.update_domains(domain)
        consolidator.add_subnets(subnet)
        consolidator.update_subnets(subnet)
        consolidator.update_all_zones()

        # The changes are not empty now.
        self.assertThat(consolidator.changes, self.changes_are_not_empty)

        # They are once again empty after the post-commit hook fires.
        post_commit_hooks.fire()
        self.assertThat(consolidator.changes, self.changes_are_empty)

    def test__changes_are_reset_post_commit_on_failure(self):
        exception_type = factory.make_exception_type()

        dns_update_all_zones_now = self.patch_autospec(
            dns_config_module, "dns_update_all_zones_now")
        dns_update_all_zones_now.side_effect = exception_type

        domain = factory.make_Domain()
        subnet = factory.make_Subnet()
        consolidator.add_domains(domain)
        consolidator.update_domains(domain)
        consolidator.add_subnets(subnet)
        consolidator.update_subnets(subnet)
        # This is going to crash.
        consolidator.update_all_zones()

        # The changes are empty after the post-commit hook fires.
        self.assertRaises(exception_type, post_commit_hooks.fire)
        self.assertThat(consolidator.changes, self.changes_are_empty)


class TestDNSServer(MAASServerTestCase):
    """A base class to perform real-world DNS-related tests.

    The class starts a BINDServer for every test and provides a set of
    helper methods to perform DNS queries.

    Because of the overhead added by starting and stopping the DNS
    server, new tests in this class and its descendants are expensive.
    """

    def setUp(self):
        super(TestDNSServer, self).setUp()
        # Make sure the zone_serial is created.
        zone_serial.create_if_not_exists()
        # Allow test-local changes to configuration.
        self.useFixture(RegionConfigurationFixture())
        # Immediately make DNS changes as they're needed.
        self.patch(dns_config_module, "DNS_DEFER_UPDATES", False)
        # Create a DNS server.
        self.bind = self.useFixture(BINDServer())
        patch_dns_config_path(self, self.bind.config.homedir)
        # Use a random port for rndc.
        patch_dns_rndc_port(self, allocate_ports("localhost")[0])
        # This simulates what should happen when the package is
        # installed:
        # Create MAAS-specific DNS configuration files.
        call_command('set_up_dns')
        # Register MAAS-specific DNS configuration files with the
        # system's BIND instance.
        call_command(
            'get_named_conf', edit=True,
            config_path=self.bind.config.conf_file)
        # Reload BIND.
        self.bind.runner.rndc('reload')

    def create_node_with_static_ip(
            self, domain=None, subnet=None):
        if domain is None:
            domain = Domain.objects.get_default_domain()
        if subnet is None:
            network = factory.make_ipv4_network()
            subnet = factory.make_Subnet(cidr=str(network.cidr))
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.READY, domain=domain,
            disable_ipv4=False)
        nic = node.get_boot_interface()
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet, interface=nic)
        dns_update_zones_now([domain], [subnet])
        return node, static_ip

    def dig_resolve(self, fqdn, version=4):
        """Resolve `fqdn` using dig.  Returns a list of results."""
        # Using version=6 has two effects:
        # - it changes the type of query from 'A' to 'AAAA';
        # - it forces dig to only use IPv6 query transport.
        record_type = 'AAAA' if version == 6 else 'A'
        commands = [fqdn, '+short', '-%i' % version, record_type]
        output = dig_call(
            port=self.bind.config.port,
            commands=commands)
        return output.split('\n')

    def dig_reverse_resolve(self, ip, version=4):
        """Reverse resolve `ip` using dig.  Returns a list of results."""
        output = dig_call(
            port=self.bind.config.port,
            commands=['-x', ip, '+short', '-%i' % version])
        return output.split('\n')

    def assertDNSMatches(self, hostname, domain, ip, version=-1):
        # A forward lookup on the hostname returns the IP address.
        if version == -1:
            version = IPAddress(ip).version
        fqdn = "%s.%s" % (hostname, domain)
        forward_lookup_result = self.dig_resolve(fqdn, version=version)
        self.assertThat(
            forward_lookup_result, Contains(ip),
            "Failed to resolve '%s' (results: '%s')." % (
                fqdn, ','.join(forward_lookup_result)))
        # A reverse lookup on the IP address returns the hostname.
        reverse_lookup_result = self.dig_reverse_resolve(
            ip, version=version)
        self.assertThat(
            reverse_lookup_result, Contains("%s." % fqdn),
            "Failed to reverse resolve '%s' missing '%s' (results: '%s')." % (
                ip, "%s." % fqdn, ','.join(reverse_lookup_result)))


class TestDNSConfigModifications(TestDNSServer):

    def test_dns_add_zones_now_loads_dns_zone(self):
        node, static = self.create_node_with_static_ip()
        self.patch(settings, 'DNS_CONNECT', True)
        dns_add_zones_now([node.domain], [static.subnet])
        self.assertDNSMatches(node.hostname, node.domain.name, static.ip)

    def test_dns_add_zones_now_preserves_trusted_networks(self):
        node, static = self.create_node_with_static_ip()
        trusted_network = factory.make_ipv4_address()
        get_trusted_networks_patch = self.patch(
            dns_config_module, 'get_trusted_networks')
        get_trusted_networks_patch.return_value = [trusted_network]
        self.patch(settings, 'DNS_CONNECT', True)
        dns_add_zones_now([node.domain], [static.subnet])
        self.assertThat(
            compose_config_path(DNSConfig.target_file_name),
            FileContains(matcher=Contains(trusted_network)))

    def test_dns_update_zones_now_changes_dns_zone(self):
        node, static = self.create_node_with_static_ip()
        self.patch(settings, 'DNS_CONNECT', True)
        dns_update_all_zones_now()
        new_node, new_static = (
            self.create_node_with_static_ip(
                domain=node.domain, subnet=static.subnet))
        dns_update_zones_now(
            [node.domain],
            [static.subnet])
        self.assertDNSMatches(
            new_node.hostname, new_node.domain.name, new_static.ip)

    def test_is_dns_enabled_return_false_if_DNS_CONNECT_False(self):
        self.patch(settings, 'DNS_CONNECT', False)
        self.assertFalse(is_dns_enabled())

    def test_is_dns_enabled_return_True_if_DNS_CONNECT_True(self):
        self.patch(settings, 'DNS_CONNECT', True)
        self.assertTrue(is_dns_enabled())

    def test_dns_update_all_zones_now_loads_full_dns_config(self):
        node, static = self.create_node_with_static_ip()
        self.patch(settings, 'DNS_CONNECT', True)
        dns_update_all_zones_now()
        self.assertDNSMatches(node.hostname, node.domain.name, static.ip)

    def test_dns_update_all_zones_now_passes_reload_retry_parameter(self):
        self.patch(settings, 'DNS_CONNECT', True)
        bind_reload_with_retries = self.patch_autospec(
            dns_config_module, "bind_reload_with_retries")
        dns_update_all_zones_now(reload_retry=True)
        self.assertThat(bind_reload_with_retries, MockCalledOnceWith())

    def test_dns_update_all_zones_now_passes_upstream_dns_parameter(self):
        self.patch(settings, 'DNS_CONNECT', True)
        random_ip = factory.make_ipv4_address()
        Config.objects.set_config("upstream_dns", random_ip)
        bind_write_options = self.patch_autospec(
            dns_config_module, "bind_write_options")
        dns_update_all_zones_now()
        self.assertThat(
            bind_write_options,
            MockCalledOnceWith(
                dnssec_validation='auto', upstream_dns=[random_ip]))

    def test_dns_update_all_zones_now_writes_trusted_networks_parameter(self):
        self.patch(settings, 'DNS_CONNECT', True)
        trusted_network = factory.make_ipv4_address()
        get_trusted_networks_patch = self.patch(
            dns_config_module, 'get_trusted_networks')
        get_trusted_networks_patch.return_value = [trusted_network]
        dns_update_all_zones_now()
        self.assertThat(
            compose_config_path(DNSConfig.target_file_name),
            FileContains(matcher=Contains(trusted_network)))

    def test_dns_config_has_NS_record(self):
        ip = factory.make_ipv4_address()
        with RegionConfiguration.open_for_update() as config:
            config.maas_url = 'http://%s/' % ip
        domain = factory.make_Domain()
        node, static = self.create_node_with_static_ip(domain=domain)
        self.patch(settings, 'DNS_CONNECT', True)
        dns_update_all_zones_now()
        # Sleep half a second to make sure bind is fully-ready. This is not the
        # best, but it does prevent this tests from failing randomly.
        time.sleep(0.5)
        # Get the NS record for the zone 'domain.name'.
        ns_record = dig_call(
            port=self.bind.config.port,
            commands=[domain.name, 'NS', '+short'])
        self.assertGreater(
            len(ns_record), 0, "No NS record for domain.name.")
        # Resolve that hostname.
        ip_of_ns_record = dig_call(
            port=self.bind.config.port, commands=[ns_record, '+short'])
        self.assertEqual(ip, ip_of_ns_record)

    def test_edit_subnet_updates_DNS_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        old_network = IPNetwork('192.168.7.1/24')
        subnet = factory.make_Subnet(cidr=str(old_network.cidr))
        node, lease = self.create_node_with_static_ip(subnet=subnet)
        self.assertItemsEqual(
            get_expected_names(node, lease),
            self.dig_reverse_resolve(lease.ip))
        # Edit subnet's network information to '192.168.44.1/24'
        subnet.cidr = '192.168.44.1/24'
        subnet.gateway_ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        subnet.dns_servers = []
        subnet.save()
        # The IP from the old network does not resolve anymore.
        self.assertEqual([''], self.dig_reverse_resolve(lease.ip))
        # A lease in the new network resolves.
        node, lease = self.create_node_with_static_ip(subnet=subnet)
        self.assertTrue(
            IPAddress(lease.ip) in subnet.get_ipnetwork(),
            "The lease IP Address is not in the new network")
        self.assertItemsEqual(
            get_expected_names(node, lease),
            self.dig_reverse_resolve(lease.ip))

    def test_delete_domain_disables_DNS_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        network = IPNetwork('192.168.7.1/24')
        ip = factory.pick_ip_in_network(network)
        domain = factory.make_Domain()
        domain.delete()
        self.assertEqual([''], self.dig_reverse_resolve(ip))

    def test_add_node_updates_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        node, static = self.create_node_with_static_ip()
        self.assertDNSMatches(node.hostname, node.domain.name, static.ip)

    def test_delete_node_updates_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        node, static = self.create_node_with_static_ip()
        node.delete()
        fqdn = "%s.%s" % (node.hostname, node.domain.name)
        self.assertEqual([''], self.dig_resolve(fqdn))

    def test_change_node_hostname_updates_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        node, static = self.create_node_with_static_ip()
        node.hostname = factory.make_name('hostname')
        node.save()
        self.assertDNSMatches(node.hostname, node.domain.name, static.ip)

    def test_change_node_other_field_does_not_update_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        node, static = self.create_node_with_static_ip()
        recorder = FakeMethod()
        self.patch(DomainConfigBase, 'write_config', recorder)
        node.error = factory.make_string()
        node.save()
        self.assertEqual(0, recorder.call_count)


class TestDNSDynamicIPAddresses(TestDNSServer):
    """Allocated nodes with IP addresses in the dynamic range get a DNS
    record.
    """

    def test_bind_configuration_includes_dynamic_ips_of_deployed_nodes(self):
        self.patch(settings, "DNS_CONNECT", True)
        subnet = factory.make_ipv4_Subnet_with_IPRanges()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.DEPLOYED, disable_ipv4=False)
        nic = node.get_boot_interface()
        # Get an IP in the dynamic range.
        dynamic_range = subnet.get_dynamic_ranges()[0]
        ip = factory.pick_ip_in_IPRange(dynamic_range)
        ip_obj = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=ip,
            subnet=subnet, interface=nic)
        dns_update_zones_now([node.domain], [subnet])
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
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, ip=ip,
            subnet=subnet)
        rrname = factory.make_name('label')
        dnsrr = factory.make_DNSResource(
            name=rrname, domain=domain,
            ip_addresses=[ip_obj])
        self.assertDNSMatches(dnsrr.name, domain.name, ip_obj.ip)


class TestIPv6DNS(TestDNSServer):

    def test_bind_configuration_includes_ipv6_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        network = factory.make_ipv6_network(slash=random.randint(118, 125))
        subnet = factory.make_Subnet(cidr=str(network.cidr))
        node, static = self.create_node_with_static_ip(subnet=subnet)
        self.assertDNSMatches(
            node.hostname, node.domain.name, static.ip, version=6)


class TestGetUpstreamDNS(MAASServerTestCase):
    """Test for maasserver/dns/config.py:get_upstream_dns()"""

    def test__returns_empty_list_if_not_set(self):
        self.assertEqual([], get_upstream_dns())

    def test__returns_list_of_one_address_if_set(self):
        address = factory.make_ip_address()
        Config.objects.set_config("upstream_dns", address)
        self.assertEqual([address], get_upstream_dns())

    def test__returns_list_if_space_separated_ips(self):
        addresses = [
            factory.make_ip_address() for _ in range(3)]
        Config.objects.set_config("upstream_dns", " ".join(addresses))
        self.assertEqual(addresses, get_upstream_dns())


class TestGetTrustedNetworks(MAASServerTestCase):
    """Test for maasserver/dns/config.py:get_trusted_networks()"""

    def setUp(self):
        super(TestGetTrustedNetworks, self).setUp()
        self.useFixture(RegionConfigurationFixture())

    def test__returns_empty_string_if_no_networks(self):
        self.assertEqual([], get_trusted_networks())

    def test__returns_single_network(self):
        subnet = factory.make_Subnet()
        expected = [str(subnet.cidr)]
        self.assertEqual(expected, get_trusted_networks())

    def test__returns_many_networks(self):
        subnets = [factory.make_Subnet() for _ in range(random.randint(1, 5))]
        expected = [str(subnet.cidr) for subnet in subnets]
        # Note: This test was seen randomly failing because the networks were
        # in an unexpected order...
        self.assertItemsEqual(expected, get_trusted_networks())
