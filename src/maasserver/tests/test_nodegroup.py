# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the NodeGroup model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from django.conf import settings
import maasserver
from maasserver.dns import get_dns_server_address
from maasserver.enum import NODEGROUPINTERFACE_MANAGEMENT
from maasserver.models import NodeGroup
from maasserver.server_address import get_maas_facing_server_address
from maasserver.testing import reload_object
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from maasserver.worker_user import get_worker_user
from maastesting.celery import CeleryFixture
from maastesting.fakemethod import FakeMethod
from provisioningserver.omshell import (
    generate_omapi_key,
    Omshell,
    )
from testresources import FixtureResource
from testtools.matchers import (
    GreaterThan,
    MatchesStructure,
    )


def make_dhcp_settings():
    """Create a dict of arbitrary nodegroup configuration parameters."""
    return {
        'interface': factory.make_name('interface'),
        'subnet_mask': '255.0.0.0',
        'broadcast_ip': '10.255.255.255',
        'router_ip': factory.getRandomIPAddress(),
        'ip_range_low': '10.0.0.1',
        'ip_range_high': '10.254.254.254',
    }


class TestNodeGroupManager(TestCase):

    def test_new_creates_nodegroup(self):
        name = factory.make_name('nodegroup')
        uuid = factory.getRandomUUID()
        ip = factory.getRandomIPAddress()
        self.assertThat(
            NodeGroup.objects.new(name, uuid, ip),
            MatchesStructure.fromExample(
                {'name': name, 'uuid': uuid, 'worker_ip': ip}))

    def test_new_does_not_require_dhcp_settings(self):
        name = factory.make_name('nodegroup')
        uuid = factory.getRandomUUID()
        ip = factory.getRandomIPAddress()
        nodegroup = NodeGroup.objects.new(name, uuid, ip)
        self.assertThat(
            nodegroup,
            MatchesStructure.fromExample({
                item: None
                for item in make_dhcp_settings().keys()}))

    def test_new_requires_all_dhcp_settings_or_none(self):
        name = factory.make_name('nodegroup')
        uuid = factory.make_name('uuid')
        ip = factory.getRandomIPAddress()
        self.assertRaises(
            AssertionError,
            NodeGroup.objects.new, name, uuid, ip, subnet_mask='255.0.0.0')

    def test_new_creates_nodegroup_with_given_dhcp_settings(self):
        name = factory.make_name('nodegroup')
        uuid = factory.make_name('uuid')
        ip = factory.getRandomIPAddress()
        dhcp_settings = make_dhcp_settings()
        nodegroup = NodeGroup.objects.new(name, uuid, ip, **dhcp_settings)
        nodegroup = reload_object(nodegroup)
        self.assertEqual(name, nodegroup.name)
        self.assertThat(
            nodegroup, MatchesStructure.fromExample(dhcp_settings))

    def test_new_assigns_token_and_key_for_worker_user(self):
        nodegroup = NodeGroup.objects.new(
            factory.make_name('nodegroup'), factory.make_name('uuid'),
            factory.getRandomIPAddress())
        self.assertIsNotNone(nodegroup.api_token)
        self.assertIsNotNone(nodegroup.api_key)
        self.assertEqual(get_worker_user(), nodegroup.api_token.user)
        self.assertEqual(nodegroup.api_key, nodegroup.api_token.key)

    def test_new_creates_nodegroup_with_empty_dhcp_key(self):
        nodegroup = NodeGroup.objects.new(
            factory.make_name('nodegroup'), factory.make_name('uuid'),
            factory.getRandomIPAddress())
        self.assertEqual('', nodegroup.dhcp_key)

    def test_new_stores_dhcp_key_on_nodegroup(self):
        key = generate_omapi_key()
        nodegroup = NodeGroup.objects.new(
            factory.make_name('nodegroup'), factory.make_name('uuid'),
            factory.getRandomIPAddress(),
            dhcp_key=key)
        self.assertEqual(key, nodegroup.dhcp_key)

    def test_ensure_master_creates_minimal_master_nodegroup(self):
        self.assertThat(
            NodeGroup.objects.ensure_master(),
            MatchesStructure.fromExample({
                'name': 'master',
                'workder_id': 'master',
                'worker_ip': '127.0.0.1',
                'subnet_mask': None,
                'broadcast_ip': None,
                'router_ip': None,
                'ip_range_low': None,
                'ip_range_high': None,
            }))

    def test_ensure_master_writes_master_nodegroup_to_database(self):
        master = NodeGroup.objects.ensure_master()
        self.assertEqual(
            master.id, NodeGroup.objects.get(name=master.name).id)

    def test_ensure_master_creates_dhcp_key(self):
        master = NodeGroup.objects.ensure_master()
        self.assertThat(len(master.dhcp_key), GreaterThan(20))

    def test_ensure_master_returns_same_nodegroup_every_time(self):
        self.assertEqual(
            NodeGroup.objects.ensure_master().id,
            NodeGroup.objects.ensure_master().id)

    def test_ensure_master_does_not_return_other_nodegroup(self):
        self.assertNotEqual(
            NodeGroup.objects.new(
                factory.make_name('nodegroup'), factory.make_name('uuid'),
                factory.getRandomIPAddress()),
            NodeGroup.objects.ensure_master())

    def test_ensure_master_preserves_existing_attributes(self):
        master = NodeGroup.objects.ensure_master()
        key = factory.getRandomString()
        master.dhcp_key = key
        master.save()
        self.assertEqual(key, NodeGroup.objects.ensure_master().dhcp_key)

    def test_get_by_natural_key_looks_up_by_uuid(self):
        nodegroup = factory.make_node_group()
        self.assertEqual(
            nodegroup,
            NodeGroup.objects.get_by_natural_key(nodegroup.uuid))

    def test_get_by_natural_key_will_not_return_other_nodegroup(self):
        factory.make_node_group()
        self.assertRaises(
            NodeGroup.DoesNotExist,
            NodeGroup.objects.get_by_natural_key,
            factory.make_name("nonexistent-nodegroup"))


