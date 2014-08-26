# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for DHCP management."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random

from django.conf import settings
from maasserver import dhcp
from maasserver.dhcp import (
    configure_dhcp,
    get_interfaces_managed_by,
    make_subnet_config,
    split_ipv4_ipv6_interfaces,
    )
from maasserver.dns.zonegenerator import get_dns_server_address
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.models import Config
from maasserver.models.config import get_default_config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.celery import CeleryFixture
from maastesting.matchers import MockCalledOnceWith
from netaddr import (
    IPAddress,
    IPNetwork,
    )
from provisioningserver import tasks
from provisioningserver.utils.enum import map_enum
from testresources import FixtureResource
from testtools.matchers import (
    ContainsAll,
    EndsWith,
    Equals,
    HasLength,
    IsInstance,
    Not,
    )


class TestSplitIPv4IPv6Interfaces(MAASServerTestCase):
    """Tests for `split_ipv4_ipv6_interfaces`."""

    def make_ipv4_interface(self, nodegroup):
        return factory.make_node_group_interface(
            nodegroup, network=factory.getRandomNetwork())

    def make_ipv6_interface(self, nodegroup):
        return factory.make_node_group_interface(
            nodegroup, network=factory.make_ipv6_network())

    def test__separates_IPv4_from_IPv6_interfaces(self):
        nodegroup = factory.make_node_group()
        # Create 0-2 IPv4 cluster interfaces and 0-2 IPv6 cluster interfaces.
        ipv4_interfaces = [
            self.make_ipv4_interface(nodegroup)
            for _ in range(random.randint(0, 2))
            ]
        ipv6_interfaces = [
            self.make_ipv6_interface(nodegroup)
            for _ in range(random.randint(0, 2))
            ]
        interfaces = sorted(
            ipv4_interfaces + ipv6_interfaces,
            key=lambda *args: random.randint(0, 10))

        ipv4_result, ipv6_result = split_ipv4_ipv6_interfaces(interfaces)

        self.assertItemsEqual(ipv4_interfaces, ipv4_result)
        self.assertItemsEqual(ipv6_interfaces, ipv6_result)


