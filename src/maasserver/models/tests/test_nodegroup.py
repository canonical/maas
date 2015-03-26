# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
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

from random import randint
from urlparse import urlparse

from apiclient.creds import convert_string_to_tuple
from django.db.models.signals import post_save
import django.dispatch
from maasserver.bootresources import get_simplestream_endpoint
from maasserver.enum import (
    NODEGROUP_STATE,
    NODEGROUP_STATUS,
    NODEGROUP_STATUS_CHOICES,
    NODEGROUPINTERFACE_MANAGEMENT,
)
from maasserver.models import (
    Config,
    NodeGroup,
    nodegroup as nodegroup_module,
)
from maasserver.rpc.testing.fixtures import MockLiveRegionToClusterRPCFixture
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.worker_user import get_worker_user
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from mock import (
    ANY,
    call,
    Mock,
    sentinel,
)
from provisioningserver.dhcp.omshell import generate_omapi_key
from provisioningserver.rpc.cluster import (
    AddESXi,
    AddSeaMicro15k,
    AddVirsh,
    AddVsphere,
    EnlistNodesFromMicrosoftOCS,
    EnlistNodesFromMSCM,
    EnlistNodesFromUCSM,
    ImportBootImages,
)
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.utils.enum import map_enum
from testtools.matchers import (
    EndsWith,
    Equals,
    GreaterThan,
    IsInstance,
)
from twisted.internet import defer


