# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the NodeGroup model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from django.db.models.signals import post_save
import django.dispatch
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.models import (
    Config,
    NodeGroup,
    nodegroup as nodegroup_module,
    )
from maasserver.testing import reload_object
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import map_enum
from maasserver.utils.orm import get_one
from maasserver.worker_user import get_worker_user
from maastesting.celery import CeleryFixture
from maastesting.fakemethod import FakeMethod
from mock import (
    call,
    Mock,
    )
from provisioningserver import tasks
from provisioningserver.omshell import (
    generate_omapi_key,
    Omshell,
    )
from testresources import FixtureResource
from testtools.matchers import (
    EndsWith,
    GreaterThan,
    MatchesStructure,
    )


def make_dhcp_settings():
    """Return an arbitrary dict of DHCP settings."""
    network = factory.getRandomNetwork()
    return network, {
        'interface': factory.make_name('interface'),
        'subnet_mask': unicode(network.netmask),
        'broadcast_ip': unicode(network.broadcast),
        'router_ip': factory.getRandomIPInNetwork(network),
        'ip_range_low': factory.getRandomIPInNetwork(network),
        'ip_range_high': factory.getRandomIPInNetwork(network),
        }


class TestNodeGroupManager(MAASServerTestCase):

    def test_new_creates_nodegroup_with_interface(self):
        name = factory.make_name('nodegroup')
        uuid = factory.getRandomUUID()
        ip = factory.getRandomIPAddress()
        nodegroup = NodeGroup.objects.new(name, uuid, ip)
        interface = get_one(nodegroup.nodegroupinterface_set.all())
        self.assertEqual(
            (name, uuid, ip),
            (nodegroup.name, nodegroup.uuid, interface.ip))

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
        interface = get_one(nodegroup.nodegroupinterface_set.all())
        self.assertEqual(name, nodegroup.name)
        self.assertThat(
            interface, MatchesStructure.byEquality(**dhcp_settings))

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

    def test_ensure_master_creates_minimal_interface(self):
        master = NodeGroup.objects.ensure_master()
        interface = get_one(master.nodegroupinterface_set.all())
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                ip='127.0.0.1',
                subnet_mask=None,
                broadcast_ip=None,
                router_ip=None,
                ip_range_low=None,
                ip_range_high=None,
            ))

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

    def test__mass_change_status_changes_statuses(self):
        old_status = factory.getRandomEnum(NODEGROUP_STATUS)
        nodegroup1 = factory.make_node_group(status=old_status)
        nodegroup2 = factory.make_node_group(status=old_status)
        new_status = factory.getRandomEnum(
            NODEGROUP_STATUS, but_not=[old_status])
        changed = NodeGroup.objects._mass_change_status(old_status, new_status)
        self.assertEqual(
            (
                reload_object(nodegroup1).status,
                reload_object(nodegroup2).status,
                2,
            ),
            (
                new_status,
                new_status,
                changed,
            ))

    def test__mass_change_status_calls_post_save_signal(self):
        old_status = factory.getRandomEnum(NODEGROUP_STATUS)
        nodegroup = factory.make_node_group(status=old_status)
        recorder = Mock()

        def post_save_NodeGroup(sender, instance, created, **kwargs):
            recorder(instance)

        django.dispatch.Signal.connect(
            post_save, post_save_NodeGroup, sender=NodeGroup)
        self.addCleanup(
            django.dispatch.Signal.disconnect, post_save,
            receiver=post_save_NodeGroup, sender=NodeGroup)
        NodeGroup.objects._mass_change_status(
            old_status, factory.getRandomEnum(NODEGROUP_STATUS))
        self.assertEqual(
            [call(nodegroup)], recorder.call_args_list)

    def test_reject_all_pending_rejects_nodegroups(self):
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.PENDING)
        changed = NodeGroup.objects.reject_all_pending()
        self.assertEqual(
            (NODEGROUP_STATUS.REJECTED, 1),
            (reload_object(nodegroup).status, changed))

    def test_reject_all_pending_does_not_change_others(self):
        unaffected_status = factory.getRandomEnum(
            NODEGROUP_STATUS, but_not=[NODEGROUP_STATUS.PENDING])
        nodegroup = factory.make_node_group(status=unaffected_status)
        changed_count = NodeGroup.objects.reject_all_pending()
        self.assertEqual(
            (unaffected_status, 0),
            (reload_object(nodegroup).status, changed_count))

    def test_accept_all_pending_accepts_nodegroups(self):
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.PENDING)
        changed = NodeGroup.objects.accept_all_pending()
        self.assertEqual(
            (NODEGROUP_STATUS.ACCEPTED, 1),
            (reload_object(nodegroup).status, changed))

    def test_accept_all_pending_does_not_change_others(self):
        unaffected_status = factory.getRandomEnum(
            NODEGROUP_STATUS, but_not=[NODEGROUP_STATUS.PENDING])
        nodegroup = factory.make_node_group(status=unaffected_status)
        changed_count = NodeGroup.objects.accept_all_pending()
        self.assertEqual(
            (unaffected_status, 0),
            (reload_object(nodegroup).status, changed_count))

    def test_import_boot_images_accepted_clusters_calls_tasks(self):
        recorder = self.patch(nodegroup_module, 'import_boot_images')
        proxy = factory.make_name('proxy')
        Config.objects.set_config('http_proxy', proxy)
        accepted_nodegroups = [
            factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED),
            factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED),
        ]
        factory.make_node_group(status=NODEGROUP_STATUS.REJECTED)
        factory.make_node_group(status=NODEGROUP_STATUS.PENDING)
        NodeGroup.objects.import_boot_images_accepted_clusters()
        expected_queues = [
            nodegroup.work_queue
            for nodegroup in accepted_nodegroups]
        actual_queues = [
            kwargs['queue']
            for args, kwargs in recorder.apply_async.call_args_list]
        self.assertItemsEqual(expected_queues, actual_queues)