class TestMakeSubnetConfig(MAASServerTestCase):
    """Tests for `make_subnet_config`."""

    def test__includes_all_parameters(self):
        interface = factory.make_node_group_interface(
            factory.make_node_group())
        config = make_subnet_config(
            interface, factory.make_name('dns'), factory.make_name('ntp'))
        self.assertIsInstance(config, dict)
        self.assertThat(
            config.keys(),
            ContainsAll([
                'subnet',
                'subnet_mask',
                'subnet_cidr',
                'broadcast_ip',
                'interface',
                'router_ip',
                'dns_servers',
                'ntp_server',
                'domain_name',
                'ip_range_low',
                'ip_range_high',
                ]))

    def test__sets_dns_and_ntp_from_arguments(self):
        interface = factory.make_node_group_interface(
            factory.make_node_group())
        dns = '%s %s' % (
            factory.getRandomIPAddress(),
            factory.make_ipv6_address(),
            )
        ntp = factory.make_name('ntp')
        config = make_subnet_config(interface, dns_servers=dns, ntp_server=ntp)
        self.expectThat(config['dns_servers'], Equals(dns))
        self.expectThat(config['ntp_server'], Equals(ntp))

    def test__sets_domain_name_from_cluster(self):
        nodegroup = factory.make_node_group()
        interface = factory.make_node_group_interface(nodegroup)
        config = make_subnet_config(
            interface, factory.make_name('dns'), factory.make_name('ntp'))
        self.expectThat(config['domain_name'], Equals(nodegroup.name))

    def test__sets_other_items_from_interface(self):
        interface = factory.make_node_group_interface(
            factory.make_node_group())
        config = make_subnet_config(
            interface, factory.make_name('dns'), factory.make_name('ntp'))
        self.expectThat(config['broadcast_ip'], Equals(interface.broadcast_ip))
        self.expectThat(config['interface'], Equals(interface.interface))
        self.expectThat(config['router_ip'], Equals(interface.router_ip))

    def test__passes_IP_addresses_as_strings(self):
        interface = factory.make_node_group_interface(
            factory.make_node_group())
        config = make_subnet_config(
            interface, factory.make_name('dns'), factory.make_name('ntp'))
        self.expectThat(config['subnet'], IsInstance(unicode))
        self.expectThat(config['subnet_mask'], IsInstance(unicode))
        self.expectThat(config['subnet_cidr'], IsInstance(unicode))
        self.expectThat(config['broadcast_ip'], IsInstance(unicode))
        self.expectThat(config['router_ip'], IsInstance(unicode))
        self.expectThat(config['ip_range_low'], IsInstance(unicode))
        self.expectThat(config['ip_range_high'], IsInstance(unicode))

    def test__defines_IPv4_subnet(self):
        interface = factory.make_node_group_interface(
            factory.make_node_group(), network=IPNetwork('10.9.8.7/24'))
        config = make_subnet_config(
            interface, factory.make_name('dns'), factory.make_name('ntp'))
        self.expectThat(config['subnet'], Equals('10.9.8.0'))
        self.expectThat(config['subnet_mask'], Equals('255.255.255.0'))
        self.expectThat(config['subnet_cidr'], Equals('10.9.8.0/24'))

    def test__defines_IPv6_subnet(self):
        interface = factory.make_node_group_interface(
            factory.make_node_group(),
            network=IPNetwork('fd38:c341:27da:c831::/64'))
        config = make_subnet_config(
            interface, factory.make_name('dns'), factory.make_name('ntp'))
        # Don't expect a specific literal value, like we do for IPv4; there
        # are different spellings.
        self.expectThat(
            IPAddress(config['subnet']),
            Equals(IPAddress('fd38:c341:27da:c831::')))
        # (Netmask is not used for the IPv6 config, so ignore it.)
        self.expectThat(
            IPNetwork(config['subnet_cidr']),
            Equals(IPNetwork('fd38:c341:27da:c831::/64')))

    def test__passes_dynamic_range(self):
        interface = factory.make_node_group_interface(
            factory.make_node_group())
        config = make_subnet_config(
            interface, factory.make_name('dns'), factory.make_name('ntp'))
        self.expectThat(
            (config['ip_range_low'], config['ip_range_high']),
            Equals((interface.ip_range_low, interface.ip_range_high)))
        self.expectThat(
            config['ip_range_low'], Not(Equals(interface.static_ip_range_low)))


class TestGetInterfacesManagedBy(MAASServerTestCase):
    """Tests for `get_interfaces_managed_by`."""

    def test_get_interfaces_managed_by_returns_managed_interfaces(self):
        self.patch(settings, "DHCP_CONNECT", False)
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        self.patch(settings, "DHCP_CONNECT", True)
        managed_interfaces = get_interfaces_managed_by(nodegroup)
        self.assertThat(managed_interfaces, HasLength(1))
        self.assertItemsEqual(
            nodegroup.nodegroupinterface_set.all(),
            managed_interfaces)

    def test_get_interfaces_managed_by_returns_None_if_not_accepted(self):
        unaccepted_statuses = set(map_enum(NODEGROUP_STATUS).values())
        unaccepted_statuses.remove(NODEGROUP_STATUS.ACCEPTED)
        managed_interfaces = {
            status: get_interfaces_managed_by(
                factory.make_node_group(
                    status=status,
                    management=NODEGROUPINTERFACE_MANAGEMENT.DHCP))
            for status in unaccepted_statuses
            }
        self.assertEqual(
            {status: None for status in unaccepted_statuses},
            managed_interfaces)