class TestNodeGroupManager(MAASServerTestCase):

    def test_new_creates_nodegroup(self):
        name = factory.make_name('nodegroup')
        uuid = factory.make_name('uuid')
        nodegroup = NodeGroup.objects.new(name, uuid)
        nodegroup = reload_object(nodegroup)
        self.assertEqual(name, nodegroup.name)

    def test_new_assigns_token_and_key_for_worker_user(self):
        nodegroup = NodeGroup.objects.new(
            factory.make_name('nodegroup'), factory.make_name('uuid'),
            factory.make_ipv4_address())
        self.assertIsNotNone(nodegroup.api_token)
        self.assertIsNotNone(nodegroup.api_key)
        self.assertEqual(get_worker_user(), nodegroup.api_token.user)
        self.assertEqual(nodegroup.api_key, nodegroup.api_token.key)

    def test_new_creates_nodegroup_with_empty_dhcp_key(self):
        nodegroup = NodeGroup.objects.new(
            factory.make_name('nodegroup'), factory.make_name('uuid'),
            factory.make_ipv4_address())
        self.assertEqual('', nodegroup.dhcp_key)

    def test_new_stores_dhcp_key_on_nodegroup(self):
        key = generate_omapi_key()
        nodegroup = NodeGroup.objects.new(
            factory.make_name('nodegroup'), factory.make_name('uuid'),
            factory.make_ipv4_address(),
            dhcp_key=key)
        self.assertEqual(key, nodegroup.dhcp_key)

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
            factory.make_ipv4_address())
        NodeGroup.objects.new(
            factory.make_name('nodegroup'), factory.make_name('uuid'),
            factory.make_ipv4_address())
        self.assertEqual(first_nodegroup, NodeGroup.objects.ensure_master())

    def test_ensure_master_preserves_existing_attributes(self):
        master = NodeGroup.objects.ensure_master()
        key = factory.make_string()
        master.dhcp_key = key
        master.save()
        self.assertEqual(key, NodeGroup.objects.ensure_master().dhcp_key)

    def test_ensure_master_creates_accepted_nodegroup(self):
        master = NodeGroup.objects.ensure_master()
        self.assertEqual(NODEGROUP_STATUS.ACCEPTED, master.status)

    def test_get_by_natural_key_looks_up_by_uuid(self):
        nodegroup = factory.make_NodeGroup()
        self.assertEqual(
            nodegroup,
            NodeGroup.objects.get_by_natural_key(nodegroup.uuid))

    def test_get_by_natural_key_will_not_return_other_nodegroup(self):
        factory.make_NodeGroup()
        self.assertRaises(
            NodeGroup.DoesNotExist,
            NodeGroup.objects.get_by_natural_key,
            factory.make_name("nonexistent-nodegroup"))

    def test__mass_change_status_changes_statuses(self):
        old_status = factory.pick_enum(NODEGROUP_STATUS)
        nodegroup1 = factory.make_NodeGroup(status=old_status)
        nodegroup2 = factory.make_NodeGroup(status=old_status)
        new_status = factory.pick_enum(NODEGROUP_STATUS, but_not=[old_status])
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
        old_status = factory.pick_enum(NODEGROUP_STATUS)
        nodegroup = factory.make_NodeGroup(status=old_status)
        recorder = Mock()

        def post_save_NodeGroup(sender, instance, created, **kwargs):
            recorder(instance)

        django.dispatch.Signal.connect(
            post_save, post_save_NodeGroup, sender=NodeGroup)
        self.addCleanup(
            django.dispatch.Signal.disconnect, post_save,
            receiver=post_save_NodeGroup, sender=NodeGroup)
        NodeGroup.objects._mass_change_status(
            old_status, factory.pick_enum(NODEGROUP_STATUS))
        self.assertEqual(
            [call(nodegroup)], recorder.call_args_list)

    def test_reject_all_pending_rejects_nodegroups(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.PENDING)
        changed = NodeGroup.objects.reject_all_pending()
        self.assertEqual(
            (NODEGROUP_STATUS.REJECTED, 1),
            (reload_object(nodegroup).status, changed))

    def test_reject_all_pending_does_not_change_others(self):
        unaffected_status = factory.pick_enum(
            NODEGROUP_STATUS, but_not=[NODEGROUP_STATUS.PENDING])
        nodegroup = factory.make_NodeGroup(status=unaffected_status)
        changed_count = NodeGroup.objects.reject_all_pending()
        self.assertEqual(
            (unaffected_status, 0),
            (reload_object(nodegroup).status, changed_count))

    def test_accept_all_pending_accepts_nodegroups(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.PENDING)
        changed = NodeGroup.objects.accept_all_pending()
        self.assertEqual(
            (NODEGROUP_STATUS.ACCEPTED, 1),
            (reload_object(nodegroup).status, changed))

    def test_accept_all_pending_does_not_change_others(self):
        unaffected_status = factory.pick_enum(
            NODEGROUP_STATUS, but_not=[NODEGROUP_STATUS.PENDING])
        nodegroup = factory.make_NodeGroup(status=unaffected_status)
        changed_count = NodeGroup.objects.accept_all_pending()
        self.assertEqual(
            (unaffected_status, 0),
            (reload_object(nodegroup).status, changed_count))

    def test_import_boot_images_on_accepted_clusters_calls_getClientFor(self):
        mock_getClientFor = self.patch(nodegroup_module, 'getClientFor')
        accepted_nodegroups = [
            factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED),
            factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED),
        ]
        factory.make_NodeGroup(status=NODEGROUP_STATUS.REJECTED)
        factory.make_NodeGroup(status=NODEGROUP_STATUS.PENDING)
        NodeGroup.objects.import_boot_images_on_accepted_clusters()
        expected_uuids = [
            nodegroup.uuid
            for nodegroup in accepted_nodegroups
            ]
        called_uuids = [
            client_call[0][0]
            for client_call in mock_getClientFor.call_args_list
            ]
        self.assertItemsEqual(expected_uuids, called_uuids)

    def test_all_accepted_only_includes_accepted_nodegroups(self):
        nodegroups = {
            status: factory.make_NodeGroup(status=status)
            for status, _ in NODEGROUP_STATUS_CHOICES
        }
        self.assertItemsEqual(
            [nodegroups[NODEGROUP_STATUS.ACCEPTED]],
            NodeGroup.objects.all_accepted())


