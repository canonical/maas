# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver models."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from datetime import (
    datetime,
    timedelta,
    )
import random

import crochet
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
from django.db import transaction
from fixtures import LoggerFixture
from maasserver import (
    node_query,
    preseed as preseed_module,
    )
from maasserver.clusterrpc import power as power_module
from maasserver.clusterrpc.power_parameters import get_power_types
from maasserver.clusterrpc.testing.boot_images import make_rpc_boot_image
from maasserver.dns import config as dns_config
from maasserver.enum import (
    IPADDRESS_TYPE,
    NODE_BOOT,
    NODE_PERMISSION,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_STATUS_CHOICES_DICT,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    POWER_STATE,
    )
from maasserver.exceptions import (
    NodeStateViolation,
    StaticIPAddressTypeClash,
    StaticIPAddressUnavailable,
    )
from maasserver.fields import MAC
from maasserver.models import (
    Config,
    LicenseKey,
    MACAddress,
    Node,
    node as node_module,
    )
from maasserver.models.node import PowerInfo
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.user import create_auth_token
from maasserver.node_status import (
    get_failed_status,
    MONITORED_STATUSES,
    NODE_FAILURE_STATUS_TRANSITIONS,
    NODE_TRANSITIONS,
    )
from maasserver.rpc import monitors as monitors_module
from maasserver.rpc.testing.fixtures import (
    MockLiveRegionToClusterRPCFixture,
    RunningClusterRPCFixture,
    )
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
    )
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import ignore_unused
from maasserver.utils.orm import (
    post_commit,
    post_commit_hooks,
    )
from maastesting.djangotestcase import count_queries
from maastesting.matchers import (
    MockAnyCall,
    MockCalledOnceWith,
    MockNotCalled,
    )
from metadataserver.enum import RESULT_TYPE
from metadataserver.fields import Bin
from metadataserver.models import (
    NodeResult,
    NodeUserData,
    )
from metadataserver.user_data import (
    commissioning,
    disk_erasing,
    )
import mock
from mock import (
    ANY,
    sentinel,
    )
from netaddr import IPAddress
from provisioningserver.power.poweraction import UnknownPowerType
from provisioningserver.power_schema import JSON_POWER_TYPE_PARAMETERS
from provisioningserver.rpc import cluster as cluster_module
from provisioningserver.rpc.cluster import StartMonitors
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.power import QUERY_POWER_TYPES
from provisioningserver.rpc.testing import always_succeed_with
from provisioningserver.utils.enum import map_enum
from testtools import ExpectedException
from testtools.matchers import (
    Contains,
    Equals,
    HasLength,
    Is,
    IsInstance,
    MatchesStructure,
    Not,
    )
from twisted.internet import defer
from twisted.protocols import amp
from twisted.python.failure import Failure