class TestConfigureDHCP(MAASServerTestCase):
    """Tests for `configure_dhcp`."""

    resources = (
        ('celery', FixtureResource(CeleryFixture())),
        )

    def test_configure_dhcp_stops_server_if_no_managed_interface(self):
        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(dhcp, 'stop_dhcp_server')
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED,
            )
        configure_dhcp(nodegroup)
        self.assertEqual(1, dhcp.stop_dhcp_server.apply_async.call_count)

    def test_configure_dhcp_obeys_DHCP_CONNECT(self):
        self.patch(settings, "DHCP_CONNECT", False)
        self.patch(dhcp, 'write_dhcp_config')
        factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        self.assertEqual(0, dhcp.write_dhcp_config.apply_async.call_count)

    def test_configure_dhcp_writes_dhcp_config(self):
        mocked_task = self.patch(dhcp, 'write_dhcp_config')
        self.patch(
            settings, 'DEFAULT_MAAS_URL',
            'http://%s/' % factory.getRandomIPAddress())
        self.patch(settings, "DHCP_CONNECT", True)
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            dhcp_key=factory.make_string(),
            interface=factory.make_name('eth'),
            network=IPNetwork("192.168.102.0/22"))
        # Create a second DHCP-managed interface.
        factory.make_node_group_interface(
            nodegroup=nodegroup,
            interface=factory.make_name('eth'),
            network=IPNetwork("10.1.1/24"),
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            )

        configure_dhcp(nodegroup)

        expected_params = {
            'omapi_key': nodegroup.dhcp_key,
            'dhcp_interfaces': ' '.join([
                interface.interface
                for interface in nodegroup.get_managed_interfaces()
                ]),
            'dhcp_subnets': [
                make_subnet_config(
                    interface, get_dns_server_address(),
                    get_default_config()['ntp_server'])
                for interface in nodegroup.get_managed_interfaces()
                ],
            }

        args, kwargs = mocked_task.apply_async.call_args
        result_params = kwargs['kwargs']
        # The check that the callback is correct is done in
        # test_configure_dhcp_restart_dhcp_server.
        del result_params['callback']

        self.assertEqual(expected_params, result_params)

    def test_dhcp_config_uses_dns_server_from_cluster_controller(self):
        mocked_task = self.patch(dhcp, 'write_dhcp_config')
        ip = factory.getRandomIPAddress()
        maas_url = 'http://%s/' % ip
        nodegroup = factory.make_node_group(
            maas_url=maas_url,
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            dhcp_key=factory.make_string(),
            interface=factory.make_name('eth'),
            network=IPNetwork("192.168.102.0/22"))
        self.patch(settings, "DHCP_CONNECT", True)
        configure_dhcp(nodegroup)
        kwargs = mocked_task.apply_async.call_args[1]['kwargs']

        self.assertEqual(ip, kwargs['dhcp_subnets'][0]['dns_servers'])

    def test_configure_dhcp_restarts_dhcp_server(self):
        self.patch(tasks, "sudo_write_file")
        restart_dhcpv4 = self.patch(tasks, "restart_dhcpv4")
        self.patch(settings, "DHCP_CONNECT", True)
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        configure_dhcp(nodegroup)
        self.assertThat(restart_dhcpv4, MockCalledOnceWith())

    def test_configure_dhcp_is_called_with_valid_dhcp_key(self):
        self.patch(dhcp, 'write_dhcp_config')
        self.patch(settings, "DHCP_CONNECT", True)
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED, dhcp_key='',
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        configure_dhcp(nodegroup)
        args, kwargs = dhcp.write_dhcp_config.apply_async.call_args
        self.assertThat(kwargs['kwargs']['omapi_key'], EndsWith('=='))

    def test_write_dhcp_config_task_routed_to_nodegroup_worker(self):
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.PENDING,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(dhcp, 'write_dhcp_config')
        nodegroup.accept()
        args, kwargs = dhcp.write_dhcp_config.apply_async.call_args
        self.assertEqual(nodegroup.work_queue, kwargs['queue'])

    def test_write_dhcp_config_restart_task_routed_to_nodegroup_worker(self):
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.PENDING,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(tasks, 'sudo_write_file')
        task = self.patch(dhcp, 'restart_dhcp_server')
        nodegroup.accept()
        args, kwargs = task.subtask.call_args
        self.assertEqual(nodegroup.work_queue, kwargs['options']['queue'])