class TestNodeGroup(MAASServerTestCase):

    def test_delete_cluster_with_nodes(self):
        nodegroup = factory.make_NodeGroup()
        factory.make_Node(nodegroup=nodegroup)
        nodegroup.delete()
        self.assertEqual(nodegroup.uuid, nodegroup.work_queue)
        self.assertFalse(NodeGroup.objects.filter(id=nodegroup.id).exists())

    def test_work_queue_returns_uuid(self):
        nodegroup = factory.make_NodeGroup()
        self.assertEqual(nodegroup.uuid, nodegroup.work_queue)

    def test_manages_dns_returns_True_if_managing_DNS(self):
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        self.assertTrue(nodegroup.manages_dns())

    def test_manages_dns_returns_False_if_not_accepted(self):
        nodegroups = [
            factory.make_NodeGroup(
                status=status,
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
            for status in map_enum(NODEGROUP_STATUS).values()
            ]
        self.assertEqual(
            {
                NODEGROUP_STATUS.PENDING: False,
                NODEGROUP_STATUS.ACCEPTED: True,
                NODEGROUP_STATUS.REJECTED: False,
            },
            {
                nodegroup.status: nodegroup.manages_dns()
                for nodegroup in nodegroups
            })

    def test_manages_dns_returns_False_if_no_interface_manages_DNS(self):
        nodegroups = {
            management: factory.make_NodeGroup(
                status=NODEGROUP_STATUS.ACCEPTED, management=management)
            for management in map_enum(NODEGROUPINTERFACE_MANAGEMENT).values()
            }
        self.assertEqual(
            {
                NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED: False,
                NODEGROUPINTERFACE_MANAGEMENT.DHCP: False,
                NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS: True,
            },
            {
                management: nodegroup.manages_dns()
                for management, nodegroup in nodegroups.items()
            })

    def test_manages_dns_returns_False_if_nodegroup_has_no_interfaces(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)
        nodegroup.nodegroupinterface_set.all().delete()
        self.assertFalse(nodegroup.manages_dns())

    def test_manages_dhcp_returns_True_if_managing_DHCP(self):
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        self.assertTrue(nodegroup.manages_dhcp())

    def test_manages_dhcp_returns_True_if_managing_DHCP_and_DNS(self):
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        self.assertTrue(nodegroup.manages_dhcp())

    def test_manages_dhcp_returns_False_if_not_accepted(self):
        nodegroups = [
            factory.make_NodeGroup(
                status=status,
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
            for status in map_enum(NODEGROUP_STATUS).values()
            ]
        self.assertEqual(
            {
                NODEGROUP_STATUS.PENDING: False,
                NODEGROUP_STATUS.ACCEPTED: True,
                NODEGROUP_STATUS.REJECTED: False,
            },
            {
                nodegroup.status: nodegroup.manages_dhcp()
                for nodegroup in nodegroups
            })

    def test_manages_dhcp_returns_False_if_no_interface_manages_DHCP(self):
        nodegroups = {
            management: factory.make_NodeGroup(
                status=NODEGROUP_STATUS.ACCEPTED, management=management)
            for management in map_enum(NODEGROUPINTERFACE_MANAGEMENT).values()
            }
        self.assertEqual(
            {
                NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED: False,
                NODEGROUPINTERFACE_MANAGEMENT.DHCP: True,
                NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS: True,
            },
            {
                management: nodegroup.manages_dhcp()
                for management, nodegroup in nodegroups.items()
            })

    def test_get_managed_interfaces_returns_list(self):
        nodegroup = factory.make_NodeGroup()
        self.assertIsInstance(nodegroup.get_managed_interfaces(), list)

    def test_get_managed_interfaces_returns_dhcp_managed_interfaces(self):
        nodegroup = factory.make_NodeGroup(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        self.assertEqual(
            set(nodegroup.nodegroupinterface_set.all()),
            set(nodegroup.get_managed_interfaces()))

    def test_get_managed_interfaces_returns_dns_managed_interfaces(self):
        nodegroup = factory.make_NodeGroup(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        self.assertEqual(
            set(nodegroup.nodegroupinterface_set.all()),
            set(nodegroup.get_managed_interfaces()))

    def test_get_managed_interfaces_ignores_unmanaged_interfaces(self):
        nodegroup = factory.make_NodeGroup(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        self.assertEqual([], nodegroup.get_managed_interfaces())

    def test_get_managed_interfaces_returns_empty_list_if_none_managed(self):
        nodegroup = factory.make_NodeGroup(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        managed_interfaces = nodegroup.get_managed_interfaces()
        self.assertIsInstance(managed_interfaces, list)
        self.assertEqual([], managed_interfaces)

    def test_get_managed_interface_returns_empty_list_if_no_interface(self):
        nodegroup = factory.make_NodeGroup(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        nodegroup.nodegroupinterface_set.all().delete()
        self.assertEqual([], nodegroup.get_managed_interfaces())

    def test_accept_node_changes_status(self):
        nodegroup = factory.make_NodeGroup(
            status=factory.pick_enum(NODEGROUP_STATUS))
        nodegroup.accept()
        self.assertEqual(nodegroup.status, NODEGROUP_STATUS.ACCEPTED)

    def test_reject_node_changes_status(self):
        nodegroup = factory.make_NodeGroup(
            status=factory.pick_enum(NODEGROUP_STATUS))
        nodegroup.reject()
        self.assertEqual(nodegroup.status, NODEGROUP_STATUS.REJECTED)

    def test_ensure_dhcp_key_creates_key(self):
        nodegroup = factory.make_NodeGroup(dhcp_key='')
        nodegroup.ensure_dhcp_key()
        # Check that the dhcp_key is not empty and looks
        # valid.
        self.assertThat(nodegroup.dhcp_key, EndsWith("=="))
        # The key is persisted.
        self.assertThat(
            reload_object(nodegroup).dhcp_key, EndsWith("=="))

    def test_ensure_dhcp_key_preserves_existing_key(self):
        key = factory.make_name('dhcp-key')
        nodegroup = factory.make_NodeGroup(dhcp_key=key)
        nodegroup.ensure_dhcp_key()
        self.assertEqual(key, nodegroup.dhcp_key)

    def test_ensure_dhcp_key_creates_different_keys(self):
        nodegroup1 = factory.make_NodeGroup(dhcp_key='')
        nodegroup2 = factory.make_NodeGroup(dhcp_key='')
        nodegroup1.ensure_dhcp_key()
        nodegroup2.ensure_dhcp_key()
        self.assertNotEqual(nodegroup1.dhcp_key, nodegroup2.dhcp_key)

    def test_import_boot_images_calls_getClientFor_with_uuid(self):
        mock_getClientFor = self.patch(nodegroup_module, 'getClientFor')
        nodegroup = factory.make_NodeGroup()
        nodegroup.import_boot_images()
        self.assertThat(
            mock_getClientFor, MockCalledOnceWith(nodegroup.uuid, timeout=1))

    def test_import_boot_images_calls_client_with_resource_endpoint(self):
        proxy = 'http://%s.example.com' % factory.make_name('proxy')
        Config.objects.set_config('http_proxy', proxy)
        sources = [get_simplestream_endpoint()]
        fake_client = Mock()
        mock_getClientFor = self.patch(nodegroup_module, 'getClientFor')
        mock_getClientFor.return_value = fake_client
        nodegroup = factory.make_NodeGroup()
        nodegroup.import_boot_images()
        self.assertThat(
            fake_client,
            MockCalledOnceWith(
                ImportBootImages, sources=sources,
                http_proxy=urlparse(proxy), https_proxy=urlparse(proxy)))

    def test_import_boot_images_does_nothing_if_no_connection_to_cluster(self):
        mock_getClientFor = self.patch(nodegroup_module, 'getClientFor')
        mock_getClientFor.side_effect = NoConnectionsAvailable()
        mock_get_simplestreams_endpoint = self.patch(
            nodegroup_module, 'get_simplestream_endpoint')
        nodegroup = factory.make_NodeGroup()
        nodegroup.import_boot_images()
        self.assertThat(mock_get_simplestreams_endpoint, MockNotCalled())

    def test_import_boot_images_end_to_end(self):
        proxy = 'http://%s.example.com' % factory.make_name('proxy')
        Config.objects.set_config('http_proxy', proxy)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)

        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(nodegroup, ImportBootImages)
        protocol.ImportBootImages.return_value = defer.succeed({})

        nodegroup.import_boot_images().wait(10)

        self.assertThat(
            protocol.ImportBootImages,
            MockCalledOnceWith(
                ANY, sources=[get_simplestream_endpoint()],
                http_proxy=urlparse(proxy), https_proxy=urlparse(proxy)))

    def test_is_connected_returns_true_if_connection(self):
        mock_getClientFor = self.patch(nodegroup_module, 'getClientFor')
        mock_getClientFor.return_value = sentinel
        nodegroup = factory.make_NodeGroup()
        connected = nodegroup.is_connected()
        self.assertThat(
            mock_getClientFor, MockCalledOnceWith(nodegroup.uuid, timeout=0))
        self.assertTrue(connected)

    def test_is_connected_returns_true_if_no_connection(self):
        mock_getClientFor = self.patch(nodegroup_module, 'getClientFor')
        mock_getClientFor.side_effect = NoConnectionsAvailable
        nodegroup = factory.make_NodeGroup()
        connected = nodegroup.is_connected()
        self.assertThat(
            mock_getClientFor, MockCalledOnceWith(nodegroup.uuid, timeout=0))
        self.assertFalse(connected)

    def test_get_state_returns_disconnected_if_no_connection(self):
        mock_get_boot_images = self.patch(nodegroup_module, 'get_boot_images')
        mock_get_boot_images.side_effect = NoConnectionsAvailable
        nodegroup = factory.make_NodeGroup()
        self.assertEqual(NODEGROUP_STATE.DISCONNECTED, nodegroup.get_state())

    def test_get_state_returns_disconnected_if_is_importing_errors(self):
        self.patch(nodegroup_module, 'get_boot_images')
        mock_boot_resources = self.patch(nodegroup_module, 'BootResource')
        mock_boot_resources.objects.boot_images_are_in_sync.return_value = (
            False)
        mock_is_import_boot_images_running = self.patch(
            nodegroup_module, 'is_import_boot_images_running_for')
        mock_is_import_boot_images_running.side_effect = NoConnectionsAvailable
        nodegroup = factory.make_NodeGroup()
        self.assertEqual(NODEGROUP_STATE.DISCONNECTED, nodegroup.get_state())

    def test_get_state_returns_synced_if_images_match_resources(self):
        self.patch(nodegroup_module, 'get_boot_images')
        mock_boot_resources = self.patch(nodegroup_module, 'BootResource')
        mock_boot_resources.objects.boot_images_are_in_sync.return_value = (
            True)
        nodegroup = factory.make_NodeGroup()
        self.assertEqual(NODEGROUP_STATE.SYNCED, nodegroup.get_state())

    def test_get_state_returns_out_of_sync_if_not_syncing(self):
        self.patch(nodegroup_module, 'get_boot_images')
        mock_boot_resources = self.patch(nodegroup_module, 'BootResource')
        mock_boot_resources.objects.boot_images_are_in_sync.return_value = (
            False)
        mock_is_import_boot_images_running = self.patch(
            nodegroup_module, 'is_import_boot_images_running_for')
        mock_is_import_boot_images_running.return_value = False
        nodegroup = factory.make_NodeGroup()
        self.assertEqual(NODEGROUP_STATE.OUT_OF_SYNC, nodegroup.get_state())

    def test_get_state_returns_syncing_if_currently_syncing(self):
        self.patch(nodegroup_module, 'get_boot_images')
        mock_boot_resources = self.patch(nodegroup_module, 'BootResource')
        mock_boot_resources.objects.boot_images_are_in_sync.return_value = (
            False)
        mock_is_import_boot_images_running = self.patch(
            nodegroup_module, 'is_import_boot_images_running_for')
        mock_is_import_boot_images_running.return_value = True
        nodegroup = factory.make_NodeGroup()
        self.assertEqual(NODEGROUP_STATE.SYNCING, nodegroup.get_state())

    def test_add_virsh_end_to_end(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)

        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(nodegroup, AddVirsh)
        protocol.AddVirsh.return_value = defer.succeed(
            {'system_id': factory.make_name('system-id')})

        user = factory.make_name('user')
        poweraddr = factory.make_name('poweraddr')
        password = factory.make_name('password')
        nodegroup.add_virsh(user, poweraddr, password, None, True).wait(10)

        self.expectThat(
            protocol.AddVirsh,
            MockCalledOnceWith(
                ANY, user=user, poweraddr=poweraddr,
                password=password, prefix_filter=None, accept_all=True))

    def test_add_virsh_calls_client_with_resource_endpoint(self):
        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        client = getClientFor.return_value
        nodegroup = factory.make_NodeGroup()

        user = factory.make_name('user')
        poweraddr = factory.make_name('poweraddr')
        password = factory.make_name('password')
        nodegroup.add_virsh(user, poweraddr, password, None, True)

        self.expectThat(
            client,
            MockCalledOnceWith(
                AddVirsh, user=user, poweraddr=poweraddr,
                password=password, prefix_filter=None, accept_all=True))

    def test_add_virsh_raises_if_no_connection_to_cluster(self):
        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        getClientFor.side_effect = NoConnectionsAvailable()
        nodegroup = factory.make_NodeGroup()

        user = factory.make_name('user')
        poweraddr = factory.make_name('poweraddr')
        password = factory.make_name('password')

        self.assertRaises(
            NoConnectionsAvailable, nodegroup.add_virsh, user,
            poweraddr, password, True)

    def test_add_vsphere_end_to_end(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)

        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(nodegroup, AddVsphere)
        protocol.AddVsphere.return_value = defer.succeed(
            {'system_id': factory.make_name('system-id')})

        user = factory.make_name('user')
        host = factory.make_ip_address()
        username = factory.make_username()
        password = factory.make_name('password')

        nodegroup.add_vsphere(
            user, host, username, password, protocol=None, port=None,
            prefix_filter=None, accept_all=True).wait(10)

        self.expectThat(
            protocol.AddVsphere,
            MockCalledOnceWith(
                ANY, user=user, host=host, username=username,
                password=password, protocol=None, port=None,
                prefix_filter=None, accept_all=True))

    def test_add_vsphere_calls_client_with_resource_endpoint(self):
        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        client = getClientFor.return_value
        nodegroup = factory.make_NodeGroup()

        user = factory.make_name('user')
        host = factory.make_ip_address()
        username = factory.make_username()
        password = factory.make_name('password')

        nodegroup.add_vsphere(
            user, host, username, password, protocol=None, port=None,
            prefix_filter=None, accept_all=True).wait(10)

        self.expectThat(
            client,
            MockCalledOnceWith(
                AddVsphere, user=user, host=host, username=username,
                password=password, protocol=None, port=None,
                prefix_filter=None, accept_all=True))

    def test_add_vsphere_raises_if_no_connection_to_cluster(self):
        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        getClientFor.side_effect = NoConnectionsAvailable()
        nodegroup = factory.make_NodeGroup()

        user = factory.make_name('user')
        host = factory.make_ip_address()
        username = factory.make_username()
        password = factory.make_name('password')

        self.assertRaises(
            NoConnectionsAvailable, nodegroup.add_vsphere, user, host,
            username, password, protocol=None, port=None,
            prefix_filter=None, accept_all=True)

    def test_add_esxi_end_to_end(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)

        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(nodegroup, AddESXi)
        protocol.AddESXi.return_value = defer.succeed(
            {'system_id': factory.make_name('system-id')})

        user = factory.make_name('user')
        poweraddr = factory.make_name('poweraddr')
        password = factory.make_name('password')
        nodegroup.add_esxi(user, poweraddr, password, None, True).wait(10)

        self.expectThat(
            protocol.AddESXi,
            MockCalledOnceWith(
                ANY, user=user, poweraddr=poweraddr,
                password=password, prefix_filter=None, accept_all=True))

    def test_add_esxi_calls_client_with_resource_endpoint(self):
        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        client = getClientFor.return_value
        nodegroup = factory.make_NodeGroup()

        user = factory.make_name('user')
        poweraddr = factory.make_name('poweraddr')
        password = factory.make_name('password')
        nodegroup.add_esxi(user, poweraddr, password, None, True)

        self.expectThat(
            client,
            MockCalledOnceWith(
                AddESXi, user=user, poweraddr=poweraddr,
                password=password, prefix_filter=None, accept_all=True))

    def test_add_esxi_raises_if_no_connection_to_cluster(self):
        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        getClientFor.side_effect = NoConnectionsAvailable()
        nodegroup = factory.make_NodeGroup()

        user = factory.make_name('user')
        poweraddr = factory.make_name('poweraddr')
        password = factory.make_name('password')

        self.assertRaises(
            NoConnectionsAvailable, nodegroup.add_esxi, user,
            poweraddr, password, True)

    def test_add_seamicro15k_end_to_end(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)

        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(nodegroup, AddSeaMicro15k)
        protocol.AddSeaMicro15k.return_value = defer.succeed({})

        user = factory.make_name('user')
        mac = factory.make_mac_address()
        username = factory.make_name('user')
        password = factory.make_name('password')
        power_control = factory.make_name('power_control')
        nodegroup.add_seamicro15k(
            user, mac, username, password, power_control, True).wait(10)

        self.expectThat(
            protocol.AddSeaMicro15k,
            MockCalledOnceWith(
                ANY, user=user, mac=mac, username=username,
                password=password, power_control=power_control,
                accept_all=True))

    def test_add_seamicro15k_calls_client_with_resource_endpoint(self):
        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        client = getClientFor.return_value
        nodegroup = factory.make_NodeGroup()

        user = factory.make_name('user')
        mac = factory.make_mac_address()
        username = factory.make_name('user')
        password = factory.make_name('password')
        power_control = factory.make_name('power_control')
        nodegroup.add_seamicro15k(
            user, mac, username, password, power_control, True)

        self.expectThat(
            client,
            MockCalledOnceWith(
                AddSeaMicro15k, user=user, mac=mac, username=username,
                password=password, power_control=power_control,
                accept_all=True))

    def test_add_seamicro15k_raises_if_no_connection_to_cluster(self):
        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        getClientFor.side_effect = NoConnectionsAvailable()
        nodegroup = factory.make_NodeGroup()

        user = factory.make_name('user')
        mac = factory.make_mac_address()
        username = factory.make_name('user')
        password = factory.make_name('password')
        power_control = factory.make_name('power_control')

        self.assertRaises(
            NoConnectionsAvailable, nodegroup.add_seamicro15k,
            user, mac, username, password, power_control, True)

    def test_enlist_nodes_from_mscm_end_to_end(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)

        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(nodegroup, EnlistNodesFromMSCM)
        protocol.EnlistNodesFromMSCM.return_value = defer.succeed({})

        user = factory.make_name('user')
        host = factory.make_name('host')
        username = factory.make_name('user')
        password = factory.make_name('password')
        nodegroup.enlist_nodes_from_mscm(
            user, host, username, password, True).wait(10)

        self.expectThat(
            protocol.EnlistNodesFromMSCM,
            MockCalledOnceWith(
                ANY, user=user, host=host,
                username=username, password=password, accept_all=True))

    def test_enlist_nodes_from_mscm_calls_client_with_resource_endpoint(self):
        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        client = getClientFor.return_value
        nodegroup = factory.make_NodeGroup()

        user = factory.make_name('user')
        host = factory.make_name('host')
        username = factory.make_name('user')
        password = factory.make_name('password')
        nodegroup.enlist_nodes_from_mscm(
            user, host, username, password, True).wait(10)

        self.expectThat(
            client,
            MockCalledOnceWith(
                EnlistNodesFromMSCM, user=user, host=host,
                username=username, password=password, accept_all=True))

    def test_enlist_nodes_from_mscm_raises_if_no_connection_to_cluster(self):
        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        getClientFor.side_effect = NoConnectionsAvailable()
        nodegroup = factory.make_NodeGroup()

        user = factory.make_name('user')
        host = factory.make_name('host')
        username = factory.make_name('user')
        password = factory.make_name('password')

        self.assertRaises(
            NoConnectionsAvailable, nodegroup.enlist_nodes_from_mscm,
            user, host, username, password, True)

    def test_enlist_nodes_from_ucsm_end_to_end(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)

        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(nodegroup, EnlistNodesFromUCSM)
        protocol.EnlistNodesFromUCSM.return_value = defer.succeed({})

        user = factory.make_name('user')
        url = factory.make_url()
        username = factory.make_name('user')
        password = factory.make_name('password')
        nodegroup.enlist_nodes_from_ucsm(
            user, url, username, password, True).wait(10)

        self.expectThat(
            protocol.EnlistNodesFromUCSM,
            MockCalledOnceWith(
                ANY, user=user, url=url,
                username=username, password=password, accept_all=True))

    def test_enlist_nodes_from_ucsm_calls_client_with_resource_endpoint(self):
        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        client = getClientFor.return_value
        nodegroup = factory.make_NodeGroup()

        user = factory.make_name('user')
        url = factory.make_url()
        username = factory.make_name('user')
        password = factory.make_name('password')
        nodegroup.enlist_nodes_from_ucsm(
            user, url, username, password, True).wait(10)

        self.expectThat(
            client,
            MockCalledOnceWith(
                EnlistNodesFromUCSM, user=user, url=url,
                username=username, password=password, accept_all=True))

    def test_enlist_nodes_from_ucsm_raises_if_no_connection_to_cluster(self):
        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        getClientFor.side_effect = NoConnectionsAvailable()
        nodegroup = factory.make_NodeGroup()

        user = factory.make_name('user')
        url = factory.make_url()
        username = factory.make_name('user')
        password = factory.make_name('password')

        self.assertRaises(
            NoConnectionsAvailable, nodegroup.enlist_nodes_from_ucsm,
            user, url, username, password, True)

    def test_enlist_nodes_from_msftocs_end_to_end(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)

        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(nodegroup, EnlistNodesFromMicrosoftOCS)
        protocol.EnlistNodesFromMicrosoftOCS.return_value = defer.succeed({})

        user = factory.make_name('user')
        ip = factory.make_ipv4_address()
        port = '%d' % randint(2000, 4000)
        username = factory.make_name('user')
        password = factory.make_name('password')
        nodegroup.enlist_nodes_from_msftocs(
            user, ip, port, username, password, True).wait(10)

        self.expectThat(
            protocol.EnlistNodesFromMicrosoftOCS,
            MockCalledOnceWith(
                ANY, user=user, ip=ip, port=port,
                username=username, password=password, accept_all=True))

    def test_enlist_nodes_from_msftocs_calls_client_with_res_endpoint(self):
        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        client = getClientFor.return_value
        nodegroup = factory.make_NodeGroup()

        user = factory.make_name('user')
        ip = factory.make_ipv4_address()
        port = randint(2000, 4000)
        username = factory.make_name('user')
        password = factory.make_name('password')
        nodegroup.enlist_nodes_from_msftocs(
            user, ip, port, username, password, True).wait(10)

        self.expectThat(
            client,
            MockCalledOnceWith(
                EnlistNodesFromMicrosoftOCS, user=user, ip=ip, port=port,
                username=username, password=password, accept_all=True))

    def test_enlist_nodes_from_msftocs_raises_if_no_conn_to_cluster(self):
        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        getClientFor.side_effect = NoConnectionsAvailable()
        nodegroup = factory.make_NodeGroup()

        user = factory.make_name('user')
        ip = factory.make_ipv4_address()
        port = randint(2000, 4000)
        username = factory.make_name('user')
        password = factory.make_name('password')

        self.assertRaises(
            NoConnectionsAvailable, nodegroup.enlist_nodes_from_msftocs,
            user, ip, port, username, password, True)

    def test_api_credentials(self):
        nodegroup = factory.make_NodeGroup()
        self.assertThat(nodegroup.api_credentials, IsInstance(unicode))
        consumer_key, token_key, token_secret = (
            convert_string_to_tuple(nodegroup.api_credentials))
        self.expectThat(consumer_key, Equals(nodegroup.api_token.consumer.key))
        self.expectThat(token_key, Equals(nodegroup.api_token.key))
        self.expectThat(token_secret, Equals(nodegroup.api_token.secret))
