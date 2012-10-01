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

from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.models import (
    NodeGroup,
    nodegroup as nodegroup_module,
    )
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
    """Return an arbitrary dict of DHCP settings."""
    network = factory.getRandomNetwork()
    return network, {
        'interface': factory.make_name('interface'),
        'subnet_mask': str(network.netmask),
        'broadcast_ip': str(network.broadcast),
        'router_ip': factory.getRandomIPInNetwork(network),
        'ip_range_low': factory.getRandomIPInNetwork(network),
        'ip_range_high': factory.getRandomIPInNetwork(network),
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
        dhcp_network, dhcp_settings = make_dhcp_settings()
        self.assertThat(
            nodegroup, MatchesStructure.fromExample(
                dict.fromkeys(dhcp_settings)))

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
        dhcp_network, dhcp_settings = make_dhcp_settings()
        ip = factory.getRandomIPInNetwork(dhcp_network)
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
                'worker_id': 'master',
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

    def test_ensure_master_returns_oldest_nodegroup(self):
        first_nodegroup = NodeGroup.objects.new(
            factory.make_name('nodegroup'), factory.make_name('uuid'),
            factory.getRandomIPAddress())
        NodeGroup.objects.new(
            factory.make_name('nodegroup'), factory.make_name('uuid'),
            factory.getRandomIPAddress())
        self.assertEqual(first_nodegroup, NodeGroup.objects.ensure_master())

    def test_ensure_master_preserves_existing_attributes(self):
        master = NodeGroup.objects.ensure_master()
        key = factory.getRandomString()
        master.dhcp_key = key
        master.save()
        self.assertEqual(key, NodeGroup.objects.ensure_master().dhcp_key)

    def test_ensure_master_creates_accepted_nodegroup(self):
        master = NodeGroup.objects.ensure_master()
        self.assertEqual(NODEGROUP_STATUS.ACCEPTED, master.status)

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

    def test_work_queue_returns_uuid(self):
        nodegroup = factory.make_node_group()
        self.assertEqual(nodegroup.uuid, nodegroup.work_queue)

    def test_add_dhcp_host_maps_adds_maps_if_managing_dhcp(self):
        self.patch(Omshell, 'create', FakeMethod())
        nodegroup = factory.make_node_group()
        leases = factory.make_random_leases()
        nodegroup.add_dhcp_host_maps(leases)
        self.assertEqual(
            [(leases.keys()[0], leases.values()[0])],
            Omshell.create.extract_args())

    def test_add_dhcp_host_maps_does_nothing_if_not_managing_dhcp(self):
        self.patch(Omshell, 'create', FakeMethod())
        nodegroup = factory.make_node_group(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        leases = factory.make_random_leases()
        nodegroup.add_dhcp_host_maps(leases)
        self.assertEqual([], Omshell.create.extract_args())

    def test_fires_tasks_routed_to_nodegroup_worker(self):
        nodegroup = factory.make_node_group()
        task = self.patch(nodegroup_module, 'add_new_dhcp_host_map')
        leases = factory.make_random_leases()
        nodegroup.add_dhcp_host_maps(leases)
        args, kwargs = task.apply_async.call_args
        self.assertEqual(nodegroup.work_queue, kwargs['queue'])

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

    def test_accept_node_changes_status(self):
        nodegroup = factory.make_node_group(
            status=factory.getRandomEnum(NODEGROUP_STATUS))
        nodegroup.accept()
        self.assertEqual(nodegroup.status, NODEGROUP_STATUS.ACCEPTED)

    def test_reject_node_changes_status(self):
        nodegroup = factory.make_node_group(
            status=factory.getRandomEnum(NODEGROUP_STATUS))
        nodegroup.reject()
        self.assertEqual(nodegroup.status, NODEGROUP_STATUS.REJECTED)