def make_archive_url(name):
    """Create a fake archive URL."""
    return "http://%s.example.com/%s/" % (
        factory.make_name(name),
        factory.make_name('path'),
        )

    def test_refresh_workers_refreshes_accepted_cluster_controllers(self):
        self.patch(nodegroup_module, 'refresh_worker')
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        NodeGroup.objects.refresh_workers()
        nodegroup_module.refresh_worker.assert_called_once_with(nodegroup)

    def test_refresh_workers_skips_unaccepted_cluster_controllers(self):
        self.patch(nodegroup_module, 'refresh_worker')
        for status in map_enum(NODEGROUP_STATUS).values():
            if status != NODEGROUP_STATUS.ACCEPTED:
                factory.make_node_group(status=status)
        NodeGroup.objects.refresh_workers()
        self.assertEqual(0, nodegroup_module.refresh_worker.call_count)


class TestNodeGroup(MAASServerTestCase):

    resources = (
        ('celery', FixtureResource(CeleryFixture())),
        )

    def test_delete_cluster_with_nodes(self):
        nodegroup = factory.make_node_group()
        factory.make_node(nodegroup=nodegroup)
        nodegroup.delete()
        self.assertEqual(nodegroup.uuid, nodegroup.work_queue)
        self.assertFalse(NodeGroup.objects.filter(id=nodegroup.id).exists())

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

    def test_ensure_dhcp_key_creates_key(self):
        nodegroup = factory.make_node_group(dhcp_key='')
        nodegroup.ensure_dhcp_key()
        # Check that the dhcp_key is not empty and looks
        # valid.
        self.assertThat(nodegroup.dhcp_key, EndsWith("=="))
        # The key is persisted.
        self.assertThat(
            reload_object(nodegroup).dhcp_key, EndsWith("=="))

    def test_ensure_dhcp_key_preserves_existing_key(self):
        key = factory.make_name('dhcp-key')
        nodegroup = factory.make_node_group(dhcp_key=key)
        nodegroup.ensure_dhcp_key()
        self.assertEqual(key, nodegroup.dhcp_key)

    def test_ensure_dhcp_key_creates_different_keys(self):
        nodegroup1 = factory.make_node_group(dhcp_key='')
        nodegroup2 = factory.make_node_group(dhcp_key='')
        nodegroup1.ensure_dhcp_key()
        nodegroup2.ensure_dhcp_key()
        self.assertNotEqual(nodegroup1.dhcp_key, nodegroup2.dhcp_key)

    def test_import_boot_images_calls_script_with_proxy(self):
        recorder = self.patch(tasks, 'call_and_check')
        proxy = factory.make_name('proxy')
        Config.objects.set_config('http_proxy', proxy)
        nodegroup = factory.make_node_group()
        nodegroup.import_boot_images()
        args, kwargs = recorder.call_args
        env = kwargs['env']
        self.assertEqual(
            (proxy, proxy),
            (env.get('http_proxy'), env.get('https_proxy')))

    def test_import_boot_images_selects_archive_locations_from_config(self):
        recorder = self.patch(nodegroup_module, 'import_boot_images')
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)

        archives = {
            'main_archive': make_archive_url('main'),
            'ports_archive': make_archive_url('ports'),
            'cloud_images_archive': make_archive_url('cloud_images'),
        }
        for key, value in archives.items():
            Config.objects.set_config(key, value)

        nodegroup.import_boot_images()

        kwargs = recorder.apply_async.call_args[1]['kwargs']
        archive_options = {arg: kwargs.get(arg) for arg in archives}
        self.assertEqual(archives, archive_options)

    def test_import_boot_images_sent_to_nodegroup_queue(self):
        recorder = self.patch(nodegroup_module, 'import_boot_images', Mock())
        nodegroup = factory.make_node_group()
        proxy = factory.make_name('proxy')
        Config.objects.set_config('http_proxy', proxy)
        nodegroup.import_boot_images()
        args, kwargs = recorder.apply_async.call_args
        self.assertEqual(nodegroup.uuid, kwargs['queue'])
