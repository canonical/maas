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

from functools import partial
import random

from django.conf import settings
from maasserver import dhcp
from maasserver.dhcp import (
    configure_dhcp,
    get_interfaces_managed_by,
    )
from maasserver.dns import get_dns_server_address
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.models import Config
from maasserver.models.config import get_default_config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import map_enum
from maastesting.celery import CeleryFixture
from netaddr import (
    IPAddress,
    IPNetwork,
    )
from provisioningserver import tasks
from testresources import FixtureResource
from testtools.matchers import EndsWith


class TestDHCP(MAASServerTestCase):

    resources = (
        ('celery', FixtureResource(CeleryFixture())),
        )

    def test_get_interfaces_managed_by_returns_managed_interfaces(self):
        self.patch(settings, "DHCP_CONNECT", False)
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        self.patch(settings, "DHCP_CONNECT", True)
        managed_interfaces = get_interfaces_managed_by(nodegroup)
        self.assertNotEqual([], managed_interfaces)
        self.assertEqual(1, len(managed_interfaces))
        self.assertEqual(
            list(nodegroup.nodegroupinterface_set.all()),
            managed_interfaces)

    def test_get_interfaces_managed_by_obeys_DHCP_CONNECT(self):
        self.patch(settings, "DHCP_CONNECT", False)
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        self.assertEqual([], get_interfaces_managed_by(nodegroup))

    def test_get_interfaces_managed_by_returns_empty_if_not_accepted(self):
        self.patch(settings, "DHCP_CONNECT", True)
        unaccepted_statuses = set(map_enum(NODEGROUP_STATUS).values())
        unaccepted_statuses.remove(NODEGROUP_STATUS.ACCEPTED)
        managed_interfaces = {
            status: get_interfaces_managed_by(
                factory.make_node_group(status=status))
            for status in unaccepted_statuses
            }
        self.assertEqual(
            {status: [] for status in unaccepted_statuses},
            managed_interfaces)

    def test_configure_dhcp_writes_dhcp_config(self):
        mocked_task = self.patch(dhcp, 'write_dhcp_config')
        self.patch(
            settings, 'DEFAULT_MAAS_URL',
            'http://%s/' % factory.getRandomIPAddress())
        self.patch(settings, "DHCP_CONNECT", True)
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            dhcp_key=factory.getRandomString(),
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
        dhcp_subnets = []
        for interface in nodegroup.get_managed_interfaces():
            dhcp_params = [
                'interface',
                'subnet_mask',
                'broadcast_ip',
                'router_ip',
                'ip_range_low',
                'ip_range_high',
                ]

            dhcp_subnet = {
                param: getattr(interface, param)
                for param in dhcp_params}
            dhcp_subnet["dns_servers"] = get_dns_server_address()
            dhcp_subnet["ntp_server"] = get_default_config()['ntp_server']
            dhcp_subnet["domain_name"] = nodegroup.name
            dhcp_subnet["subnet"] = unicode(
                IPAddress(interface.ip_range_low) &
                IPAddress(interface.subnet_mask))
            dhcp_subnets.append(dhcp_subnet)

        expected_params = {}
        expected_params["omapi_key"] = nodegroup.dhcp_key
        expected_params["dhcp_interfaces"] = ' '.join([
            interface.interface
            for interface in nodegroup.get_managed_interfaces()])
        expected_params["dhcp_subnets"] = dhcp_subnets

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
            dhcp_key=factory.getRandomString(),
            interface=factory.make_name('eth'),
            network=IPNetwork("192.168.102.0/22"))
        self.patch(settings, "DHCP_CONNECT", True)
        configure_dhcp(nodegroup)
        kwargs = mocked_task.apply_async.call_args[1]['kwargs']

        self.assertEqual(ip, kwargs['dhcp_subnets'][0]['dns_servers'])

    def test_configure_dhcp_restart_dhcp_server(self):
        self.patch(tasks, "sudo_write_file")
        mocked_check_call = self.patch(tasks, "call_and_check")
        self.patch(settings, "DHCP_CONNECT", True)
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        configure_dhcp(nodegroup)
        self.assertEqual(
            mocked_check_call.call_args[0][0],
            ['sudo', '-n', 'service', 'maas-dhcp-server', 'restart'])

    def test_configure_dhcp_is_called_with_valid_dhcp_key(self):
        self.patch(dhcp, 'write_dhcp_config')
        self.patch(settings, "DHCP_CONNECT", True)
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED, dhcp_key='')
        configure_dhcp(nodegroup)
        args, kwargs = dhcp.write_dhcp_config.apply_async.call_args
        self.assertThat(kwargs['kwargs']['omapi_key'], EndsWith('=='))

    def test_dhcp_config_gets_written_when_nodegroup_becomes_active(self):
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.PENDING)
        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(dhcp, 'write_dhcp_config')
        nodegroup.accept()
        self.assertEqual(1, dhcp.write_dhcp_config.apply_async.call_count)

    def test_dhcp_config_gets_written_when_nodegroup_name_changes(self):
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(dhcp, 'write_dhcp_config')
        new_name = factory.make_name('dns name'),

        nodegroup.name = new_name
        nodegroup.save()

        self.assertEqual(1, dhcp.write_dhcp_config.apply_async.call_count)

    def test_write_dhcp_config_task_routed_to_nodegroup_worker(self):
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.PENDING)
        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(dhcp, 'write_dhcp_config')
        nodegroup.accept()
        args, kwargs = dhcp.write_dhcp_config.apply_async.call_args
        self.assertEqual(nodegroup.work_queue, kwargs['queue'])

    def test_write_dhcp_config_restart_task_routed_to_nodegroup_worker(self):
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.PENDING)
        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(tasks, 'sudo_write_file')
        task = self.patch(dhcp, 'restart_dhcp_server')
        nodegroup.accept()
        args, kwargs = task.subtask.call_args
        self.assertEqual(nodegroup.work_queue, kwargs['options']['queue'])

    def test_dhcp_config_gets_written_when_nodegroupinterface_changes(self):
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        [interface] = nodegroup.get_managed_interfaces()
        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(dhcp, 'write_dhcp_config')
        get_ip_in_network = partial(
            factory.getRandomIPInNetwork, interface.network)
        new_router_ip = next(
            ip for ip in iter(get_ip_in_network, None)
            if ip != interface.router_ip)
        interface.router_ip = new_router_ip
        interface.save()
        args, kwargs = dhcp.write_dhcp_config.apply_async.call_args
        self.assertEqual(
            (1, new_router_ip),
            (
                dhcp.write_dhcp_config.apply_async.call_count,
                kwargs['kwargs']['dhcp_subnets'][0]['router_ip'],
            ))

    def test_dhcp_config_gets_written_when_ntp_server_changes(self):
        # When the "ntp_server" Config item is changed, check that all
        # nodegroups get their DHCP config re-written.
        num_active_nodegroups = random.randint(1, 10)
        num_inactive_nodegroups = random.randint(1, 10)
        for x in range(num_active_nodegroups):
            factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        for x in range(num_inactive_nodegroups):
            factory.make_node_group(status=NODEGROUP_STATUS.PENDING)

        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(dhcp, 'write_dhcp_config')

        Config.objects.set_config("ntp_server", factory.getRandomIPAddress())

        self.assertEqual(
            num_active_nodegroups,
            dhcp.write_dhcp_config.apply_async.call_count)