class TestDHCPConnect(MAASServerTestCase):
    """Tests for DHCP signals triggered when saving a cluster interface."""

    resources = (
        ('celery', FixtureResource(CeleryFixture())),
        )

    def test_dhcp_config_gets_written_when_nodegroup_becomes_active(self):
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.PENDING,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(dhcp, 'write_dhcp_config')
        nodegroup.accept()
        self.assertEqual(1, dhcp.write_dhcp_config.apply_async.call_count)

    def test_dhcp_config_gets_written_when_nodegroup_name_changes(self):
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(dhcp, 'write_dhcp_config')
        new_name = factory.make_name('dns name'),

        nodegroup.name = new_name
        nodegroup.save()

        self.assertEqual(1, dhcp.write_dhcp_config.apply_async.call_count)

    def test_dhcp_config_gets_written_when_interface_IP_changes(self):
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        [interface] = nodegroup.nodegroupinterface_set.all()
        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(dhcp, 'write_dhcp_config')

        interface.ip = factory.pick_ip_in_network(
            interface.network, but_not=[interface.ip])
        interface.save()

        self.assertEqual(1, dhcp.write_dhcp_config.apply_async.call_count)

    def test_dhcp_config_gets_written_when_interface_management_changes(self):
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        [interface] = nodegroup.nodegroupinterface_set.all()
        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(dhcp, 'write_dhcp_config')

        interface.management = NODEGROUPINTERFACE_MANAGEMENT.DHCP
        interface.save()

        self.assertEqual(1, dhcp.write_dhcp_config.apply_async.call_count)

    def test_dhcp_config_gets_written_when_interface_name_changes(self):
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        [interface] = nodegroup.get_managed_interfaces()
        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(dhcp, 'write_dhcp_config')

        interface.interface = factory.make_name('itf')
        interface.save()

        self.assertEqual(1, dhcp.write_dhcp_config.apply_async.call_count)

    def test_dhcp_config_gets_written_when_netmask_changes(self):
        network = factory.getRandomNetwork(slash='255.255.255.0')
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED, network=network,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        [interface] = nodegroup.get_managed_interfaces()
        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(dhcp, 'write_dhcp_config')

        interface.subnet_mask = '255.255.0.0'
        interface.save()

        self.assertEqual(1, dhcp.write_dhcp_config.apply_async.call_count)

    def test_dhcp_config_gets_written_when_interface_router_ip_changes(self):
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        [interface] = nodegroup.get_managed_interfaces()
        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(dhcp, 'write_dhcp_config')
        new_router_ip = factory.pick_ip_in_network(
            interface.network, but_not=[interface.router_ip])

        interface.router_ip = new_router_ip
        interface.save()

        self.assertEqual(1, dhcp.write_dhcp_config.apply_async.call_count)

    def test_dhcp_config_gets_written_when_ip_range_changes(self):
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        [interface] = nodegroup.get_managed_interfaces()
        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(dhcp, 'write_dhcp_config')

        interface.ip_range_low = unicode(
            IPAddress(interface.ip_range_low) + 1)
        interface.ip_range_high = unicode(
            IPAddress(interface.ip_range_high) - 1)
        interface.save()

        self.assertEqual(1, dhcp.write_dhcp_config.apply_async.call_count)

    def test_dhcp_config_is_not_written_when_foreign_dhcp_changes(self):
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        [interface] = nodegroup.get_managed_interfaces()
        self.patch(dhcp, 'write_dhcp_config')
        self.patch(settings, "DHCP_CONNECT", True)

        interface.foreign_dhcp = factory.pick_ip_in_network(
            interface.network)
        interface.save()

        self.assertEqual([], dhcp.write_dhcp_config.apply_async.mock_calls)

    def test_dhcp_config_gets_written_when_ntp_server_changes(self):
        # When the "ntp_server" Config item is changed, check that all
        # nodegroups get their DHCP config re-written.
        num_active_nodegroups = random.randint(1, 10)
        num_inactive_nodegroups = random.randint(1, 10)
        for x in range(num_active_nodegroups):
            factory.make_node_group(
                status=NODEGROUP_STATUS.ACCEPTED,
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        for x in range(num_inactive_nodegroups):
            factory.make_node_group(
                status=NODEGROUP_STATUS.PENDING,
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        # Silence stop_dhcp_server: it will be called for the inactive
        # nodegroups.
        self.patch(dhcp, 'stop_dhcp_server')

        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(dhcp, 'write_dhcp_config')

        Config.objects.set_config("ntp_server", factory.getRandomIPAddress())

        self.assertEqual(
            num_active_nodegroups,
            dhcp.write_dhcp_config.apply_async.call_count)