def make_active_lease(nodegroup=None):
    """Create a `DHCPLease` on a managed `NodeGroupInterface`."""
    lease = factory.make_DHCPLease(nodegroup=nodegroup)
    factory.make_NodeGroupInterface(
        lease.nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
    return lease


class TestNode(MAASServerTestCase):

    def disable_node_query(self):
        self.addCleanup(node_query.enable)
        node_query.disable()

    def test_system_id(self):
        # The generated system_id looks good.
        node = factory.make_Node()
        self.assertThat(node.system_id, HasLength(41))
        self.assertTrue(node.system_id.startswith('node-'))

    def test_empty_architecture_rejected_for_installable_nodes(self):
        self.assertRaises(
            ValidationError,
            factory.make_Node, installable=True, architecture='')

    def test_empty_architecture_accepted_for_non_installable_nodes(self):
        node = factory.make_Node(installable=False, architecture='')
        self.assertThat(node, IsInstance(Node))

    def test_hostname_is_validated(self):
        bad_hostname = '-_?!@*-'
        self.assertRaises(
            ValidationError,
            factory.make_Node, hostname=bad_hostname)

    def test_work_queue_returns_nodegroup_uuid(self):
        nodegroup = factory.make_NodeGroup()
        node = factory.make_Node(nodegroup=nodegroup)
        self.assertEqual(nodegroup.uuid, node.work_queue)

    def test_display_status_shows_default_status(self):
        node = factory.make_Node()
        self.assertEqual(
            NODE_STATUS_CHOICES_DICT[node.status],
            node.display_status())

    def test_display_memory_returns_decimal_less_than_1024(self):
        node = factory.make_Node(memory=512)
        self.assertEqual('0.5', node.display_memory())

    def test_display_memory_returns_value_divided_by_1024(self):
        node = factory.make_Node(memory=2048)
        self.assertEqual('2', node.display_memory())

    def test_physicalblockdevice_set_returns_physicalblockdevices(self):
        node = factory.make_Node()
        device = factory.make_PhysicalBlockDevice(node=node)
        factory.make_BlockDevice(node=node)
        factory.make_PhysicalBlockDevice()
        self.assertItemsEqual([device], node.physicalblockdevice_set.all())

    def test_storage_returns_size_of_physicalblockdevices_in_mb(self):
        node = factory.make_Node()
        for _ in range(3):
            factory.make_PhysicalBlockDevice(node=node, size=50 * (1000 ** 2))
        self.assertEqual(50 * 3, node.storage)

    def test_display_storage_returns_decimal_less_than_1000(self):
        node = factory.make_Node()
        factory.make_PhysicalBlockDevice(node=node, size=500 * (1000 ** 2))
        self.assertEqual('0.5', node.display_storage())

    def test_display_storage_returns_value_divided_by_1000(self):
        node = factory.make_Node()
        factory.make_PhysicalBlockDevice(node=node, size=2000 * (1000 ** 2))
        self.assertEqual('2', node.display_storage())

    def test_add_node_with_token(self):
        user = factory.make_User()
        token = create_auth_token(user)
        node = factory.make_Node(token=token)
        self.assertEqual(token, node.token)

    def test_add_mac_address(self):
        mac = factory.make_mac_address()
        node = factory.make_Node()
        node.add_mac_address(mac)
        macs = MACAddress.objects.filter(node=node, mac_address=mac).count()
        self.assertEqual(1, macs)

    def test_add_mac_address_sets_cluster_interface(self):
        # If a DHCPLease exists for this mac, ensure the
        # cluster_interface is set on the basis of that lease.
        cluster = factory.make_NodeGroup()
        cluster_interface = factory.make_NodeGroupInterface(nodegroup=cluster)
        ip_in_range = cluster_interface.static_ip_range_low
        mac_address = factory.make_mac_address()
        factory.make_DHCPLease(
            mac=mac_address, ip=ip_in_range, nodegroup=cluster)
        node = factory.make_Node(nodegroup=cluster)

        node.add_mac_address(mac_address)
        self.assertEqual(
            cluster_interface, node.get_primary_mac().cluster_interface)

    def test_remove_mac_address(self):
        mac = factory.make_mac_address()
        node = factory.make_Node()
        node.add_mac_address(mac)
        node.remove_mac_address(mac)
        self.assertItemsEqual(
            [],
            MACAddress.objects.filter(node=node, mac_address=mac))

    def test_get_primary_mac_returns_mac_address(self):
        node = factory.make_Node()
        mac = factory.make_mac_address()
        node.add_mac_address(mac)
        self.assertEqual(mac, node.get_primary_mac().mac_address)

    def test_get_primary_mac_returns_None_if_node_has_no_mac(self):
        node = factory.make_Node()
        self.assertIsNone(node.get_primary_mac())

    def test_get_primary_mac_returns_oldest_mac(self):
        node = factory.make_Node()
        macs = [factory.make_mac_address() for counter in range(3)]
        offset = timedelta(0)
        for mac in macs:
            mac_address = node.add_mac_address(mac)
            mac_address.created += offset
            mac_address.save()
            offset += timedelta(1)
        self.assertEqual(macs[0], node.get_primary_mac().mac_address)

    def test_get_osystem_returns_default_osystem(self):
        node = factory.make_Node(osystem='')
        osystem = Config.objects.get_config('default_osystem')
        self.assertEqual(osystem, node.get_osystem())

    def test_get_distro_series_returns_default_series(self):
        node = factory.make_Node(distro_series='')
        series = Config.objects.get_config('default_distro_series')
        self.assertEqual(series, node.get_distro_series())

    def test_get_effective_license_key_returns_node_value(self):
        license_key = factory.make_name('license_key')
        node = factory.make_Node(license_key=license_key)
        self.assertEqual(license_key, node.get_effective_license_key())

    def test_get_effective_license_key_returns_blank(self):
        node = factory.make_Node()
        self.assertEqual('', node.get_effective_license_key())

    def test_get_effective_license_key_returns_global(self):
        license_key = factory.make_name('license_key')
        osystem = factory.make_name('os')
        series = factory.make_name('series')
        LicenseKey.objects.create(
            osystem=osystem, distro_series=series, license_key=license_key)
        node = factory.make_Node(osystem=osystem, distro_series=series)
        self.assertEqual(license_key, node.get_effective_license_key())

    def test_delete_node_deletes_managed_node_when_changed_to_unmanaged(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        factory.make_DHCPLease(
            nodegroup=node.nodegroup,
            mac=node.macaddress_set.all().first().mac_address)
        interface = node.nodegroup.nodegroupinterface_set.all().first()
        interface.management = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
        interface.save()
        self.useFixture(RunningClusterRPCFixture())
        node.delete()
        self.assertItemsEqual([], Node.objects.all())

    def test_delete_node_deletes_related_mac(self):
        node = factory.make_Node()
        mac = node.add_mac_address('AA:BB:CC:DD:EE:FF')
        node.delete()
        self.assertRaises(
            MACAddress.DoesNotExist, MACAddress.objects.get, id=mac.id)

    def test_can_delete_allocated_node(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        system_id = node.system_id
        node.delete()
        self.assertItemsEqual([], Node.objects.filter(system_id=system_id))

    def test_delete_node_also_deletes_related_static_IPs(self):
        self.patch_autospec(node_module, "remove_host_maps")
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        primary_mac = node.get_primary_mac()
        random_alloc_type = factory.pick_enum(
            IPADDRESS_TYPE, but_not=[IPADDRESS_TYPE.USER_RESERVED])
        primary_mac.claim_static_ips(alloc_type=random_alloc_type)
        node.delete()
        self.assertItemsEqual([], StaticIPAddress.objects.all())

    def test_delete_node_also_deletes_static_dhcp_maps(self):
        remove_host_maps = self.patch_autospec(
            node_module, "remove_host_maps")
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        primary_mac = node.get_primary_mac()
        static_ip_addresses = set(
            static_ip_address.ip for static_ip_address in
            primary_mac.claim_static_ips(alloc_type=IPADDRESS_TYPE.STICKY))
        node.delete()
        self.assertThat(
            remove_host_maps, MockCalledOnceWith(
                {node.nodegroup: static_ip_addresses}))

    def test_delete_node_also_deletes_dhcp_host_map(self):
        remove_host_maps = self.patch_autospec(
            node_module, "remove_host_maps")
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        lease = factory.make_DHCPLease(
            nodegroup=node.nodegroup,
            mac=node.macaddress_set.all().first().mac_address)
        node.delete()
        self.assertThat(
            remove_host_maps, MockCalledOnceWith(
                {node.nodegroup: {lease.ip}}))

    def test_delete_node_removes_multiple_host_maps(self):
        remove_host_maps = self.patch_autospec(
            node_module, "remove_host_maps")
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        mac = node.add_mac_address('AA:BB:CC:DD:EE:FF')
        mac.cluster_interface = (
            node.nodegroup.nodegroupinterface_set.all().first())
        mac.save()
        lease1 = factory.make_DHCPLease(
            nodegroup=node.nodegroup,
            mac=node.macaddress_set.all().first().mac_address)
        lease2 = factory.make_DHCPLease(
            nodegroup=node.nodegroup,
            mac=mac.mac_address)
        node.delete()
        self.assertThat(
            remove_host_maps, MockCalledOnceWith(
                {node.nodegroup: {lease1.ip, lease2.ip}},
            ))

    def test_set_random_hostname_set_hostname(self):
        # Blank out enlistment_domain.
        Config.objects.set_config("enlistment_domain", '')
        node = factory.make_Node()
        original_hostname = node.hostname
        node.set_random_hostname()
        self.assertNotEqual(original_hostname, node.hostname)
        self.assertNotEqual("", node.hostname)

    def test_set_random_hostname_checks_hostname_existence(self):
        Config.objects.set_config("enlistment_domain", '')
        existing_node = factory.make_Node(hostname='hostname')

        hostnames = [existing_node.hostname, "new-hostname"]
        self.patch(
            node_module, "gen_candidate_names",
            lambda: iter(hostnames))

        node = factory.make_Node()
        node.set_random_hostname()
        self.assertEqual('new-hostname', node.hostname)

    def test_get_effective_power_type_raises_if_not_set(self):
        node = factory.make_Node(power_type='')
        self.assertRaises(
            UnknownPowerType, node.get_effective_power_type)

    def test_get_effective_power_type_reads_node_field(self):
        power_types = list(get_power_types().keys())  # Python3 proof.
        nodes = [
            factory.make_Node(power_type=power_type)
            for power_type in power_types]
        self.assertEqual(
            power_types, [node.get_effective_power_type() for node in nodes])

    def test_power_parameters_are_stored(self):
        node = factory.make_Node(power_type='')
        parameters = dict(user="tarquin", address="10.1.2.3")
        node.power_parameters = parameters
        node.save()
        node = reload_object(node)
        self.assertEqual(parameters, node.power_parameters)

    def test_power_parameters_default(self):
        node = factory.make_Node(power_type='')
        self.assertEqual('', node.power_parameters)

    def test_get_effective_power_parameters_returns_power_parameters(self):
        params = {'test_parameter': factory.make_string()}
        node = factory.make_Node(power_parameters=params)
        self.assertEqual(
            params['test_parameter'],
            node.get_effective_power_parameters()['test_parameter'])

    def test_get_effective_power_parameters_adds_system_id(self):
        node = factory.make_Node()
        self.assertEqual(
            node.system_id,
            node.get_effective_power_parameters()['system_id'])

    def test_get_effective_power_parameters_adds_mac_if_no_params_set(self):
        node = factory.make_Node()
        mac = factory.make_mac_address()
        node.add_mac_address(mac)
        self.assertEqual(
            mac, node.get_effective_power_parameters()['mac_address'])

    def test_get_effective_power_parameters_adds_no_mac_if_params_set(self):
        node = factory.make_Node(power_parameters={'foo': 'bar'})
        mac = factory.make_mac_address()
        node.add_mac_address(mac)
        self.assertNotIn('mac', node.get_effective_power_parameters())

    def test_get_effective_power_parameters_adds_empty_power_off_mode(self):
        node = factory.make_Node()
        params = node.get_effective_power_parameters()
        self.assertEqual("", params["power_off_mode"])

    def test_get_effective_power_type_no_default_power_address_if_not_virsh(
            self):
        node = factory.make_Node(power_type="ether_wake")
        params = node.get_effective_power_parameters()
        self.assertEqual("", params["power_address"])

    def test_get_effective_power_type_defaults_power_address_if_virsh(self):
        node = factory.make_Node(power_type="virsh")
        params = node.get_effective_power_parameters()
        self.assertEqual("qemu://localhost/system", params["power_address"])

    def test_get_effective_power_parameters_sets_local_boot_mode(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        params = node.get_effective_power_parameters()
        self.assertEqual("local", params['boot_mode'])

    def test_get_effective_power_parameters_sets_pxe_boot_mode(self):
        status = factory.pick_enum(NODE_STATUS, but_not=[NODE_STATUS.DEPLOYED])
        node = factory.make_Node(status=status)
        params = node.get_effective_power_parameters()
        self.assertEqual("pxe", params['boot_mode'])

    def test_get_effective_power_info_is_False_for_unset_power_type(self):
        node = factory.make_Node(power_type="")
        self.assertEqual(
            (False, False, False, None, None),
            node.get_effective_power_info())

    def test_get_effective_power_info_is_True_for_set_power_type(self):
        node = factory.make_Node(power_type=factory.make_name("pwr"))
        gepp = self.patch(node, "get_effective_power_parameters")
        gepp.return_value = sentinel.power_parameters
        self.assertEqual(
            PowerInfo(
                True, True, False, node.power_type, sentinel.power_parameters),
            node.get_effective_power_info())

    def test_get_effective_power_info_can_be_False_for_ether_wake(self):
        node = factory.make_Node(power_type="ether_wake")
        gepp = self.patch(node, "get_effective_power_parameters")
        # When there's no MAC address in the power parameters,
        # get_effective_power_info() says that this node's power cannot
        # be turned on. However, it does return the power parameters.
        # For ether_wake the power can never be turned off.
        gepp.return_value = {}
        self.assertEqual(
            (False, False, False, "ether_wake", {}),
            node.get_effective_power_info())

    def test_get_effective_power_info_can_be_True_for_ether_wake(self):
        node = factory.make_Node(power_type="ether_wake")
        gepp = self.patch(node, "get_effective_power_parameters")
        # When the MAC address is supplied it changes its mind: this
        # node's power can be turned on. For ether_wake the power can
        # never be turned off.
        gepp.return_value = {"mac_address": sentinel.mac_addr}
        self.assertEqual(
            (
                True, False, False, "ether_wake",
                {"mac_address": sentinel.mac_addr}
            ),
            node.get_effective_power_info())

    def test_get_effective_power_info_cant_be_queried(self):
        all_power_types = {
            power_type_details['name']
            for power_type_details in JSON_POWER_TYPE_PARAMETERS
        }
        uncontrolled_power_types = all_power_types.difference(
            QUERY_POWER_TYPES)
        power_type = random.choice(list(uncontrolled_power_types))
        node = factory.make_Node(power_type=power_type)
        gepp = self.patch(node, "get_effective_power_parameters")
        self.assertEqual(
            PowerInfo(
                True, power_type != 'ether_wake', False, power_type,
                gepp()),
            node.get_effective_power_info())

    def test_get_effective_power_info_can_be_queried(self):
        power_type = random.choice(QUERY_POWER_TYPES)
        node = factory.make_Node(power_type=power_type)
        gepp = self.patch(node, "get_effective_power_parameters")
        self.assertEqual(
            PowerInfo(
                True, power_type != 'ether_wake', True,
                power_type, gepp()),
            node.get_effective_power_info())

    def test_get_effective_power_info_returns_named_tuple(self):
        node = factory.make_Node(power_type="ether_wake")
        # Ensure that can_be_started and can_be_stopped have different
        # values by specifying a MAC address for ether_wake.
        gepp = self.patch(node, "get_effective_power_parameters")
        gepp.return_value = {"mac_address": sentinel.mac_addr}
        self.assertThat(
            node.get_effective_power_info(),
            MatchesStructure.byEquality(
                can_be_started=True,
                can_be_stopped=False,
                can_be_queried=False,
                power_type="ether_wake",
                power_parameters={
                    "mac_address": sentinel.mac_addr,
                },
            ),
        )

    def test_get_effective_kernel_options_with_nothing_set(self):
        node = factory.make_Node()
        self.assertEqual((None, None), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_sees_global_config(self):
        node = factory.make_Node()
        kernel_opts = factory.make_string()
        Config.objects.set_config('kernel_opts', kernel_opts)
        self.assertEqual(
            (None, kernel_opts), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_not_confused_by_None_opts(self):
        node = factory.make_Node()
        tag = factory.make_Tag()
        node.tags.add(tag)
        kernel_opts = factory.make_string()
        Config.objects.set_config('kernel_opts', kernel_opts)
        self.assertEqual(
            (None, kernel_opts), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_not_confused_by_empty_str_opts(self):
        node = factory.make_Node()
        tag = factory.make_Tag(kernel_opts="")
        node.tags.add(tag)
        kernel_opts = factory.make_string()
        Config.objects.set_config('kernel_opts', kernel_opts)
        self.assertEqual(
            (None, kernel_opts), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_multiple_tags_with_opts(self):
        # In this scenario:
        #     global   kernel_opts='fish-n-chips'
        #     tag_a    kernel_opts=null
        #     tag_b    kernel_opts=''
        #     tag_c    kernel_opts='bacon-n-eggs'
        # we require that 'bacon-n-eggs' is chosen as it is the first
        # tag with a valid kernel option.
        Config.objects.set_config('kernel_opts', 'fish-n-chips')
        node = factory.make_Node()
        node.tags.add(factory.make_Tag('tag_a'))
        node.tags.add(factory.make_Tag('tag_b', kernel_opts=''))
        tag_c = factory.make_Tag('tag_c', kernel_opts='bacon-n-eggs')
        node.tags.add(tag_c)

        self.assertEqual(
            (tag_c, 'bacon-n-eggs'), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_ignores_unassociated_tag_value(self):
        node = factory.make_Node()
        factory.make_Tag(kernel_opts=factory.make_string())
        self.assertEqual((None, None), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_uses_tag_value(self):
        node = factory.make_Node()
        tag = factory.make_Tag(kernel_opts=factory.make_string())
        node.tags.add(tag)
        self.assertEqual(
            (tag, tag.kernel_opts), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_tag_overrides_global(self):
        node = factory.make_Node()
        global_opts = factory.make_string()
        Config.objects.set_config('kernel_opts', global_opts)
        tag = factory.make_Tag(kernel_opts=factory.make_string())
        node.tags.add(tag)
        self.assertEqual(
            (tag, tag.kernel_opts), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_uses_first_real_tag_value(self):
        node = factory.make_Node()
        # Intentionally create them in reverse order, so the default 'db' order
        # doesn't work, and we have asserted that we sort them.
        tag3 = factory.make_Tag(
            factory.make_name('tag-03-'),
            kernel_opts=factory.make_string())
        tag2 = factory.make_Tag(
            factory.make_name('tag-02-'),
            kernel_opts=factory.make_string())
        tag1 = factory.make_Tag(factory.make_name('tag-01-'), kernel_opts=None)
        self.assertTrue(tag1.name < tag2.name)
        self.assertTrue(tag2.name < tag3.name)
        node.tags.add(tag1, tag2, tag3)
        self.assertEqual(
            (tag2, tag2.kernel_opts), node.get_effective_kernel_options())

    def test_acquire(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        user = factory.make_User()
        token = create_auth_token(user)
        agent_name = factory.make_name('agent-name')
        node.acquire(user, token, agent_name)
        self.assertEqual(
            (user, NODE_STATUS.ALLOCATED, agent_name),
            (node.owner, node.status, node.agent_name))

    def test_start_disk_erasing_changes_state_and_starts_node(self):
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=owner, agent_name=agent_name)
        node_start = self.patch(node, 'start')
        # Return a post-commit hook from Node.start().
        node_start.side_effect = lambda user, user_data: post_commit()
        with post_commit_hooks:
            node.start_disk_erasing(owner)
        self.expectThat(node.owner, Equals(owner))
        self.expectThat(node.status, Equals(NODE_STATUS.DISK_ERASING))
        self.expectThat(node.agent_name, Equals(agent_name))
        self.assertThat(
            node_start, MockCalledOnceWith(owner, user_data=ANY))

    def test_abort_disk_erasing_changes_state_and_stops_node(self):
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, owner=owner,
            agent_name=agent_name)
        node_stop = self.patch(node, 'stop')
        # Return a post-commit hook from Node.stop().
        node_stop.side_effect = lambda user: post_commit()
        self.patch(Node, "_set_status")

        with post_commit_hooks:
            node.abort_disk_erasing(owner)

        self.assertThat(node_stop, MockCalledOnceWith(owner))
        self.assertThat(node._set_status, MockCalledOnceWith(
            node.system_id, NODE_STATUS.FAILED_DISK_ERASING))

        # Neither the owner nor the agent has been changed.
        node = reload_object(node)
        self.expectThat(node.owner, Equals(owner))
        self.expectThat(node.agent_name, Equals(agent_name))

    def test_start_disk_erasing_reverts_to_sane_state_on_error(self):
        # If start_disk_erasing encounters an error when calling start(), it
        # will transition the node to a sane state. Failures encountered in
        # one call to start_disk_erasing() won't affect subsequent calls.
        self.disable_node_query()
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        generate_user_data = self.patch(disk_erasing, 'generate_user_data')
        node_start = self.patch(node, 'start')
        node_start.side_effect = factory.make_exception()

        try:
            with transaction.atomic():
                node.start_disk_erasing(admin)
        except node_start.side_effect.__class__:
            # We don't care about the error here, so suppress it. It
            # exists only to cause the transaction to abort.
            pass

        self.assertThat(
            node_start, MockCalledOnceWith(
                admin, user_data=generate_user_data.return_value))
        self.assertEqual(NODE_STATUS.FAILED_DISK_ERASING, node.status)

    def test_start_disk_erasing_logs_and_raises_errors_in_starting(self):
        self.disable_node_query()
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        maaslog = self.patch(node_module, 'maaslog')
        exception_type = factory.make_exception_type()
        exception = exception_type(factory.make_name())
        self.patch(node, 'start').side_effect = exception
        self.assertRaises(
            exception_type, node.start_disk_erasing, admin)
        self.assertEqual(NODE_STATUS.FAILED_DISK_ERASING, node.status)
        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "%s: Could not start node for disk erasure: %s",
                node.hostname, exception))

    def test_abort_operation_aborts_commissioning(self):
        agent_name = factory.make_name('agent-name')
        user = factory.make_admin()
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING,
            agent_name=agent_name)
        abort_commissioning = self.patch_autospec(node, 'abort_commissioning')
        node.abort_operation(user)
        self.assertThat(abort_commissioning, MockCalledOnceWith(user))

    def test_abort_operation_aborts_disk_erasing(self):
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, owner=owner,
            agent_name=agent_name)
        abort_disk_erasing = self.patch_autospec(node, 'abort_disk_erasing')
        node.abort_operation(owner)
        self.assertThat(abort_disk_erasing, MockCalledOnceWith(owner))

    def test_abort_operation_raises_exception_for_unsupported_state(self):
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.READY, owner=owner,
            agent_name=agent_name)
        self.assertRaises(NodeStateViolation, node.abort_operation, owner)

    def test_abort_disk_erasing_reverts_to_sane_state_on_error(self):
        # If abort_disk_erasing encounters an error when calling stop(), it
        # will transition the node to a sane state. Failures encountered in
        # one call to start_disk_erasing() won't affect subsequent calls.
        admin = factory.make_admin()
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, power_type="virsh")
        node_stop = self.patch(node, 'stop')
        node_stop.side_effect = factory.make_exception()

        try:
            with transaction.atomic():
                node.abort_disk_erasing(admin)
        except node_stop.side_effect.__class__:
            # We don't care about the error here, so suppress it. It
            # exists only to cause the transaction to abort.
            pass

        self.assertThat(node_stop, MockCalledOnceWith(admin))
        self.assertEqual(NODE_STATUS.DISK_ERASING, node.status)

    def test_abort_disk_erasing_logs_and_raises_errors_in_stopping(self):
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.DISK_ERASING)
        maaslog = self.patch(node_module, 'maaslog')
        exception_class = factory.make_exception_type()
        exception = exception_class(factory.make_name())
        self.patch(node, 'stop').side_effect = exception
        self.assertRaises(
            exception_class, node.abort_disk_erasing, admin)
        self.assertEqual(NODE_STATUS.DISK_ERASING, node.status)
        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "%s: Error when aborting disk erasure: %s",
                node.hostname, exception))

    def test_release_node_that_has_power_on_and_controlled_power_type(self):
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        # Use a "controlled" power type (i.e. a power type for which we
        # can query the status of the node).
        power_type = random.choice(QUERY_POWER_TYPES)
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=owner, agent_name=agent_name,
            power_type=power_type)
        self.patch(node, 'start_transition_monitor')
        self.patch(node_module, "post_commit_do")
        node.power_state = POWER_STATE.ON
        node.release()
        self.expectThat(
            node.start_transition_monitor,
            MockCalledOnceWith(node.get_releasing_time()))
        self.expectThat(node.status, Equals(NODE_STATUS.RELEASING))
        self.expectThat(node.owner, Equals(owner))
        self.expectThat(node.agent_name, Equals(''))
        self.expectThat(node.token, Is(None))
        self.expectThat(node.netboot, Is(True))
        self.expectThat(node.osystem, Equals(''))
        self.expectThat(node.distro_series, Equals(''))
        self.expectThat(node.license_key, Equals(''))

        expected_power_info = node.get_effective_power_info()
        expected_power_info.power_parameters['power_off_mode'] = "hard"
        self.expectThat(
            node_module.post_commit_do, MockCalledOnceWith(
                node_module.power_off_node, node.system_id, node.hostname,
                node.nodegroup.uuid, expected_power_info,
            ))

    def test_release_node_that_has_power_on_and_uncontrolled_power_type(self):
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        # Use an "uncontrolled" power type (i.e. a power type for which we
        # cannot query the status of the node).
        all_power_types = {
            power_type_details['name']
            for power_type_details in JSON_POWER_TYPE_PARAMETERS
        }
        uncontrolled_power_types = (
            all_power_types.difference(QUERY_POWER_TYPES))
        # ether_wake cannot be stopped, so discard this option.
        uncontrolled_power_types.discard("ether_wake")
        power_type = random.choice(list(uncontrolled_power_types))
        self.assertNotEqual("ether_wake", power_type)
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=owner, agent_name=agent_name,
            power_type=power_type)
        self.patch(node, 'start_transition_monitor')
        self.patch(node_module, "post_commit_do")
        node.power_state = POWER_STATE.ON
        node.release()
        self.expectThat(node.start_transition_monitor, MockNotCalled())
        self.expectThat(node.status, Equals(NODE_STATUS.READY))
        self.expectThat(node.owner, Is(None))
        self.expectThat(node.agent_name, Equals(''))
        self.expectThat(node.token, Is(None))
        self.expectThat(node.netboot, Is(True))
        self.expectThat(node.osystem, Equals(''))
        self.expectThat(node.distro_series, Equals(''))
        self.expectThat(node.license_key, Equals(''))

        expected_power_info = node.get_effective_power_info()
        expected_power_info.power_parameters['power_off_mode'] = "hard"
        self.expectThat(
            node_module.post_commit_do, MockCalledOnceWith(
                node_module.power_off_node, node.system_id, node.hostname,
                node.nodegroup.uuid, expected_power_info,
            ))

    def test_release_node_that_has_power_off(self):
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=owner, agent_name=agent_name)
        self.patch(node, 'start_transition_monitor')
        node.power_state = POWER_STATE.OFF
        node.release()
        self.expectThat(node.start_transition_monitor, MockNotCalled())
        self.expectThat(node.status, Equals(NODE_STATUS.READY))
        self.expectThat(node.owner, Is(None))
        self.expectThat(node.agent_name, Equals(''))
        self.expectThat(node.token, Is(None))
        self.expectThat(node.netboot, Is(True))
        self.expectThat(node.osystem, Equals(''))
        self.expectThat(node.distro_series, Equals(''))
        self.expectThat(node.license_key, Equals(''))

    def test_release_clears_installation_results(self):
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=owner, agent_name=agent_name)
        self.patch(node, 'start_transition_monitor')
        node_result = factory.make_NodeResult_for_installation(node=node)
        self.assertEquals(
            [node_result], list(NodeResult.objects.filter(
                node=node, result_type=RESULT_TYPE.INSTALLATION)))
        node.release()
        self.assertEquals(
            [], list(NodeResult.objects.filter(
                node=node, result_type=RESULT_TYPE.INSTALLATION)))

    def test_dynamic_ip_addresses_queries_leases(self):
        node = factory.make_Node()
        macs = [factory.make_MACAddress(node=node) for _ in range(2)]
        leases = [
            factory.make_DHCPLease(
                nodegroup=node.nodegroup, mac=mac.mac_address)
            for mac in macs]
        self.assertItemsEqual(
            [lease.ip for lease in leases], node.dynamic_ip_addresses())

    def test_dynamic_ip_addresses_uses_result_cache(self):
        # dynamic_ip_addresses has a specialized code path for the case where
        # the node group's set of DHCP leases is already cached in Django's
        # ORM.  This test exercises that code path.
        node = factory.make_Node()
        macs = [factory.make_MACAddress(node=node) for _ in range(2)]
        leases = [
            factory.make_DHCPLease(
                nodegroup=node.nodegroup, mac=mac.mac_address)
            for mac in macs]
        # Other nodes in the nodegroup have leases, but those are not
        # relevant here.
        factory.make_DHCPLease(nodegroup=node.nodegroup)

        # Don't address the node directly; address it through a query with
        # prefetched DHCP leases, to ensure that the query cache for those
        # leases on the nodegroup will be populated.
        query = Node.objects.filter(id=node.id)
        query = query.prefetch_related('nodegroup__dhcplease_set')
        # The cache is populated.  This is the condition that triggers the
        # separate code path in Node.dynamic_ip_addresses().
        self.assertIsNotNone(
            query[0].nodegroup.dhcplease_set.all()._result_cache)

        # dynamic_ip_addresses() still returns the node's leased addresses.
        num_queries, addresses = count_queries(query[0].dynamic_ip_addresses)
        # It only takes one query: to get the node's MAC addresses.
        self.assertEqual(1, num_queries)
        # The result is not a query set, so this isn't hiding a further query.
        no_queries, _ = count_queries(list, addresses)
        self.assertEqual(0, no_queries)
        # We still get exactly the right IP addresses.
        self.assertItemsEqual([lease.ip for lease in leases], addresses)

    def test_dynamic_ip_addresses_filters_by_mac_addresses(self):
        node = factory.make_Node()
        # Another node in the same nodegroup has some IP leases.  The one thing
        # that tells ip_addresses what nodes these leases belong to are their
        # MAC addresses.
        other_node = factory.make_Node(nodegroup=node.nodegroup)
        macs = [factory.make_MACAddress(node=node) for _ in range(2)]
        for mac in macs:
            factory.make_DHCPLease(
                nodegroup=node.nodegroup, mac=mac.mac_address)
        # The other node's leases do not get mistaken for ones that belong to
        # our original node.
        self.assertItemsEqual([], other_node.dynamic_ip_addresses())

    def test_static_ip_addresses_returns_static_ip_addresses(self):
        node = factory.make_Node()
        [mac2, mac3] = [
            factory.make_MACAddress(node=node) for _ in range(2)]
        ip1 = factory.make_StaticIPAddress(mac=mac2)
        ip2 = factory.make_StaticIPAddress(mac=mac3)
        # Create another node with a static IP address.
        other_node = factory.make_Node(nodegroup=node.nodegroup, mac=True)
        factory.make_StaticIPAddress(mac=other_node.macaddress_set.all()[0])
        self.assertItemsEqual([ip1.ip, ip2.ip], node.static_ip_addresses())

    def test_static_ip_addresses_uses_result_cache(self):
        # static_ip_addresses has a specialized code path for the case where
        # the node's static IPs are already cached in Django's ORM.  This
        # test exercises that code path.
        node = factory.make_Node()
        [mac2, mac3] = [
            factory.make_MACAddress(node=node) for _ in range(2)]
        ip1 = factory.make_StaticIPAddress(mac=mac2)
        ip2 = factory.make_StaticIPAddress(mac=mac3)

        # Don't address the node directly; address it through a query with
        # prefetched static IPs, to ensure that the query cache for those
        # IP addresses.
        query = Node.objects.filter(id=node.id)
        query = query.prefetch_related('macaddress_set__ip_addresses')

        # dynamic_ip_addresses() still returns the node's leased addresses.
        num_queries, addresses = count_queries(query[0].static_ip_addresses)
        self.assertEqual(0, num_queries)
        # The result is not a query set, so this isn't hiding a further query.
        self.assertIsInstance(addresses, list)
        # We still get exactly the right IP addresses.
        self.assertItemsEqual([ip1.ip, ip2.ip], addresses)

    def test_ip_addresses_returns_static_ip_addresses_if_allocated(self):
        # If both static and dynamic IP addresses are present, the static
        # addresses take precedence: they are allocated and deallocated in
        # a synchronous fashion whereas the dynamic addresses are updated
        # periodically.
        node = factory.make_Node(mac=True, disable_ipv4=False)
        mac = node.macaddress_set.all()[0]
        # Create a dynamic IP attached to the node.
        factory.make_DHCPLease(
            nodegroup=node.nodegroup, mac=mac.mac_address)
        # Create a static IP attached to the node.
        ip = factory.make_StaticIPAddress(mac=mac)
        self.assertItemsEqual([ip.ip], node.ip_addresses())

    def test_ip_addresses_returns_dynamic_ip_if_no_static_ip(self):
        node = factory.make_Node(mac=True, disable_ipv4=False)
        lease = factory.make_DHCPLease(
            nodegroup=node.nodegroup,
            mac=node.macaddress_set.all()[0].mac_address)
        self.assertItemsEqual([lease.ip], node.ip_addresses())

    def test_ip_addresses_includes_static_ipv4_addresses_by_default(self):
        node = factory.make_Node(disable_ipv4=False)
        ipv4_address = factory.make_ipv4_address()
        ipv6_address = factory.make_ipv6_address()
        self.patch(node, 'static_ip_addresses').return_value = [
            ipv4_address,
            ipv6_address,
            ]
        self.assertItemsEqual(
            [ipv4_address, ipv6_address],
            node.ip_addresses())

    def test_ip_addresses_includes_dynamic_ipv4_addresses_by_default(self):
        node = factory.make_Node(disable_ipv4=False)
        ipv4_address = factory.make_ipv4_address()
        ipv6_address = factory.make_ipv6_address()
        self.patch(node, 'dynamic_ip_addresses').return_value = [
            ipv4_address,
            ipv6_address,
            ]
        self.assertItemsEqual(
            [ipv4_address, ipv6_address],
            node.ip_addresses())

    def test_ip_addresses_strips_static_ipv4_addresses_if_ipv4_disabled(self):
        node = factory.make_Node(disable_ipv4=True)
        ipv4_address = factory.make_ipv4_address()
        ipv6_address = factory.make_ipv6_address()
        self.patch(node, 'static_ip_addresses').return_value = [
            ipv4_address,
            ipv6_address,
            ]
        self.assertEqual([ipv6_address], node.ip_addresses())

    def test_ip_addresses_strips_dynamic_ipv4_addresses_if_ipv4_disabled(self):
        node = factory.make_Node(disable_ipv4=True)
        ipv4_address = factory.make_ipv4_address()
        ipv6_address = factory.make_ipv6_address()
        self.patch(node, 'dynamic_ip_addresses').return_value = [
            ipv4_address,
            ipv6_address,
            ]
        self.assertEqual([ipv6_address], node.ip_addresses())

    def test_get_static_ip_mappings_returns_static_ip_and_mac(self):
        node = factory.make_Node(mac=True, disable_ipv4=False)
        [mac] = node.macaddress_set.all()
        sip = factory.make_StaticIPAddress(mac=mac)
        self.assertEqual(
            [(sip.ip, mac.mac_address)],
            node.get_static_ip_mappings())

    def test_get_static_ip_mappings_returns_mappings_for_all_macs(self):
        node = factory.make_Node(disable_ipv4=False)
        mac1 = factory.make_MACAddress(node=node)
        mac2 = factory.make_MACAddress(node=node)
        sip1 = factory.make_StaticIPAddress(mac=mac1)
        sip2 = factory.make_StaticIPAddress(mac=mac2)
        self.assertItemsEqual(
            [
                (sip1.ip, mac1.mac_address),
                (sip2.ip, mac2.mac_address),
            ],
            node.get_static_ip_mappings())

    def test_get_static_ip_mappings_includes_multiple_addresses(self):
        node = factory.make_Node(mac=True, disable_ipv4=False)
        [mac] = node.macaddress_set.all()
        sip1 = factory.make_StaticIPAddress(mac=mac)
        sip2 = factory.make_StaticIPAddress(mac=mac)
        self.assertItemsEqual(
            [
                (sip1.ip, mac.mac_address),
                (sip2.ip, mac.mac_address),
            ],
            node.get_static_ip_mappings())

    def test_get_static_ip_mappings_ignores_dynamic_addresses(self):
        node = factory.make_Node(mac=True, disable_ipv4=False)
        [mac] = node.macaddress_set.all()
        factory.make_DHCPLease(nodegroup=node.nodegroup, mac=mac.mac_address)
        self.assertEqual([], node.get_static_ip_mappings())

    def test_release_turns_on_netboot(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        node.set_netboot(on=False)
        node.release()
        self.assertTrue(node.netboot)

    def test_release_clears_osystem_and_distro_series(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        node.osystem = factory.make_name('os')
        node.distro_series = factory.make_name('series')
        node.release()
        self.assertEqual("", node.osystem)
        self.assertEqual("", node.distro_series)

    def test_release_powers_off_node(self):
        user = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=user, power_type='virsh')
        self.patch(node, 'start_transition_monitor')
        node_stop = self.patch(node, 'stop')
        node.release()
        self.assertThat(
            node_stop, MockCalledOnceWith(user))

    def test_release_deallocates_static_ip_when_node_is_off(self):
        user = factory.make_User()
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            owner=user, status=NODE_STATUS.ALLOCATED,
            power_state=POWER_STATE.OFF)
        deallocate_static_ip_addresses = self.patch_autospec(
            node, "deallocate_static_ip_addresses")
        self.patch(node, 'start_transition_monitor')
        node.release()
        self.assertThat(
            deallocate_static_ip_addresses, MockCalledOnceWith())

    def test_release_deallocates_static_ip_when_node_cannot_be_queried(self):
        user = factory.make_User()
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            owner=user, status=NODE_STATUS.ALLOCATED,
            power_state=POWER_STATE.ON, power_type='ether_wake')
        deallocate_static_ip_addresses = self.patch_autospec(
            node, "deallocate_static_ip_addresses")
        self.patch(node, 'start_transition_monitor')
        node.release()
        self.assertThat(
            deallocate_static_ip_addresses, MockCalledOnceWith())

    def test_release_doesnt_deallocate_static_ip_when_node_releasing(self):
        user = factory.make_User()
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            owner=user, status=NODE_STATUS.ALLOCATED,
            power_state=POWER_STATE.ON, power_type='virsh')
        deallocate_static_ip_addresses = self.patch_autospec(
            node, "deallocate_static_ip_addresses")
        self.patch_autospec(node, 'stop')
        self.patch(node, 'start_transition_monitor')
        node.release()
        self.assertThat(
            deallocate_static_ip_addresses, MockNotCalled())

    def test_deallocate_static_ip_deletes_static_ip_host_maps(self):
        remove_host_maps = self.patch_autospec(
            node_module, "remove_host_maps")
        user = factory.make_User()
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            owner=user, status=NODE_STATUS.ALLOCATED)
        sips = node.get_primary_mac().claim_static_ips()
        node.release()
        expected = {sip.ip.format() for sip in sips}
        self.assertThat(
            remove_host_maps, MockCalledOnceWith(
                {node.nodegroup: expected}))

    def test_deallocate_static_ip_updates_dns(self):
        # silence remove_host_maps
        self.patch_autospec(node_module, "remove_host_maps")
        dns_update_zones = self.patch(dns_config, 'dns_update_zones')
        nodegroup = factory.make_NodeGroup(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            status=NODEGROUP_STATUS.ACCEPTED)
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            nodegroup=nodegroup, status=NODE_STATUS.ALLOCATED,
            owner=factory.make_User(), power_type='ether_wake')
        node.get_primary_mac().claim_static_ips()
        node.release()
        self.assertThat(dns_update_zones, MockCalledOnceWith([node.nodegroup]))

    def test_release_logs_and_raises_errors_in_stopping(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        maaslog = self.patch(node_module, 'maaslog')
        exception_class = factory.make_exception_type()
        exception = exception_class(factory.make_name())
        self.patch(node, 'stop').side_effect = exception
        self.assertRaises(exception_class, node.release)
        self.assertEqual(NODE_STATUS.DEPLOYED, node.status)
        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "%s: Unable to shut node down: %s",
                node.hostname, unicode(exception)))

    def test_release_reverts_to_sane_state_on_error(self):
        # If release() encounters an error when stopping the node, it
        # will leave the node in its previous state (i.e. DEPLOYED).
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, power_type="virsh",
            owner=factory.make_User())
        node_stop = self.patch(node, 'stop')
        node_stop.side_effect = factory.make_exception()

        try:
            with transaction.atomic():
                node.release()
        except node_stop.side_effect.__class__:
            # We don't care about the error here, so suppress it. It
            # exists only to cause the transaction to abort.
            pass

        self.assertThat(node_stop, MockCalledOnceWith(node.owner))
        self.assertEqual(NODE_STATUS.DEPLOYED, node.status)

    def test_accept_enlistment_gets_node_out_of_declared_state(self):
        # If called on a node in New state, accept_enlistment()
        # changes the node's status, and returns the node.
        target_state = NODE_STATUS.COMMISSIONING

        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.NEW, owner=user)
        self.patch(node, 'start_transition_monitor')
        with post_commit_hooks:
            return_value = node.accept_enlistment(user)
        self.assertEqual((node, target_state), (return_value, node.status))

    def test_accept_enlistment_does_nothing_if_already_accepted(self):
        # If a node has already been accepted, but not assigned a role
        # yet, calling accept_enlistment on it is meaningless but not an
        # error.  The method returns None in this case.
        accepted_states = [
            NODE_STATUS.COMMISSIONING,
            NODE_STATUS.READY,
            ]
        nodes = {
            status: factory.make_Node(status=status)
            for status in accepted_states}

        return_values = {
            status: node.accept_enlistment(factory.make_User())
            for status, node in nodes.items()}

        self.assertEqual(
            {status: None for status in accepted_states}, return_values)
        self.assertEqual(
            {status: status for status in accepted_states},
            {status: node.status for status, node in nodes.items()})

    def test_accept_enlistment_rejects_bad_state_change(self):
        # If a node is neither New nor in one of the "accepted"
        # states where acceptance is a safe no-op, accept_enlistment
        # raises a node state violation and leaves the node's state
        # unchanged.
        all_states = map_enum(NODE_STATUS).values()
        acceptable_states = [
            NODE_STATUS.NEW,
            NODE_STATUS.COMMISSIONING,
            NODE_STATUS.READY,
            ]
        unacceptable_states = set(all_states) - set(acceptable_states)
        nodes = {
            status: factory.make_Node(status=status)
            for status in unacceptable_states}

        exceptions = {status: False for status in unacceptable_states}
        for status, node in nodes.items():
            try:
                node.accept_enlistment(factory.make_User())
            except NodeStateViolation:
                exceptions[status] = True

        self.assertEqual(
            {status: True for status in unacceptable_states}, exceptions)
        self.assertEqual(
            {status: status for status in unacceptable_states},
            {status: node.status for status, node in nodes.items()})

    def test_start_commissioning_changes_status_and_starts_node(self):
        node = factory.make_Node(
            status=NODE_STATUS.NEW, power_type='ether_wake')
        node_start = self.patch(node, 'start')
        # Return a post-commit hook from Node.start().
        node_start.side_effect = lambda user, user_data: post_commit()
        factory.make_MACAddress(node=node)
        admin = factory.make_admin()
        node.start_commissioning(admin)
        post_commit_hooks.reset()  # Ignore these for now.
        node = reload_object(node)
        expected_attrs = {
            'status': NODE_STATUS.COMMISSIONING,
        }
        self.assertAttributes(node, expected_attrs)
        self.assertThat(node_start, MockCalledOnceWith(
            admin, user_data=ANY))

    def test_start_commissioning_sets_user_data(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node_start = self.patch(node, 'start')
        node_start.side_effect = lambda user, user_data: post_commit()
        user_data = factory.make_string().encode('ascii')
        generate_user_data = self.patch(
            commissioning, 'generate_user_data')
        generate_user_data.return_value = user_data
        admin = factory.make_admin()
        node.start_commissioning(admin)
        post_commit_hooks.reset()  # Ignore these for now.
        self.assertThat(node_start, MockCalledOnceWith(
            admin, user_data=user_data))

    def test_start_commissioning_clears_node_commissioning_results(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        NodeResult.objects.store_data(
            node, factory.make_string(),
            random.randint(0, 10),
            RESULT_TYPE.COMMISSIONING,
            Bin(factory.make_bytes()))
        with post_commit_hooks:
            node.start_commissioning(factory.make_admin())
        self.assertItemsEqual([], node.noderesult_set.all())

    def test_start_commissioning_ignores_other_commissioning_results(self):
        node = factory.make_Node()
        filename = factory.make_string()
        data = factory.make_bytes()
        script_result = random.randint(0, 10)
        NodeResult.objects.store_data(
            node, filename, script_result, RESULT_TYPE.COMMISSIONING,
            Bin(data))
        other_node = factory.make_Node(status=NODE_STATUS.NEW)
        with post_commit_hooks:
            other_node.start_commissioning(factory.make_admin())
        self.assertEqual(
            data, NodeResult.objects.get_data(node, filename))

    def test_start_commissioning_reverts_to_sane_state_on_error(self):
        # When start_commissioning encounters an error when trying to
        # start the node, it will revert the node to its previous
        # status.
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.NEW)
        generate_user_data = self.patch(commissioning, 'generate_user_data')
        node_start = self.patch(node, 'start')
        node_start.side_effect = factory.make_exception()

        try:
            with transaction.atomic():
                node.start_commissioning(admin)
        except node_start.side_effect.__class__:
            # We don't care about the error here, so suppress it. It
            # exists only to cause the transaction to abort.
            pass

        self.assertThat(
            node_start,
            MockCalledOnceWith(
                admin, user_data=generate_user_data.return_value))
        self.assertEqual(NODE_STATUS.NEW, node.status)

    def test_start_commissioning_logs_and_raises_errors_in_starting(self):
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.NEW)
        maaslog = self.patch(node_module, 'maaslog')
        exception = NoConnectionsAvailable(factory.make_name())
        self.patch(node, 'start').side_effect = exception
        self.assertRaises(
            NoConnectionsAvailable, node.start_commissioning, admin)
        self.assertEqual(NODE_STATUS.NEW, node.status)
        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "%s: Could not start node for commissioning: %s",
                node.hostname, exception))

    def test_abort_commissioning_reverts_to_sane_state_on_error(self):
        # If abort commissioning hits an error when trying to stop the
        # node, it will revert the node to the state it was in before
        # abort_commissioning() was called.
        admin = factory.make_admin()
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, power_type="virsh")
        node_stop = self.patch(node, 'stop')
        node_stop.side_effect = factory.make_exception()

        try:
            with transaction.atomic():
                node.abort_commissioning(admin)
        except node_stop.side_effect.__class__:
            # We don't care about the error here, so suppress it. It
            # exists only to cause the transaction to abort.
            pass

        self.assertThat(node_stop, MockCalledOnceWith(admin))
        self.assertEqual(NODE_STATUS.COMMISSIONING, node.status)

    def test_start_commissioning_starts_monitor(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        admin = factory.make_admin()

        monitor_timeout = random.randint(1, 100)
        monitor_start = self.patch_autospec(
            node_module.TransitionMonitor, "start")

        self.patch(node, 'get_commissioning_time')
        node.get_commissioning_time.return_value = monitor_timeout

        with post_commit_hooks:
            node.start_commissioning(admin)

        self.assertThat(monitor_start, MockCalledOnceWith(ANY))
        [monitor], _ = monitor_start.call_args  # Extract `self`.
        self.assertAttributes(monitor, {
            "timeout": timedelta(seconds=monitor_timeout),
            "status": NODE_STATUS.READY,
            "system_id": node.system_id,
        })

    def test_abort_commissioning_stops_monitor(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        admin = factory.make_admin()
        monitor_stop = self.patch_autospec(
            node_module.TransitionMonitor, "stop")
        self.patch(Node, "_set_status")
        with post_commit_hooks:
            node.abort_commissioning(admin)
        self.assertThat(monitor_stop, MockCalledOnceWith(ANY))
        [monitor], _ = monitor_stop.call_args  # Extract `self`.
        self.assertAttributes(monitor, {"system_id": node.system_id})

    def test_abort_commissioning_logs_and_raises_errors_in_stopping(self):
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        maaslog = self.patch(node_module, 'maaslog')
        exception_class = factory.make_exception_type()
        exception = exception_class(factory.make_name())
        self.patch(node, 'stop').side_effect = exception
        self.assertRaises(
            exception_class, node.abort_commissioning, admin)
        self.assertEqual(NODE_STATUS.COMMISSIONING, node.status)
        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "%s: Error when aborting commissioning: %s",
                node.hostname, exception))

    def test_abort_commissioning_changes_status_and_stops_node(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, power_type='virsh')
        admin = factory.make_admin()

        node_stop = self.patch(node, 'stop')
        # Return a post-commit hook from Node.stop().
        node_stop.side_effect = lambda user: post_commit()
        self.patch(Node, "_set_status")

        with post_commit_hooks:
            node.abort_commissioning(admin)

        self.assertThat(node_stop, MockCalledOnceWith(admin))
        self.assertThat(node._set_status, MockCalledOnceWith(
            node.system_id, NODE_STATUS.NEW))

    def test_abort_commisssioning_errors_if_node_is_not_commissioning(self):
        unaccepted_statuses = set(map_enum(NODE_STATUS).values())
        unaccepted_statuses.remove(NODE_STATUS.COMMISSIONING)
        for status in unaccepted_statuses:
            node = factory.make_Node(
                status=status, power_type='virsh')
            self.assertRaises(
                NodeStateViolation, node.abort_commissioning,
                factory.make_admin())

    def test_full_clean_checks_status_transition_and_raises_if_invalid(self):
        # RETIRED -> ALLOCATED is an invalid transition.
        node = factory.make_Node(
            status=NODE_STATUS.RETIRED, owner=factory.make_User())
        node.status = NODE_STATUS.ALLOCATED
        self.assertRaisesRegexp(
            NodeStateViolation,
            "Invalid transition: Retired -> Allocated.",
            node.full_clean)

    def test_full_clean_passes_if_status_unchanged(self):
        status = factory.pick_choice(NODE_STATUS_CHOICES)
        node = factory.make_Node(status=status)
        node.status = status
        node.full_clean()
        # The test is that this does not raise an error.
        pass

    def test_full_clean_passes_if_status_valid_transition(self):
        # NODE_STATUS.READY -> NODE_STATUS.ALLOCATED is a valid
        # transition.
        status = NODE_STATUS.READY
        node = factory.make_Node(status=status)
        node.status = NODE_STATUS.ALLOCATED
        node.full_clean()
        # The test is that this does not raise an error.
        pass

    def test_save_raises_node_state_violation_on_bad_transition(self):
        # RETIRED -> ALLOCATED is an invalid transition.
        node = factory.make_Node(
            status=NODE_STATUS.RETIRED, owner=factory.make_User())
        node.status = NODE_STATUS.ALLOCATED
        self.assertRaisesRegexp(
            NodeStateViolation,
            "Invalid transition: Retired -> Allocated.",
            node.save)

    def test_full_clean_checks_architecture_for_installable_nodes(self):
        node = factory.make_Node(installable=False, architecture='')
        node.installable = True
        exception = self.assertRaises(ValidationError, node.full_clean)
        self.assertEqual(
            exception.error_dict,
            {'architecture':
                ['Architecture must be defined for installable nodes.']})

    def test_netboot_defaults_to_True(self):
        node = Node()
        self.assertTrue(node.netboot)

    def test_nodegroup_cannot_be_null(self):
        node = factory.make_Node()
        node.nodegroup = None
        self.assertRaises(ValidationError, node.save)

    def test_fqdn_returns_hostname_if_dns_not_managed(self):
        nodegroup = factory.make_NodeGroup(
            name=factory.make_string(),
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        hostname_with_domain = '%s.%s' % (
            factory.make_string(), factory.make_string())
        node = factory.make_Node(
            nodegroup=nodegroup, hostname=hostname_with_domain)
        self.assertEqual(hostname_with_domain, node.fqdn)

    def test_fqdn_replaces_hostname_if_dns_is_managed(self):
        hostname_without_domain = factory.make_name('hostname')
        hostname_with_domain = '%s.%s' % (
            hostname_without_domain, factory.make_string())
        domain = factory.make_name('domain')
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ACCEPTED,
            name=domain,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        node = factory.make_Node(
            hostname=hostname_with_domain, nodegroup=nodegroup)
        expected_hostname = '%s.%s' % (hostname_without_domain, domain)
        self.assertEqual(expected_hostname, node.fqdn)

    def test_boot_type_has_fastpath_set_by_default(self):
        node = factory.make_Node()
        self.assertEqual(NODE_BOOT.FASTPATH, node.boot_type)

    def test_split_arch_returns_arch_as_tuple(self):
        main_arch = factory.make_name('arch')
        sub_arch = factory.make_name('subarch')
        full_arch = '%s/%s' % (main_arch, sub_arch)
        node = factory.make_Node(architecture=full_arch)
        self.assertEqual((main_arch, sub_arch), node.split_arch())

    def test_mac_addresses_on_managed_interfaces_returns_only_managed(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        mac_with_interface = node.get_primary_mac()

        mac_with_no_interface = factory.make_MACAddress(node=node)
        unmanaged_interface = factory.make_NodeGroupInterface(
            nodegroup=node.nodegroup,
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        mac_with_unmanaged_interface = factory.make_MACAddress_with_Node(
            node=node, cluster_interface=unmanaged_interface)
        ignore_unused(mac_with_no_interface, mac_with_unmanaged_interface)

        observed = node.mac_addresses_on_managed_interfaces()
        self.assertItemsEqual([mac_with_interface], observed)

    def test_mac_addresses_on_managed_interfaces_returns_empty_if_none(self):
        node = factory.make_Node(mac=True)
        observed = node.mac_addresses_on_managed_interfaces()
        self.assertItemsEqual([], observed)

    def test_mac_addresses_on_m_i_uses_parent_for_noninstallable_nodes(self):
        parent = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        node = factory.make_Node(mac=True, installable=False, parent=parent)
        mac_with_interface = node.get_primary_mac()
        self.assertItemsEqual(
            [mac_with_interface], node.mac_addresses_on_managed_interfaces())

    def test_mark_failed_updates_status(self):
        self.disable_node_query()
        nodes_mapping = {
            status: factory.make_Node(status=status)
            for status in NODE_FAILURE_STATUS_TRANSITIONS
        }
        for node in nodes_mapping.values():
            node.mark_failed(factory.make_name('error-description'))
        self.assertEqual(
            NODE_FAILURE_STATUS_TRANSITIONS,
            {status: node.status for status, node in nodes_mapping.items()})

    def test_mark_failed_updates_error_description(self):
        self.disable_node_query()
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        description = factory.make_name('error-description')
        node.mark_failed(description)
        self.assertEqual(description, reload_object(node).error_description)

    def test_mark_failed_raises_for_unauthorized_node_status(self):
        but_not = NODE_FAILURE_STATUS_TRANSITIONS.keys()
        but_not.extend(NODE_FAILURE_STATUS_TRANSITIONS.viewvalues())
        but_not.append(NODE_STATUS.NEW)
        status = factory.pick_choice(NODE_STATUS_CHOICES, but_not=but_not)
        node = factory.make_Node(status=status)
        description = factory.make_name('error-description')
        self.assertRaises(NodeStateViolation, node.mark_failed, description)

    def test_mark_failed_ignores_if_already_failed(self):
        status = random.choice([
            NODE_STATUS.FAILED_DEPLOYMENT, NODE_STATUS.FAILED_COMMISSIONING])
        node = factory.make_Node(status=status)
        description = factory.make_name('error-description')
        node.mark_failed(description)
        self.assertEqual(status, node.status)

    def test_mark_failed_ignores_if_status_is_NEW(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        description = factory.make_name('error-description')
        node.mark_failed(description)
        self.assertEqual(NODE_STATUS.NEW, node.status)

    def test_mark_broken_changes_status_to_broken(self):
        node = factory.make_Node(
            status=NODE_STATUS.NEW, owner=factory.make_User())
        node.mark_broken(factory.make_name('error-description'))
        self.assertEqual(NODE_STATUS.BROKEN, reload_object(node).status)

    def test_mark_broken_releases_allocated_node(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        err_desc = factory.make_name('error-description')
        release = self.patch(node, 'release')
        node.mark_broken(err_desc)
        self.expectThat(node.owner, Is(None))
        self.assertThat(release, MockCalledOnceWith())

    def test_mark_fixed_sets_default_osystem_and_distro_series(self):
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        node.osystem = factory.make_name('osystem')
        node.distro_series = factory.make_name('distro_series')
        node.mark_fixed()
        expected_osystem = expected_distro_series = ''
        self.expectThat(expected_osystem, Equals(node.osystem))
        self.expectThat(expected_distro_series, Equals(node.distro_series))

    def test_mark_fixed_changes_status(self):
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        node.mark_fixed()
        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)

    def test_mark_fixed_updates_error_description(self):
        description = factory.make_name('error-description')
        node = factory.make_Node(
            status=NODE_STATUS.BROKEN, error_description=description)
        node.mark_fixed()
        self.assertEqual('', reload_object(node).error_description)

    def test_mark_fixed_fails_if_node_isnt_broken(self):
        status = factory.pick_choice(
            NODE_STATUS_CHOICES, but_not=[NODE_STATUS.BROKEN])
        node = factory.make_Node(status=status)
        self.assertRaises(NodeStateViolation, node.mark_fixed)

    def test_mark_fixed_clears_installation_results(self):
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        node_result = factory.make_NodeResult_for_installation(node=node)
        self.assertEquals(
            [node_result], list(NodeResult.objects.filter(
                node=node, result_type=RESULT_TYPE.INSTALLATION)))
        node.mark_fixed()
        self.assertEquals(
            [], list(NodeResult.objects.filter(
                node=node, result_type=RESULT_TYPE.INSTALLATION)))

    def test_update_power_state(self):
        node = factory.make_Node()
        state = factory.pick_enum(POWER_STATE)
        node.update_power_state(state)
        self.assertEqual(state, reload_object(node).power_state)

    def test_update_power_state_readies_node_if_releasing(self):
        node = factory.make_Node(
            power_state=POWER_STATE.ON, status=NODE_STATUS.RELEASING,
            owner=None)
        self.patch(node, 'stop_transition_monitor')
        node.update_power_state(POWER_STATE.OFF)
        self.expectThat(node.status, Equals(NODE_STATUS.READY))
        self.expectThat(node.owner, Is(None))

    def test_update_power_state_does_not_change_status_if_not_releasing(self):
        node = factory.make_Node(
            power_state=POWER_STATE.ON, status=NODE_STATUS.ALLOCATED)
        node.update_power_state(POWER_STATE.OFF)
        self.assertThat(node.status, Equals(NODE_STATUS.ALLOCATED))

    def test_update_power_state_stops_monitor_if_releasing(self):
        node = factory.make_Node(
            power_state=POWER_STATE.ON, status=NODE_STATUS.RELEASING,
            owner=None)
        self.patch(node, 'stop_transition_monitor')
        node.update_power_state(POWER_STATE.OFF)
        self.assertThat(node.stop_transition_monitor, MockCalledOnceWith())

    def test_update_power_state_does_not_stop_monitor_if_not_releasing(self):
        node = factory.make_Node(
            power_state=POWER_STATE.ON, status=NODE_STATUS.ALLOCATED)
        self.patch(node, 'stop_transition_monitor')
        node.update_power_state(POWER_STATE.OFF)
        self.assertThat(node.stop_transition_monitor, MockNotCalled())

    def test_update_power_state_does_not_change_status_if_not_off(self):
        node = factory.make_Node(
            power_state=POWER_STATE.OFF, status=NODE_STATUS.ALLOCATED)
        node.update_power_state(POWER_STATE.ON)
        self.expectThat(node.status, Equals(NODE_STATUS.ALLOCATED))

    def test_update_power_state_deallocates_static_ips_if_releasing(self):
        node = factory.make_Node(
            power_state=POWER_STATE.ON, status=NODE_STATUS.RELEASING,
            owner=None)
        deallocate_static_ip_addresses = self.patch_autospec(
            node, 'deallocate_static_ip_addresses')
        self.patch(node, 'stop_transition_monitor')
        node.update_power_state(POWER_STATE.OFF)
        self.assertThat(deallocate_static_ip_addresses, MockCalledOnceWith())

    def test_update_power_state_doesnt_deallocates_static_ips_if_not_off(self):
        node = factory.make_Node(
            power_state=POWER_STATE.OFF, status=NODE_STATUS.ALLOCATED)
        deallocate_static_ip_addresses = self.patch_autospec(
            node, 'deallocate_static_ip_addresses')
        node.update_power_state(POWER_STATE.ON)
        self.assertThat(deallocate_static_ip_addresses, MockNotCalled())

    def test_end_deployment_changes_state(self):
        self.disable_node_query()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        node.end_deployment()
        self.assertEqual(NODE_STATUS.DEPLOYED, reload_object(node).status)

    def test_start_deployment_changes_state(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        node.start_deployment()
        self.assertEqual(NODE_STATUS.DEPLOYING, reload_object(node).status)

    def test_handle_monitor_expired_marks_node_as_failed(self):
        self.disable_node_query()
        status = random.choice(MONITORED_STATUSES)
        node = factory.make_Node(status=status)
        timeout = random.randint(1, 100)
        monitor_context = {
            'timeout': timeout,
        }
        node.handle_monitor_expired(monitor_context)
        node = reload_object(node)
        self.assertEqual(get_failed_status(status), node.status)
        error_msg = (
            "Node operation '%s' timed out after %s." % (
                NODE_STATUS_CHOICES_DICT[status],
                timedelta(seconds=timeout))
        )
        self.assertEqual(error_msg, node.error_description)

    def test_handle_monitor_expired_ignores_event_if_node_state_changed(self):
        status = factory.pick_enum(NODE_STATUS, but_not=MONITORED_STATUSES)
        node = factory.make_Node(status=status)
        node.handle_monitor_expired({})
        node = reload_object(node)
        self.assertEqual(status, node.status)

    def test_get_boot_purpose_known_node(self):
        # The following table shows the expected boot "purpose" for each set
        # of node parameters.
        options = [
            ("poweroff", {"status": NODE_STATUS.NEW}),
            ("commissioning", {"status": NODE_STATUS.COMMISSIONING}),
            ("commissioning", {"status": NODE_STATUS.DISK_ERASING}),
            ("poweroff", {"status": NODE_STATUS.FAILED_COMMISSIONING}),
            ("poweroff", {"status": NODE_STATUS.MISSING}),
            ("poweroff", {"status": NODE_STATUS.READY}),
            ("poweroff", {"status": NODE_STATUS.RESERVED}),
            ("install", {"status": NODE_STATUS.DEPLOYING, "netboot": True}),
            ("xinstall", {"status": NODE_STATUS.DEPLOYING, "netboot": True}),
            ("local", {"status": NODE_STATUS.DEPLOYING, "netboot": False}),
            ("local", {"status": NODE_STATUS.DEPLOYED}),
            ("poweroff", {"status": NODE_STATUS.RETIRED}),
            ]
        node = factory.make_Node(boot_type=NODE_BOOT.DEBIAN)
        mock_get_boot_images_for = self.patch(
            preseed_module, 'get_boot_images_for')
        for purpose, parameters in options:
            boot_image = make_rpc_boot_image(purpose=purpose)
            mock_get_boot_images_for.return_value = [boot_image]
            if purpose == "xinstall":
                node.boot_type = NODE_BOOT.FASTPATH
            for name, value in parameters.items():
                setattr(node, name, value)
            self.assertEqual(purpose, node.get_boot_purpose())

    def test_get_boot_purpose_osystem_no_xinstall_support(self):
        osystem = make_usable_osystem(self)
        release = osystem['default_release']
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING, netboot=True,
            osystem=osystem['name'], distro_series=release,
            boot_type=NODE_BOOT.FASTPATH)
        boot_image = make_rpc_boot_image(purpose='install')
        self.patch(
            preseed_module, 'get_boot_images_for').return_value = [boot_image]
        self.assertEqual('install', node.get_boot_purpose())

    def test_pxe_mac_default_is_none(self):
        node = factory.make_Node()
        self.assertIsNone(node.pxe_mac)

    def test_get_pxe_mac_returns_pxe_mac_if_pxe_mac_set(self):
        node = factory.make_Node(mac=True)
        node.pxe_mac = factory.make_MACAddress(node=node)
        node.save()
        self.assertEqual(node.pxe_mac, node.get_pxe_mac())

    def test_get_pxe_mac_returns_first_macaddress_if_pxe_mac_unset(self):
        node = factory.make_Node(mac=True)
        factory.make_MACAddress(node=node)
        self.assertEqual(node.macaddress_set.first(), node.get_pxe_mac())

    def test_pxe_mac_deletion_does_not_delete_node(self):
        node = factory.make_Node(mac=True)
        node.pxe_mac = factory.make_MACAddress(node=node)
        node.save()
        node.pxe_mac.delete()
        self.assertThat(reload_object(node), Not(Is(None)))

    def test_get_pxe_mac_vendor_returns_vendor(self):
        node = factory.make_Node()
        mac = factory.make_MACAddress(address='ec:a8:6b:fd:ae:3f', node=node)
        node.pxe_mac = mac
        node.save()
        self.assertEqual(
            "ELITEGROUP COMPUTER SYSTEMS CO., LTD.",
            node.get_pxe_mac_vendor())

    def test_get_extra_macs_returns_all_but_pxe_mac(self):
        node = factory.make_Node()
        macs = [factory.make_MACAddress(node=node) for _ in xrange(3)]
        # Do not set the pxe mac to the first mac to make sure the pxe mac
        # (and not the first created) is excluded from the list returned by
        # `get_extra_macs`.
        pxe_mac_index = 1
        node.pxe_mac = macs[pxe_mac_index]
        node.save()
        del macs[pxe_mac_index]
        self.assertItemsEqual(
            macs,
            node.get_extra_macs())

    def test_get_extra_macs_returns_all_but_first_mac_if_no_pxe_mac(self):
        node = factory.make_Node()
        macs = [factory.make_MACAddress(node=node) for _ in xrange(3)]
        node.save()
        self.assertItemsEqual(
            macs[1:],
            node.get_extra_macs())


class TestNode_pxe_mac_on_managed_interface(MAASServerTestCase):

    def test__returns_true_if_managed(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        self.assertTrue(node.is_pxe_mac_on_managed_interface())

    def test__returns_false_if_no_pxe_mac(self):
        node = factory.make_Node()
        self.assertFalse(node.is_pxe_mac_on_managed_interface())

    def test__returns_false_if_no_attached_cluster_interface(self):
        node = factory.make_Node()
        node.pxe_mac = factory.make_MACAddress(node=node)
        node.save()
        self.assertFalse(node.is_pxe_mac_on_managed_interface())

    def test__returns_false_if_cluster_interface_unmanaged(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        self.assertFalse(node.is_pxe_mac_on_managed_interface())


class NodeRoutersTest(MAASServerTestCase):

    def test_routers_stores_mac_address(self):
        node = factory.make_Node()
        macs = [MAC('aa:bb:cc:dd:ee:ff')]
        node.routers = macs
        node.save()
        self.assertEqual(macs, reload_object(node).routers)

    def test_routers_stores_multiple_mac_addresses(self):
        node = factory.make_Node()
        macs = [MAC('aa:bb:cc:dd:ee:ff'), MAC('00:11:22:33:44:55')]
        node.routers = macs
        node.save()
        self.assertEqual(macs, reload_object(node).routers)

    def test_routers_can_append(self):
        node = factory.make_Node()
        mac1 = MAC('aa:bb:cc:dd:ee:ff')
        mac2 = MAC('00:11:22:33:44:55')
        node.routers = [mac1]
        node.save()
        node = reload_object(node)
        node.routers.append(mac2)
        node.save()
        self.assertEqual([mac1, mac2], reload_object(node).routers)


class NodeTransitionsTests(MAASServerTestCase):
    """Test the structure of NODE_TRANSITIONS."""

    def test_NODE_TRANSITIONS_initial_states(self):
        allowed_states = set(NODE_STATUS_CHOICES_DICT.keys() + [None])

        self.assertTrue(set(NODE_TRANSITIONS.keys()) <= allowed_states)

    def test_NODE_TRANSITIONS_destination_state(self):
        all_destination_states = []
        for destination_states in NODE_TRANSITIONS.values():
            all_destination_states.extend(destination_states)
        allowed_states = set(NODE_STATUS_CHOICES_DICT.keys())

        self.assertTrue(set(all_destination_states) <= allowed_states)


class NodeManagerTest(MAASServerTestCase):

    def make_node(self, user=None, **kwargs):
        """Create a node, allocated to `user` if given."""
        if user is None:
            status = NODE_STATUS.READY
        else:
            status = NODE_STATUS.ALLOCATED
        return factory.make_Node(status=status, owner=user, **kwargs)

    def make_node_with_mac(self, user=None, **kwargs):
        node = self.make_node(user, **kwargs)
        mac = factory.make_MACAddress(node=node)
        return node, mac

    def make_user_data(self):
        """Create a blob of arbitrary user-data."""
        return factory.make_string().encode('ascii')

    def test_filter_by_ids_filters_nodes_by_ids(self):
        nodes = [factory.make_Node() for counter in range(5)]
        ids = [node.system_id for node in nodes]
        selection = slice(1, 3)
        self.assertItemsEqual(
            nodes[selection],
            Node.objects.filter_by_ids(Node.objects.all(), ids[selection]))

    def test_filter_by_ids_with_empty_list_returns_empty(self):
        factory.make_Node()
        self.assertItemsEqual(
            [], Node.objects.filter_by_ids(Node.objects.all(), []))

    def test_filter_by_ids_without_ids_returns_full(self):
        node = factory.make_Node()
        self.assertItemsEqual(
            [node], Node.objects.filter_by_ids(Node.objects.all(), None))

    def test_get_nodes_for_user_lists_visible_nodes(self):
        """get_nodes with perm=NODE_PERMISSION.VIEW lists the nodes a user
        has access to.

        When run for a regular user it returns unowned nodes, and nodes
        owned by that user.
        """
        user = factory.make_User()
        visible_nodes = [self.make_node(owner) for owner in [None, user]]
        self.make_node(factory.make_User())
        self.assertItemsEqual(
            visible_nodes, Node.objects.get_nodes(user, NODE_PERMISSION.VIEW))

    def test_get_nodes_admin_lists_all_nodes(self):
        admin = factory.make_admin()
        owners = [
            None,
            factory.make_User(),
            factory.make_admin(),
            admin,
            ]
        nodes = [self.make_node(owner) for owner in owners]
        self.assertItemsEqual(
            nodes, Node.objects.get_nodes(admin, NODE_PERMISSION.VIEW))

    def test_get_nodes_filters_by_id(self):
        user = factory.make_User()
        nodes = [self.make_node(user) for counter in range(5)]
        ids = [node.system_id for node in nodes]
        wanted_slice = slice(0, 3)
        self.assertItemsEqual(
            nodes[wanted_slice],
            Node.objects.get_nodes(
                user, NODE_PERMISSION.VIEW, ids=ids[wanted_slice]))

    def test_get_nodes_filters_from_nodes(self):
        admin = factory.make_admin()
        # Node that we want to see in the result:
        wanted_node = factory.make_Node()
        # Node that we'll exclude from from_nodes:
        factory.make_Node()

        self.assertItemsEqual(
            [wanted_node],
            Node.objects.get_nodes(
                admin, NODE_PERMISSION.VIEW,
                from_nodes=Node.objects.filter(id=wanted_node.id)))

    def test_get_nodes_combines_from_nodes_with_other_filter(self):
        user = factory.make_User()
        # Node that we want to see in the result:
        matching_node = factory.make_Node(owner=user)
        # Node that we'll exclude from from_nodes:
        factory.make_Node(owner=user)
        # Node that will be ignored on account of belonging to someone else:
        invisible_node = factory.make_Node(owner=factory.make_User())

        self.assertItemsEqual(
            [matching_node],
            Node.objects.get_nodes(
                user, NODE_PERMISSION.VIEW,
                from_nodes=Node.objects.filter(id__in=(
                    matching_node.id,
                    invisible_node.id,
                    ))))

    def test_get_nodes_with_edit_perm_for_user_lists_owned_nodes(self):
        user = factory.make_User()
        visible_node = self.make_node(user)
        self.make_node(None)
        self.make_node(factory.make_User())
        self.assertItemsEqual(
            [visible_node],
            Node.objects.get_nodes(user, NODE_PERMISSION.EDIT))

    def test_get_nodes_with_edit_perm_admin_lists_all_nodes(self):
        admin = factory.make_admin()
        owners = [
            None,
            factory.make_User(),
            factory.make_admin(),
            admin,
            ]
        nodes = [self.make_node(owner) for owner in owners]
        self.assertItemsEqual(
            nodes, Node.objects.get_nodes(admin, NODE_PERMISSION.EDIT))

    def test_get_nodes_with_admin_perm_returns_empty_list_for_user(self):
        user = factory.make_User()
        [self.make_node(user) for counter in range(5)]
        self.assertItemsEqual(
            [],
            Node.objects.get_nodes(user, NODE_PERMISSION.ADMIN))

    def test_get_nodes_with_admin_perm_returns_all_nodes_for_admin(self):
        user = factory.make_User()
        nodes = [self.make_node(user) for counter in range(5)]
        self.assertItemsEqual(
            nodes,
            Node.objects.get_nodes(
                factory.make_admin(), NODE_PERMISSION.ADMIN))

    def test_get_nodes_with_null_user(self):
        # Recreate conditions of bug 1376023. It is not valid to have a
        # node in this state with no user, however the code should not
        # crash.
        node = factory.make_Node(
            status=NODE_STATUS.FAILED_RELEASING, owner=None)
        observed = Node.objects.get_nodes(
            user=None, perm=NODE_PERMISSION.EDIT, ids=[node.system_id])
        self.assertItemsEqual([], observed)

    def test_get_visible_node_or_404_ok(self):
        """get_node_or_404 fetches nodes by system_id."""
        user = factory.make_User()
        node = self.make_node(user)
        self.assertEqual(
            node,
            Node.objects.get_node_or_404(
                node.system_id, user, NODE_PERMISSION.VIEW))

    def test_get_available_nodes_finds_available_nodes(self):
        user = factory.make_User()
        node1 = self.make_node(None)
        node2 = self.make_node(None)
        self.assertItemsEqual(
            [node1, node2],
            Node.objects.get_available_nodes_for_acquisition(user))

    def test_get_available_node_returns_empty_list_if_empty(self):
        user = factory.make_User()
        self.assertEqual(
            [], list(Node.objects.get_available_nodes_for_acquisition(user)))

    def test_get_available_nodes_ignores_taken_nodes(self):
        user = factory.make_User()
        available_status = NODE_STATUS.READY
        unavailable_statuses = (
            set(NODE_STATUS_CHOICES_DICT) - set([available_status]))
        for status in unavailable_statuses:
            factory.make_Node(status=status)
        self.assertEqual(
            [], list(Node.objects.get_available_nodes_for_acquisition(user)))

    def test_get_available_node_ignores_invisible_nodes(self):
        user = factory.make_User()
        node = self.make_node()
        node.owner = factory.make_User()
        node.save()
        self.assertEqual(
            [], list(Node.objects.get_available_nodes_for_acquisition(user)))

    def test_netboot_on(self):
        node = factory.make_Node(netboot=False)
        node.set_netboot(True)
        self.assertTrue(node.netboot)

    def test_netboot_off(self):
        node = factory.make_Node(netboot=True)
        node.set_netboot(False)
        self.assertFalse(node.netboot)


class TestNodeErase(MAASServerTestCase):

    def test_release_or_erase_erases_when_enabled(self):
        owner = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=owner)
        Config.objects.set_config(
            'enable_disk_erasing_on_release', True)
        erase_mock = self.patch_autospec(node, 'start_disk_erasing')
        release_mock = self.patch_autospec(node, 'release')
        node.release_or_erase()
        self.assertThat(erase_mock, MockCalledOnceWith(owner))
        self.assertThat(release_mock, MockNotCalled())

    def test_release_or_erase_releases_when_disabled(self):
        owner = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=owner)
        Config.objects.set_config(
            'enable_disk_erasing_on_release', False)
        erase_mock = self.patch_autospec(node, 'start_disk_erasing')
        release_mock = self.patch_autospec(node, 'release')
        node.release_or_erase()
        self.assertThat(release_mock, MockCalledOnceWith())
        self.assertThat(erase_mock, MockNotCalled())


class TestNodeParentRelationShip(MAASServerTestCase):

    def test_children_field_returns_children(self):
        parent = factory.make_Node()
        # Create other nodes.
        [factory.make_Node() for _ in range(3)]
        children = [factory.make_Node(parent=parent) for _ in range(3)]
        self.assertItemsEqual(parent.children.all(), children)

    def test_children_get_deleted_when_parent_is_deleted(self):
        parent = factory.make_Node()
        # Create children.
        [factory.make_Node(parent=parent) for _ in range(3)]
        other_nodes = [factory.make_Node() for _ in range(3)]
        parent.delete()
        self.assertItemsEqual(other_nodes, Node.objects.all())

    def test_children_get_deleted_when_parent_is_released(self):
        owner = factory.make_User()
        # Create children.
        parent = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=owner)
        [factory.make_Node(parent=parent) for _ in range(3)]
        other_nodes = [factory.make_Node() for _ in range(3)]
        parent.release()
        self.assertItemsEqual([], parent.children.all())
        self.assertItemsEqual(other_nodes + [parent], Node.objects.all())


class TestAllNodeManagers(MAASServerTestCase):
    """Test the node's managers."""

    def test_objects_lists_installable_nodes(self):
        # Create nodes.
        nodes = [factory.make_Node(installable=True) for _ in range(3)]
        # Create devices.
        [factory.make_Node(installable=False) for _ in range(3)]
        self.assertItemsEqual(nodes, Node.nodes.all())

    def test_devices_lists_noninstallable_nodes(self):
        # Create nodes.
        [factory.make_Node(installable=True) for _ in range(3)]
        # Create devices.
        devices = [factory.make_Node(installable=False) for _ in range(3)]
        self.assertItemsEqual(devices, Node.devices.all())

    def test_all_lists_all_nodes(self):
        # Create nodes.
        nodes = [factory.make_Node(installable=True) for _ in range(3)]
        # Create devices.
        devices = [factory.make_Node(installable=False) for _ in range(3)]
        self.assertItemsEqual(nodes + devices, Node.objects.all())


class TestNodeTransitionMonitors(MAASServerTestCase):

    def prepare_rpc(self):
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        return self.useFixture(MockLiveRegionToClusterRPCFixture())

    def patch_datetime_now(self, nowish_timestamp):
        mock_datetime = self.patch(monitors_module, "datetime")
        mock_datetime.now.return_value = nowish_timestamp

    def test__start_transition_monitor_starts_monitor(self):
        rpc_fixture = self.prepare_rpc()
        now = datetime.now(tz=amp.utc)
        self.patch_datetime_now(now)
        node = factory.make_Node()
        cluster = rpc_fixture.makeCluster(node.nodegroup, StartMonitors)
        monitor_timeout = random.randint(1, 100)
        node.start_transition_monitor(monitor_timeout)
        monitors = [{
            'deadline': now + timedelta(seconds=monitor_timeout),
            'id': node.system_id,
            'context': {
                'timeout': monitor_timeout,
                'node_status': node.status,
                },
            }]
        self.assertThat(
            cluster.StartMonitors, MockCalledOnceWith(ANY, monitors=monitors)
        )

    def test__start_transition_monitor_copes_with_timeouterror(self):
        now = datetime.now(tz=amp.utc)
        self.patch_datetime_now(now)
        node = factory.make_Node()
        monitor_start = self.patch(node_module.TransitionMonitor, "start")
        monitor_start.side_effect = crochet.TimeoutError("error")
        monitor_timeout = random.randint(1, 100)
        logger = self.useFixture(LoggerFixture("maas"))
        # start_transition_monitor() does not crash.
        node.start_transition_monitor(monitor_timeout)
        # However, the problem has been logged.
        self.assertDocTestMatches(
            "...: Unable to start transition monitor: ...",
            logger.output)


class TestClaimStaticIPAddresses(MAASServerTestCase):
    """Tests for `Node.claim_static_ip_addresses` and
    deallocate_static_ip_addresses"""

    def test__returns_empty_list_if_no_iface(self):
        node = factory.make_Node()
        self.assertEqual([], node.claim_static_ip_addresses())

    def test__returns_empty_list_if_no_iface_on_managed_network(self):
        node = factory.make_Node()
        factory.make_MACAddress(node=node)
        self.assertEqual([], node.claim_static_ip_addresses())

    def test__returns_mapping_for_iface_on_managed_network(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        static_mappings = node.claim_static_ip_addresses()
        [static_ip] = node.static_ip_addresses()
        [mac_address] = node.macaddress_set.all()
        self.assertEqual(
            [(static_ip, unicode(mac_address))],
            static_mappings)

    def test__returns_mapping_for_pxe_mac_interface(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        node.pxe_mac = factory.make_MACAddress(node=node)
        node.save()
        [managed_interface] = node.nodegroup.get_managed_interfaces()
        node.pxe_mac.cluster_interface = managed_interface
        node.pxe_mac.save()
        static_mappings = node.claim_static_ip_addresses()
        [static_ip] = node.static_ip_addresses()
        mac_address = node.get_pxe_mac()
        self.assertEqual(
            [(static_ip, unicode(mac_address))],
            static_mappings)

    def test__ignores_mac_address_with_non_auto_addresses(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        mac_address = node.macaddress_set.first()
        mac_address.claim_static_ips(IPADDRESS_TYPE.STICKY)
        self.assertRaises(
            StaticIPAddressTypeClash, mac_address.claim_static_ips)
        static_mappings = node.claim_static_ip_addresses()
        self.assertEqual([], static_mappings)

    def test__claims_and_releases_sticky_ip_address(self):
        remove_host_maps = self.patch_autospec(
            node_module, "remove_host_maps")
        user = factory.make_User()
        network = factory.make_ipv4_network(slash=24)
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            owner=user, status=NODE_STATUS.ALLOCATED, network=network)

        ngi = node.get_pxe_mac().cluster_interface
        static_range = ngi.get_static_ip_range()

        pxe_ip, pxe_mac = node.claim_static_ip_addresses(
            alloc_type=IPADDRESS_TYPE.STICKY)[0]

        self.expectThat(static_range, Contains(IPAddress(pxe_ip)))

        mac = MACAddress.objects.get(mac_address=pxe_mac)
        ip = mac.ip_addresses.first()
        self.expectThat(ip.ip, Equals(pxe_ip))
        self.expectThat(ip.alloc_type, Equals(IPADDRESS_TYPE.STICKY))

        deallocated = node.deallocate_static_ip_addresses(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=pxe_ip)

        self.expectThat(deallocated, HasLength(1))
        self.expectThat(deallocated, Equals(set([pxe_ip])))
        self.expectThat(remove_host_maps.call_count, Equals(1))

    def test__claims_specific_sticky_ip_address(self):
        user = factory.make_User()
        network = factory.make_ipv4_network(slash=24)
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            owner=user, status=NODE_STATUS.ALLOCATED, network=network)
        ngi = node.get_pxe_mac().cluster_interface
        first_ip = ngi.get_static_ip_range()[0]

        pxe_ip, pxe_mac = node.claim_static_ip_addresses(
            alloc_type=IPADDRESS_TYPE.STICKY, requested_address=first_ip)[0]
        mac = MACAddress.objects.get(mac_address=pxe_mac)
        ip = mac.ip_addresses.first()
        self.expectThat(IPAddress(ip.ip), Equals(first_ip))
        self.expectThat(ip.ip, Equals(pxe_ip))
        self.expectThat(ip.alloc_type, Equals(IPADDRESS_TYPE.STICKY))

    def test__claim_specific_sticky_ip_address_twice_fails(self):
        user = factory.make_User()
        network = factory.make_ipv4_network(slash=24)
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            owner=user, status=NODE_STATUS.ALLOCATED, network=network)
        node2 = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            owner=user, status=NODE_STATUS.ALLOCATED, network=network)
        ngi = node.get_pxe_mac().cluster_interface
        first_ip = ngi.get_static_ip_range()[0]

        node.claim_static_ip_addresses(
            alloc_type=IPADDRESS_TYPE.STICKY, requested_address=first_ip)
        with ExpectedException(StaticIPAddressUnavailable):
            node2.claim_static_ip_addresses(
                alloc_type=IPADDRESS_TYPE.STICKY, requested_address=first_ip)

    def test__claims_and_deallocates_multiple_sticky_ip_addresses(self):
        remove_host_maps = self.patch_autospec(
            node_module, "remove_host_maps")
        user = factory.make_User()
        network = factory.make_ipv4_network(slash=24)
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            owner=user, status=NODE_STATUS.ALLOCATED, network=network)
        cluster_if = node.get_primary_mac().cluster_interface

        macs = []
        for _ in range(3):
            mac = factory.make_MACAddress(
                node=node, cluster_interface=cluster_if)
            macs.append(mac)

        pxe_ip, pxe_mac = node.claim_static_ip_addresses(
            alloc_type=IPADDRESS_TYPE.STICKY)[0]

        mac = MACAddress.objects.get(mac_address=pxe_mac)
        ip = mac.ip_addresses.all()[0]
        self.expectThat(ip.ip, Equals(pxe_ip))
        self.expectThat(ip.alloc_type, Equals(IPADDRESS_TYPE.STICKY))

        sips = []
        for mac in macs:
            sips.append(node.claim_static_ip_addresses(
                mac=mac, alloc_type=IPADDRESS_TYPE.STICKY)[0])

        # try removing just the IP on the PXE MAC first
        deallocated = node.deallocate_static_ip_addresses(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=pxe_ip)

        self.expectThat(deallocated, HasLength(1))

        # try removing the remaining IP addresses now
        deallocated = node.deallocate_static_ip_addresses(
            alloc_type=IPADDRESS_TYPE.STICKY)
        self.expectThat(deallocated, HasLength(len(macs)))
        self.expectThat(remove_host_maps.call_count, Equals(2))


class TestDeploymentStatus(MAASServerTestCase):
    """Tests for node.get_deployment_status."""

    def test_returns_deploying_when_deploying(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        self.assertEqual("Deploying", node.get_deployment_status())

    def test_returns_deployed_when_deployed(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        self.assertEqual("Deployed", node.get_deployment_status())

    def test_returns_failed_deployment_when_failed_deployment(self):
        node = factory.make_Node(status=NODE_STATUS.FAILED_DEPLOYMENT)
        self.assertEqual("Failed deployment", node.get_deployment_status())

    def test_returns_not_deploying_otherwise(self):
        status = factory.pick_enum(
            NODE_STATUS, but_not=[
                NODE_STATUS.DEPLOYING, NODE_STATUS.DEPLOYED,
                NODE_STATUS.FAILED_DEPLOYMENT
                ]
            )
        node = factory.make_Node(status=status)
        self.assertEqual("Not in deployment", node.get_deployment_status())


class TestNode_Start(MAASServerTestCase):
    """Tests for Node.start()."""

    def setUp(self):
        super(TestNode_Start, self).setUp()
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        self.rpc_fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())

    def prepare_rpc_to_cluster(self, nodegroup):
        protocol = self.rpc_fixture.makeCluster(
            nodegroup, cluster_module.CreateHostMaps, cluster_module.PowerOn,
            cluster_module.StartMonitors)
        protocol.CreateHostMaps.side_effect = always_succeed_with({})
        protocol.StartMonitors.side_effect = always_succeed_with({})
        protocol.PowerOn.side_effect = always_succeed_with({})
        return protocol

    def make_acquired_node_with_mac(self, user, nodegroup=None):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            nodegroup=nodegroup, status=NODE_STATUS.READY)
        self.prepare_rpc_to_cluster(node.nodegroup)
        node.acquire(user)
        return node

    def test__sets_user_data(self):
        user = factory.make_User()
        nodegroup = factory.make_NodeGroup()
        self.prepare_rpc_to_cluster(nodegroup)
        node = self.make_acquired_node_with_mac(user, nodegroup)
        user_data = factory.make_bytes()

        with post_commit_hooks:
            node.start(user, user_data=user_data)

        nud = NodeUserData.objects.get(node=node)
        self.assertEqual(user_data, nud.data)

    def test__resets_user_data(self):
        user = factory.make_User()
        nodegroup = factory.make_NodeGroup()
        self.prepare_rpc_to_cluster(nodegroup)
        node = self.make_acquired_node_with_mac(user, nodegroup)
        user_data = factory.make_bytes()
        NodeUserData.objects.set_user_data(node, user_data)

        with post_commit_hooks:
            node.start(user, user_data=None)

        self.assertFalse(NodeUserData.objects.filter(node=node).exists())

    def test__claims_static_ip_addresses(self):
        user = factory.make_User()
        nodegroup = factory.make_NodeGroup()
        self.prepare_rpc_to_cluster(nodegroup)
        node = self.make_acquired_node_with_mac(user, nodegroup)

        claim_static_ip_addresses = self.patch_autospec(
            node, "claim_static_ip_addresses", spec_set=False)
        claim_static_ip_addresses.return_value = {}

        with post_commit_hooks:
            node.start(user)

        self.expectThat(node.claim_static_ip_addresses, MockAnyCall())

    def test__only_claims_static_addresses_when_allocated(self):
        user = factory.make_User()
        nodegroup = factory.make_NodeGroup()
        self.prepare_rpc_to_cluster(nodegroup)
        node = self.make_acquired_node_with_mac(user, nodegroup)
        node.status = NODE_STATUS.BROKEN
        node.save()

        claim_static_ip_addresses = self.patch_autospec(
            node, "claim_static_ip_addresses", spec_set=False)
        claim_static_ip_addresses.return_value = {}

        with post_commit_hooks:
            node.start(user)

        # No calls are made to claim_static_ip_addresses, since the node
        # isn't ALLOCATED.
        self.assertThat(claim_static_ip_addresses, MockNotCalled())

    def test__does_not_generate_host_maps_if_not_on_managed_interface(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_mac(user)
        self.patch(
            node, 'is_pxe_mac_on_managed_interface').return_value = False
        update_host_maps = self.patch(node_module, "update_host_maps")
        with post_commit_hooks:
            node.start(user)
        self.assertThat(update_host_maps, MockNotCalled())

    def test__updates_host_maps(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_mac(user)

        update_host_maps = self.patch(node_module, "update_host_maps")
        update_host_maps.return_value = []  # No failures.

        with post_commit_hooks:
            node.start(user)

        # Host maps are updated.
        self.assertThat(
            update_host_maps, MockCalledOnceWith({
                node.nodegroup: {
                    ip_address.ip: mac.mac_address
                    for ip_address in mac.ip_addresses.all()
                }
                for mac in node.mac_addresses_on_managed_interfaces()
            }))

    def test__propagates_errors_when_updating_host_maps(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_mac(user)

        exception_type = factory.make_exception_type()
        update_host_maps = self.patch(node_module, "update_host_maps")
        update_host_maps.return_value = [
            Failure(exception_type("Please, don't do that.")),
            ]

        self.assertRaises(exception_type, node.start, user)

    def test__updates_dns(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_mac(user)

        dns_update_zones = self.patch(dns_config, "dns_update_zones")

        with post_commit_hooks:
            node.start(user)

        self.assertThat(
            dns_update_zones, MockCalledOnceWith(node.nodegroup))

    def test__starts_nodes(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_mac(user)
        power_info = node.get_effective_power_info()

        start_transition_monitor = self.patch_autospec(
            node, 'start_transition_monitor')

        power_on_node = self.patch(node_module, "power_on_node")
        power_on_node.return_value = defer.succeed(None)

        with post_commit_hooks:
            node.start(user)

        # If the following fails the diff is big, but it's useful.
        self.maxDiff = None

        self.expectThat(power_on_node, MockCalledOnceWith(
            node.system_id, node.hostname, node.nodegroup.uuid,
            power_info))

        # A transition monitor was started.
        self.expectThat(
            start_transition_monitor, MockCalledOnceWith(
                node.get_deployment_time()))

    def test__raises_failures_when_power_action_fails(self):
        class PraiseBeToJTVException(Exception):
            """A nonsense exception for this test.

            (Though jtv is praiseworthy, and that's worth noting).
            """

        mock_getClientFor = self.patch(power_module, 'getClientFor')
        mock_getClientFor.return_value = defer.fail(
            PraiseBeToJTVException("Defiance is futile"))

        user = factory.make_User()
        node = self.make_acquired_node_with_mac(user)

        with ExpectedException(PraiseBeToJTVException):
            with post_commit_hooks:
                node.start(user)

    def test__marks_allocated_node_as_deploying(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_mac(user)
        with post_commit_hooks:
            node.start(user)
        self.assertEqual(
            NODE_STATUS.DEPLOYING, reload_object(node).status)

    def test__does_not_change_state_of_deployed_node(self):
        user = factory.make_User()
        # Create a node that we can execute power actions on, so that we
        # exercise the whole of start().
        node = factory.make_Node(
            power_type='ether_wake', status=NODE_STATUS.DEPLOYED,
            owner=user)
        factory.make_MACAddress(node=node)
        power_on_node = self.patch(node_module, "power_on_node")
        power_on_node.return_value = defer.succeed(None)
        with post_commit_hooks:
            node.start(user)
        self.assertEqual(
            NODE_STATUS.DEPLOYED, reload_object(node).status)

    def test__does_not_try_to_start_nodes_that_cant_be_started_by_MAAS(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_mac(user)
        power_info = PowerInfo(
            can_be_started=False,
            can_be_stopped=True,
            can_be_queried=True,
            power_type=node.get_effective_power_type(),
            power_parameters=node.get_effective_power_parameters(),
            )
        self.patch(node, 'get_effective_power_info').return_value = power_info
        power_on_node = self.patch(node_module, "power_on_node")
        node.start(user)
        self.assertThat(power_on_node, MockNotCalled())

    def test__does_not_start_nodes_the_user_cannot_edit(self):
        power_on_node = self.patch_autospec(node_module, "power_on_node")
        owner = factory.make_User()
        node = self.make_acquired_node_with_mac(owner)

        user = factory.make_User()
        self.assertRaises(PermissionDenied, node.start, user)
        self.assertThat(power_on_node, MockNotCalled())

    def test__allows_admin_to_start_any_node(self):
        power_on_node = self.patch_autospec(node_module, "power_on_node")
        owner = factory.make_User()
        node = self.make_acquired_node_with_mac(owner)

        admin = factory.make_admin()
        with post_commit_hooks:
            node.start(admin)

        self.expectThat(
            power_on_node, MockCalledOnceWith(
                node.system_id, node.hostname, node.nodegroup.uuid,
                node.get_effective_power_info()))

    def test__releases_static_ips_when_power_action_fails(self):
        exception_type = factory.make_exception_type()

        mock_getClientFor = self.patch(power_module, 'getClientFor')
        mock_getClientFor.return_value = defer.fail(
            exception_type("He's fallen in the water!"))

        deallocate_ips = self.patch(
            node_module.StaticIPAddress.objects, 'deallocate_by_node')

        user = factory.make_User()
        node = self.make_acquired_node_with_mac(user)

        with ExpectedException(exception_type):
            with post_commit_hooks:
                node.start(user)

        self.assertThat(deallocate_ips, MockCalledOnceWith(node))

    def test__releases_static_ips_when_update_host_maps_fails(self):
        exception_type = factory.make_exception_type()
        update_host_maps = self.patch(node_module, "update_host_maps")
        update_host_maps.return_value = [
            Failure(exception_type("You steaming nit, you!"))
            ]
        deallocate_ips = self.patch(
            node_module.StaticIPAddress.objects, 'deallocate_by_node')

        user = factory.make_User()
        node = self.make_acquired_node_with_mac(user)

        with ExpectedException(exception_type):
            with post_commit_hooks:
                node.start(user)

        self.assertThat(deallocate_ips, MockCalledOnceWith(node))

    def test_update_host_maps_updates_given_nodegroup_list(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_mac(user)

        update_host_maps = self.patch(node_module, "update_host_maps")
        update_host_maps.return_value = []  # No failures.

        claims = {mock.sentinel.ip: mock.sentinel.mac}
        # Create a bunch of nodegroups
        all_nodegroups = [factory.make_NodeGroup() for _ in range(5)]
        # Select some nodegroups.
        nodegroups = all_nodegroups[2:]
        node.update_host_maps(claims, nodegroups)

        # Host maps are updated.
        self.assertThat(
            update_host_maps, MockCalledOnceWith({
                nodegroup: claims
                for nodegroup in nodegroups
            }))


class TestNode_Stop(MAASServerTestCase):
    """Tests for Node.stop()."""

    def make_node_with_mac(self, user, nodegroup=None, power_type="virsh"):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            nodegroup=nodegroup, status=NODE_STATUS.READY,
            power_type=power_type)
        node.acquire(user)
        return node

    def test__stops_nodes(self):
        power_off_node = self.patch_autospec(node_module, "power_off_node")

        user = factory.make_User()
        node = self.make_node_with_mac(user)
        expected_power_info = node.get_effective_power_info()

        stop_mode = factory.make_name('stop-mode')
        expected_power_info.power_parameters['power_off_mode'] = stop_mode
        with post_commit_hooks:
            node.stop(user, stop_mode)

        # If the following fails the diff is big, but it's useful.
        self.maxDiff = None

        self.expectThat(
            power_off_node, MockCalledOnceWith(
                node.system_id, node.hostname, node.nodegroup.uuid,
                expected_power_info))

    def test__does_not_stop_nodes_the_user_cannot_edit(self):
        power_off_node = self.patch_autospec(node_module, "power_off_node")
        owner = factory.make_User()
        node = self.make_node_with_mac(owner)

        user = factory.make_User()
        self.assertRaises(PermissionDenied, node.stop, user)
        self.assertThat(power_off_node, MockNotCalled())

    def test__allows_admin_to_stop_any_node(self):
        power_off_node = self.patch_autospec(node_module, "power_off_node")
        owner = factory.make_User()
        node = self.make_node_with_mac(owner)
        expected_power_info = node.get_effective_power_info()

        stop_mode = factory.make_name('stop-mode')
        expected_power_info.power_parameters['power_off_mode'] = stop_mode

        admin = factory.make_admin()
        with post_commit_hooks:
            node.stop(admin, stop_mode)

        self.expectThat(
            power_off_node, MockCalledOnceWith(
                node.system_id, node.hostname, node.nodegroup.uuid,
                expected_power_info))

    def test__does_not_attempt_power_off_if_no_power_type(self):
        # If the node has a power_type set to UNKNOWN_POWER_TYPE, stop()
        # won't attempt to power it off.
        user = factory.make_User()
        node = self.make_node_with_mac(user)
        node.power_type = ""
        node.save()

        power_off_node = self.patch_autospec(node_module, "power_off_node")
        node.stop(user)
        self.assertThat(power_off_node, MockNotCalled())

    def test__does_not_attempt_power_off_if_cannot_be_stopped(self):
        # If the node has a power_type that doesn't allow MAAS to power
        # the node off, stop() won't attempt to send the power command.
        user = factory.make_User()
        node = self.make_node_with_mac(user, power_type="ether_wake")
        node.save()

        power_off_node = self.patch_autospec(node_module, "power_off_node")
        node.stop(user)
        self.assertThat(power_off_node, MockNotCalled())

    def test__propagates_failures_when_power_action_fails(self):
        fake_exception_type = factory.make_exception_type()

        mock_getClientFor = self.patch(power_module, 'getClientFor')
        mock_getClientFor.return_value = defer.fail(
            fake_exception_type("Soon be the weekend!"))

        user = factory.make_User()
        node = self.make_node_with_mac(user)

        with ExpectedException(fake_exception_type):
            with post_commit_hooks:
                node.stop(user)

    def test__returns_None_if_power_action_not_sent(self):
        user = factory.make_User()
        node = self.make_node_with_mac(user, power_type="")

        self.patch_autospec(node_module, "power_off_node")
        self.assertThat(node.stop(user), Is(None))

    def test__returns_Deferred_if_power_action_sent(self):
        user = factory.make_User()
        node = self.make_node_with_mac(user, power_type="virsh")

        self.patch_autospec(node_module, "power_off_node")
        with post_commit_hooks:
            self.assertThat(node.stop(user), IsInstance(defer.Deferred))