class TestNodeGroup(TestCase):

    resources = (
        ('celery', FixtureResource(CeleryFixture())),
        )

    def test_is_dhcp_enabled_returns_False_if_interface_not_managed(self):
        nodegroup = factory.make_node_group()
        interface = nodegroup.get_managed_interface()
        interface.management = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
        interface.save()
        self.assertFalse(nodegroup.is_dhcp_enabled())

    def test_set_up_dhcp_writes_dhcp_config(self):
        mocked_task = self.patch(
            maasserver.models.nodegroup, 'write_dhcp_config')
        self.patch(
            settings, 'DEFAULT_MAAS_URL',
            'http://%s/' % factory.getRandomIPAddress())
        nodegroup = factory.make_node_group(
            dhcp_key=factory.getRandomString(),
            ip_range_low='192.168.102.1', ip_range_high='192.168.103.254',
            subnet_mask='255.255.252.0', broadcast_ip='192.168.103.255')
        nodegroup.set_up_dhcp()
        dhcp_params = [
            'subnet_mask', 'broadcast_ip', 'router_ip',
            'ip_range_low', 'ip_range_high']

        interface = nodegroup.get_managed_interface()
        expected_params = {
            param: getattr(interface, param)
            for param in dhcp_params}

        # Currently all nodes use the central TFTP server.  This will be
        # decentralized to use NodeGroup.worker_ip later.
        expected_params["next_server"] = get_maas_facing_server_address()

        expected_params["omapi_key"] = nodegroup.dhcp_key
        expected_params["dns_servers"] = get_dns_server_address()
        expected_params["subnet"] = '192.168.100.0'

        mocked_task.delay.assert_called_once_with(**expected_params)

    def test_add_dhcp_host_maps_adds_maps_if_managing_dhcp(self):
        self.patch(Omshell, 'create', FakeMethod())
        nodegroup = factory.make_node_group()
        self.patch(nodegroup, 'is_dhcp_enabled', FakeMethod(result=True))
        leases = factory.make_random_leases()
        nodegroup.add_dhcp_host_maps(leases)
        self.assertEqual(
            [(leases.keys()[0], leases.values()[0])],
            Omshell.create.extract_args())

    def test_add_dhcp_host_maps_does_nothing_if_not_managing_dhcp(self):
        self.patch(Omshell, 'create', FakeMethod())
        nodegroup = factory.make_node_group()
        self.patch(nodegroup, 'is_dhcp_enabled', FakeMethod(result=False))
        leases = factory.make_random_leases()
        nodegroup.add_dhcp_host_maps(leases)
        self.assertEqual([], Omshell.create.extract_args())

    def test_get_managed_interface_returns_managed_interface(self):
        nodegroup = factory.make_node_group()
        interface = nodegroup.nodegroupinterface_set.all()[0]
        self.assertEqual(interface, nodegroup.get_managed_interface())

    def test_get_managed_interface_does_not_return_unmanaged_interface(self):
        nodegroup = factory.make_node_group()
        interface = nodegroup.nodegroupinterface_set.all()[0]
        interface.management = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
        interface.save()
        self.assertIsNone(nodegroup.get_managed_interface())

    def test_get_managed_interface_does_not_return_unrelated_interface(self):
        nodegroup = factory.make_node_group()
        # Create another nodegroup with a managed interface.
        factory.make_node_group()
        interface = nodegroup.nodegroupinterface_set.all()[0]
        interface.management = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
        interface.save()
        self.assertIsNone(nodegroup.get_managed_interface())
