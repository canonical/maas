# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test DNS module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from itertools import islice
import random

from django.conf import settings
from django.core.management import call_command
from maasserver import locks
from maasserver.config import RegionConfiguration
from maasserver.dns import config as dns_config_module
from maasserver.dns.config import (
    consolidator,
    dns_add_zones,
    dns_add_zones_now,
    dns_update_all_zones,
    dns_update_all_zones_now,
    dns_update_zones,
    dns_update_zones_now,
    get_trusted_networks,
    get_upstream_dns,
    is_dns_enabled,
    is_dns_in_use,
    next_zone_serial,
    zone_serial,
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
    interface as interface_module,
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
    Mock,
    sentinel,
)
from netaddr import (
    IPAddress,
    IPNetwork,
    IPRange,
)
from provisioningserver.dns.config import (
    compose_config_path,
    DNSConfig,
)
from provisioningserver.dns.testing import (
    patch_dns_config_path,
    patch_dns_rndc_port,
)
from provisioningserver.dns.zoneconfig import DNSZoneConfigBase
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


class TestDNSUtilities(MAASServerTestCase):

    def test_zone_serial_parameters(self):
        self.assertThat(
            zone_serial,
            MatchesStructure.byEquality(
                maxvalue=2 ** 32 - 1,
                minvalue=1,
                incr=1,
                )
            )

    def test_next_zone_serial_returns_sequence(self):
        initial = int(next_zone_serial())
        self.assertSequenceEqual(
            ['%0.10d' % i for i in range(initial + 1, initial + 11)],
            [next_zone_serial() for _ in range(initial, initial + 10)])


