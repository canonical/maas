# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
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
    is_dhcp_managed,
    )
from maasserver.dns import get_dns_server_address
from maasserver.enum import NODEGROUP_STATUS
from maasserver.models import Config
from maasserver.models.config import get_default_config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.celery import CeleryFixture
from netaddr import IPNetwork
from provisioningserver import tasks
from testresources import FixtureResource
from testtools.matchers import EndsWith


class TestDHCP(MAASServerTestCase):

    resources = (
        ('celery', FixtureResource(CeleryFixture())),
        )

    def test_is_dhcp_managed_follows_nodegroup_status(self):
        expected_results = {
            NODEGROUP_STATUS.PENDING: False,
            NODEGROUP_STATUS.REJECTED: False,
            NODEGROUP_STATUS.ACCEPTED: True,
        }
        nodegroups = {
            factory.make_node_group(status=status): value
            for status, value in expected_results.items()
        }
        self.patch(settings, "DHCP_CONNECT", True)
        results = {
            nodegroup.status: is_dhcp_managed(nodegroup)
            for nodegroup, value in nodegroups.items()
        }
        self.assertEquals(expected_results, results)

    def test_configure_dhcp_writes_dhcp_config(self):
        mocked_task = self.patch(dhcp, 'write_dhcp_config')
        self.patch(
            settings, 'DEFAULT_MAAS_URL',
            'http://%s/' % factory.getRandomIPAddress())
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            dhcp_key=factory.getRandomString(),
            interface=factory.make_name('eth'),
            network=IPNetwork("192.168.102.0/22"))

        self.patch(settings, "DHCP_CONNECT", True)
        configure_dhcp(nodegroup)
        dhcp_params = [
            'subnet_mask',
            'broadcast_ip',
            'router_ip',
            'ip_range_low',
            'ip_range_high',
            ]

        interface = nodegroup.get_managed_interface()
        expected_params = {
            param: getattr(interface, param)
            for param in dhcp_params}

        expected_params["omapi_key"] = nodegroup.dhcp_key
        expected_params["dns_servers"] = get_dns_server_address()
        expected_params["ntp_server"] = get_default_config()['ntp_server']
        expected_params["domain_name"] = nodegroup.name
        expected_params["subnet"] = '192.168.100.0'
        expected_params["dhcp_interfaces"] = interface.interface

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

        self.assertEqual(ip, kwargs['dns_servers'])

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
        interface = nodegroup.get_managed_interface()
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
                kwargs['kwargs']['router_ip'],
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