class TestDeferringChangesPostCommit(MAASServerTestCase):
    """
    Tests for several functions that, by default, defer work until after a
    successful commit.
    """

    scenarios = (
        ("dns_add_zones", {
            "now_function": dns_add_zones_now,
            "calling_function": dns_add_zones,
            "args": [[Mock(id=random.randint(1, 1000))]],
            "kwargs": {},
        }),
        ("dns_update_zones", {
            "now_function": dns_update_zones_now,
            "calling_function": dns_update_zones,
            "args": [[Mock(id=random.randint(1, 1000))]],
            "kwargs": {},
        }),
        ("dns_update_all_zones", {
            "now_function": dns_update_all_zones_now,
            "calling_function": dns_update_all_zones,
            "args": [],
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
        self.assertThat(func, MockCalledOnceWith(*self.args, **self.kwargs))

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
        self.assertThat(func, MockCalledOnceWith(*self.args, **self.kwargs))
        self.assertThat(post_commit_hooks.hooks, HasLength(0))


class TestConsolidatingChanges(MAASServerTestCase):
    """Tests for `Changes` and `ChangeConsolidator`."""

    def setUp(self):
        super(TestConsolidatingChanges, self).setUp()
        self.useFixture(RegionConfigurationFixture())

    def make_managed_nodegroup(self):
        return factory.make_NodeGroup(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            status=NODEGROUP_STATUS.ENABLED)

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
        cluster1 = self.make_managed_nodegroup()
        consolidator.add_zones(cluster1)
        cluster2 = self.make_managed_nodegroup()
        consolidator.add_zones(cluster2)
        self.assertThat(dns_add_zones_now, MockNotCalled())
        post_commit_hooks.fire()
        self.assertThat(dns_add_zones_now, MockCalledOnceWith(ANY))
        # There's no guaranteed ordering, so we must extract and compare.
        [clusters], _ = dns_add_zones_now.call_args
        self.assertItemsEqual([cluster1, cluster2], clusters)

    def test__added_zones_are_consolidated(self):
        dns_add_zones_now = self.patch_autospec(
            dns_config_module, "dns_add_zones_now")
        cluster = self.make_managed_nodegroup()
        consolidator.add_zones(cluster)
        consolidator.add_zones(cluster)
        consolidator.add_zones([cluster, cluster])
        post_commit_hooks.fire()
        self.assertThat(dns_add_zones_now, MockCalledOnceWith([cluster]))

    def test__updated_zones_applied_post_commit(self):
        dns_update_zones_now = self.patch_autospec(
            dns_config_module, "dns_update_zones_now")
        cluster1 = self.make_managed_nodegroup()
        consolidator.update_zones(cluster1)
        cluster2 = self.make_managed_nodegroup()
        consolidator.update_zones(cluster2)
        self.assertThat(dns_update_zones_now, MockNotCalled())
        post_commit_hooks.fire()
        self.assertThat(dns_update_zones_now, MockCalledOnceWith(ANY))
        # There's no guaranteed ordering, so we must extract and compare.
        [clusters], _ = dns_update_zones_now.call_args
        self.assertItemsEqual([cluster1, cluster2], clusters)

    def test__updated_zones_are_consolidated(self):
        dns_update_zones_now = self.patch_autospec(
            dns_config_module, "dns_update_zones_now")
        cluster = self.make_managed_nodegroup()
        consolidator.update_zones(cluster)
        consolidator.update_zones(cluster)
        consolidator.update_zones([cluster, cluster])
        post_commit_hooks.fire()
        self.assertThat(dns_update_zones_now, MockCalledOnceWith([cluster]))

    def test__added_zones_supersede_updated_zones(self):
        dns_add_zones_now = self.patch_autospec(
            dns_config_module, "dns_add_zones_now")
        dns_update_zones_now = self.patch_autospec(
            dns_config_module, "dns_update_zones_now")
        cluster = self.make_managed_nodegroup()
        consolidator.add_zones(cluster)
        consolidator.update_zones(cluster)
        post_commit_hooks.fire()
        self.assertThat(dns_add_zones_now, MockCalledOnceWith([cluster]))
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
        cluster = self.make_managed_nodegroup()
        consolidator.add_zones(cluster)
        consolidator.update_zones(cluster)
        consolidator.update_all_zones()
        post_commit_hooks.fire()
        self.assertThat(dns_add_zones_now, MockNotCalled())
        self.assertThat(dns_update_zones_now, MockNotCalled())
        self.assertThat(
            dns_update_all_zones_now, MockCalledOnceWith(
                reload_retry=False, force=False))

    # A pair of matchers to check that a `Changes` object is empty, or not.
    changes_are_empty = MatchesStructure.byEquality(
        hook=None, zones_to_add=[], zones_to_update=[],
        update_all_zones=False, update_all_zones_reload_retry=False,
        update_all_zones_force=False)
    changes_are_not_empty = Not(changes_are_empty)

    def test__changes_are_reset_post_commit(self):
        self.patch_autospec(dns_config_module, "dns_update_all_zones_now")

        # The changes start empty.
        self.assertThat(consolidator.changes, self.changes_are_empty)

        cluster = self.make_managed_nodegroup()
        consolidator.add_zones(cluster)
        consolidator.update_zones(cluster)
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

    def create_managed_nodegroup(self, network=None):
        if network is None:
            network = IPNetwork('192.168.0.1/24')
        return factory.make_NodeGroup(
            network=network,
            status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)

    def create_nodegroup_with_static_ip(self, lease_number=1, nodegroup=None):
        if nodegroup is None:
            nodegroup = self.create_managed_nodegroup()
        [interface] = nodegroup.get_managed_interfaces()
        node = factory.make_Node(nodegroup=nodegroup, disable_ipv4=False)
        nic = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        ips = IPRange(
            interface.static_ip_range_low, interface.static_ip_range_high)
        static_ip = unicode(islice(ips, lease_number, lease_number + 1).next())
        staticaddress = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip=static_ip,
            subnet=interface.subnet, interface=nic)
        dns_update_zones_now(nodegroup)
        return nodegroup, node, staticaddress

    def dig_resolve(self, fqdn, version=4):
        """Resolve `fqdn` using dig.  Returns a list of results."""
        # Using version=6 has two effects:
        # - it changes the type of query from 'A' to 'AAAA';
        # - it forces dig to only use IPv6 query transport.
        record_type = 'AAAA' if version == 6 else 'A'
        commands = [fqdn, '+short', '-%i' % version, record_type]
        return dig_call(
            port=self.bind.config.port,
            commands=commands).split('\n')

    def dig_reverse_resolve(self, ip, version=4):
        """Reverse resolve `ip` using dig.  Returns a list of results."""
        return dig_call(
            port=self.bind.config.port,
            commands=['-x', ip, '+short', '-%i' % version]).split('\n')

    def assertDNSMatches(self, hostname, domain, ip, version=4):
        # A forward lookup on the hostname returns the IP address.
        fqdn = "%s.%s" % (hostname, domain)
        forward_lookup_result = self.dig_resolve(fqdn, version=version)
        self.expectThat(
            forward_lookup_result, Contains(ip),
            "Failed to resolve '%s' (results: '%s')." % (
                fqdn, ','.join(forward_lookup_result)))
        # A reverse lookup on the IP address returns the hostname.
        reverse_lookup_result = self.dig_reverse_resolve(
            ip, version=version)
        self.expectThat(
            reverse_lookup_result, Contains("%s." % fqdn),
            "Failed to reverse resolve '%s' (results: '%s')." % (
                fqdn, ','.join(reverse_lookup_result)))


class TestDNSConfigModifications(TestDNSServer):

    def test_dns_add_zones_now_loads_dns_zone(self):
        nodegroup, node, static = self.create_nodegroup_with_static_ip()
        self.patch(settings, 'DNS_CONNECT', True)
        dns_add_zones_now(nodegroup)
        self.assertDNSMatches(node.hostname, nodegroup.name, static.ip)

    def test_dns_add_zones_now_preserves_trusted_networks(self):
        nodegroup, node, static = self.create_nodegroup_with_static_ip()
        trusted_network = factory.make_ipv4_address()
        get_trusted_networks_patch = self.patch(
            dns_config_module, 'get_trusted_networks')
        get_trusted_networks_patch.return_value = [trusted_network]
        self.patch(settings, 'DNS_CONNECT', True)
        dns_add_zones_now(nodegroup)
        self.assertThat(
            compose_config_path(DNSConfig.target_file_name),
            FileContains(matcher=Contains(trusted_network)))

    def test_dns_update_zones_now_changes_dns_zone(self):
        nodegroup, _, _ = self.create_nodegroup_with_static_ip()
        self.patch(settings, 'DNS_CONNECT', True)
        dns_update_all_zones_now()
        nodegroup, new_node, new_static = (
            self.create_nodegroup_with_static_ip(
                nodegroup=nodegroup, lease_number=2))
        dns_update_zones_now(nodegroup)
        self.assertDNSMatches(new_node.hostname, nodegroup.name, new_static.ip)

    def test_is_dns_enabled_return_false_if_DNS_CONNECT_False(self):
        self.patch(settings, 'DNS_CONNECT', False)
        self.assertFalse(is_dns_enabled())

    def test_is_dns_enabled_return_True_if_DNS_CONNECT_True(self):
        self.patch(settings, 'DNS_CONNECT', True)
        self.assertTrue(is_dns_enabled())

    def test_is_dns_in_use_return_False_no_configured_interface(self):
        self.assertFalse(is_dns_in_use())

    def test_is_dns_in_use_return_True_if_configured_interface(self):
        self.create_managed_nodegroup()
        self.assertTrue(is_dns_in_use())

    def test_dns_update_all_zones_now_loads_full_dns_config(self):
        nodegroup, node, static = self.create_nodegroup_with_static_ip()
        self.patch(settings, 'DNS_CONNECT', True)
        dns_update_all_zones_now()
        self.assertDNSMatches(node.hostname, nodegroup.name, static.ip)

    def test_dns_update_all_zones_now_passes_reload_retry_parameter(self):
        self.patch(settings, 'DNS_CONNECT', True)
        self.create_managed_nodegroup()
        bind_reload_with_retries = self.patch_autospec(
            dns_config_module, "bind_reload_with_retries")
        dns_update_all_zones_now(reload_retry=True)
        self.assertThat(bind_reload_with_retries, MockCalledOnceWith())

    def test_dns_update_all_zones_now_passes_upstream_dns_parameter(self):
        self.patch(settings, 'DNS_CONNECT', True)
        self.create_managed_nodegroup()
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
        self.create_managed_nodegroup()
        trusted_network = factory.make_ipv4_address()
        get_trusted_networks_patch = self.patch(
            dns_config_module, 'get_trusted_networks')
        get_trusted_networks_patch.return_value = [trusted_network]
        dns_update_all_zones_now()
        self.assertThat(
            compose_config_path(DNSConfig.target_file_name),
            FileContains(matcher=Contains(trusted_network)))

    def test_dns_update_all_zones_now_does_nada_if_no_iface_configured(self):
        self.patch(settings, 'DNS_CONNECT', True)
        bind_write_configuration = self.patch_autospec(
            dns_config_module, "bind_write_configuration")
        dns_update_all_zones_now()
        self.assertThat(bind_write_configuration, MockNotCalled())

    def test_dns_config_has_NS_record(self):
        ip = factory.make_ipv4_address()
        with RegionConfiguration.open() as config:
            config.maas_url = 'http://%s/' % ip
        nodegroup, node, static = self.create_nodegroup_with_static_ip()
        self.patch(settings, 'DNS_CONNECT', True)
        dns_update_all_zones_now()
        # Get the NS record for the zone 'nodegroup.name'.
        ns_record = dig_call(
            port=self.bind.config.port,
            commands=[nodegroup.name, 'NS', '+short'])
        # Resolve that hostname.
        ip_of_ns_record = dig_call(
            port=self.bind.config.port, commands=[ns_record, '+short'])
        self.assertEqual(ip, ip_of_ns_record)

    def test_edit_nodegroupinterface_updates_DNS_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        old_network = IPNetwork('192.168.7.1/24')
        nodegroup = factory.make_NodeGroup(
            network=old_network, status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        [interface] = nodegroup.get_managed_interfaces()
        _, node, lease = self.create_nodegroup_with_static_ip(
            nodegroup=nodegroup)
        self.assertEqual(
            ["%s." % node.fqdn], self.dig_reverse_resolve(lease.ip))
        # Edit nodegroup's network information to '192.168.44.1/24'
        interface.ip = '192.168.44.7'
        interface.subnet_mask = '255.255.255.0'
        interface.subnet.gateway_ip = '192.168.44.14'
        interface.ip_range_low = '192.168.44.0'
        interface.ip_range_high = '192.168.44.128'
        interface.static_ip_range_low = '192.168.44.129'
        interface.static_ip_range_high = '192.168.44.255'
        interface.save()
        # The IP from the old network does not resolve anymore.
        self.assertEqual([''], self.dig_reverse_resolve(lease.ip))
        # A lease in the new network resolves.
        _, node, lease = self.create_nodegroup_with_static_ip(
            nodegroup=nodegroup)
        self.assertTrue(
            IPAddress(lease.ip) in interface.network,
            "The lease IP Address is not in the new network")
        self.assertEqual(
            ["%s." % node.fqdn], self.dig_reverse_resolve(lease.ip))

    def test_changing_interface_management_updates_DNS_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        network = IPNetwork('192.168.7.1/24')
        ip = factory.pick_ip_in_network(network)
        nodegroup = factory.make_NodeGroup(
            network=network, status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        [interface] = nodegroup.get_managed_interfaces()
        interface.management = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
        interface.save()
        self.assertEqual([''], self.dig_reverse_resolve(ip))

    def test_delete_nodegroup_disables_DNS_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        network = IPNetwork('192.168.7.1/24')
        ip = factory.pick_ip_in_network(network)
        nodegroup = factory.make_NodeGroup(
            network=network, status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        nodegroup.delete()
        self.assertEqual([''], self.dig_reverse_resolve(ip))

    def test_add_node_updates_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        nodegroup, node, static = self.create_nodegroup_with_static_ip()
        self.assertDNSMatches(node.hostname, nodegroup.name, static.ip)

    def test_delete_node_updates_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        self.patch_autospec(interface_module, "remove_host_maps")
        nodegroup, node, static = self.create_nodegroup_with_static_ip()
        node.delete()
        fqdn = "%s.%s" % (node.hostname, nodegroup.name)
        self.assertEqual([''], self.dig_resolve(fqdn))

    def test_change_node_hostname_updates_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        nodegroup, node, static = self.create_nodegroup_with_static_ip()
        node.hostname = factory.make_name('hostname')
        node.save()
        self.assertDNSMatches(node.hostname, nodegroup.name, static.ip)

    def test_change_node_other_field_does_not_update_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        nodegroup, node, static = self.create_nodegroup_with_static_ip()
        recorder = FakeMethod()
        self.patch(DNSZoneConfigBase, 'write_config', recorder)
        node.error = factory.make_string()
        node.save()
        self.assertEqual(0, recorder.call_count)


class TestDNSDynamicIPAddresses(TestDNSServer):
    """Allocated nodes with IP addresses in the dynamic range get a DNS
    record.
    """

    def test_bind_configuration_includes_dynamic_ips_of_deployed_nodes(self):
        self.patch(settings, "DNS_CONNECT", True)
        network = IPNetwork('192.168.7.1/24')
        nodegroup = self.create_managed_nodegroup(network=network)
        [interface] = nodegroup.get_managed_interfaces()
        node = factory.make_Node(
            nodegroup=nodegroup, status=NODE_STATUS.DEPLOYED,
            disable_ipv4=False)
        nic = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        # Get an IP in the dynamic range.
        ip_range = IPRange(
            interface.ip_range_low, interface.ip_range_high)
        ip = "%s" % random.choice(ip_range)
        ip_obj = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=ip,
            subnet=interface.subnet, interface=nic)
        dns_update_zones_now(nodegroup)
        self.assertDNSMatches(node.hostname, nodegroup.name, ip_obj.ip)


class TestIPv6DNS(TestDNSServer):

    def test_bind_configuration_includes_ipv6_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        network = IPNetwork('fe80::/64')
        nodegroup = self.create_managed_nodegroup(network=network)
        nodegroup, node, static = self.create_nodegroup_with_static_ip(
            nodegroup=nodegroup)
        self.assertDNSMatches(
            node.hostname, nodegroup.name, static.ip, version=6)


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
        expected = [unicode(subnet.cidr)]
        self.assertEqual(expected, get_trusted_networks())

    def test__returns_many_networks(self):
        subnets = [factory.make_Subnet() for _ in xrange(random.randint(1, 5))]
        expected = [unicode(subnet.cidr) for subnet in subnets]
        # Note: This test was seen randomly failing because the networks were
        # in an unexpected order...
        self.assertItemsEqual(expected, get_trusted_networks())
