# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
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
import threading

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.db import transaction
from fixtures import LoggerFixture
from maasserver import preseed as preseed_module
from maasserver.clusterrpc import power as power_module
from maasserver.clusterrpc.power_parameters import get_power_types
from maasserver.clusterrpc.testing.boot_images import make_rpc_boot_image
from maasserver.enum import (
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    INTERFACE_TYPE,
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
from maasserver.exceptions import NodeStateViolation
from maasserver.fields import MAC
from maasserver.models import (
    Config,
    Device,
    Interface,
    LicenseKey,
    Node,
    node as node_module,
    PhysicalInterface,
    UnknownInterface,
)
from maasserver.models.node import PowerInfo
from maasserver.models.signals import power as node_query
from maasserver.models.timestampedmodel import now
from maasserver.models.user import create_auth_token
from maasserver.node_status import (
    get_failed_status,
    MONITORED_STATUSES,
    NODE_FAILURE_STATUS_TRANSITIONS,
    NODE_TRANSITIONS,
)
from maasserver.rpc import monitors as monitors_module
from maasserver.rpc.testing.fixtures import MockLiveRegionToClusterRPCFixture
from maasserver.storage_layouts import (
    StorageLayoutError,
    StorageLayoutMissingBootDiskError,
)
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import (
    post_commit,
    post_commit_hooks,
)
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.twisted import always_succeed_with
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
from mock import (
    ANY,
    call,
    MagicMock,
    sentinel,
)
from provisioningserver.power import QUERY_POWER_TYPES
from provisioningserver.power.poweraction import UnknownPowerType
from provisioningserver.power.schema import JSON_POWER_TYPE_PARAMETERS
from provisioningserver.rpc import cluster as cluster_module
from provisioningserver.rpc.cluster import StartMonitors
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.utils.enum import (
    map_enum,
    map_enum_reverse,
)
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
from twisted.internet import (
    defer,
    reactor,
)
from twisted.internet.threads import deferToThread
from twisted.protocols import amp


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

    def test_get_boot_disk_returns_set_boot_disk(self):
        node = factory.make_Node()
        # First disk.
        factory.make_PhysicalBlockDevice(node=node)
        boot_disk = factory.make_PhysicalBlockDevice(node=node)
        node.boot_disk = boot_disk
        node.save()
        self.assertEquals(boot_disk, node.get_boot_disk())

    def test_get_boot_disk_returns_first(self):
        node = factory.make_Node()
        boot_disk = factory.make_PhysicalBlockDevice(node=node)
        # Second disk.
        factory.make_PhysicalBlockDevice(node=node)
        factory.make_PhysicalBlockDevice(node=node)
        self.assertEquals(boot_disk, node.get_boot_disk())

    def test_get_boot_disk_returns_None(self):
        node = factory.make_Node()
        self.assertIsNone(node.get_boot_disk())

    def test_get_bios_boot_method_returns_pxe(self):
        node = factory.make_Node(bios_boot_method="pxe")
        self.assertEquals("pxe", node.get_bios_boot_method())

    def test_get_bios_boot_method_returns_uefi(self):
        node = factory.make_Node(bios_boot_method="uefi")
        self.assertEquals("uefi", node.get_bios_boot_method())

    def test_get_bios_boot_method_fallback_to_pxe(self):
        node = factory.make_Node(bios_boot_method=factory.make_name("boot"))
        self.assertEquals("pxe", node.get_bios_boot_method())

    def test_add_node_with_token(self):
        user = factory.make_User()
        token = create_auth_token(user)
        node = factory.make_Node(token=token)
        self.assertEqual(token, node.token)

    def test_add_physical_interface(self):
        mac = factory.make_mac_address()
        node = factory.make_Node()
        node.add_physical_interface(mac)
        interfaces = PhysicalInterface.objects.filter(
            node=node, mac_address=mac).count()
        self.assertEqual(1, interfaces)

    def test_add_already_attached_mac_address_doesnt_raise_error(self):
        """Re-adding a MAC address should not fail"""
        node = factory.make_Node()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        mac = unicode(interface.mac_address)
        added_interface = node.add_physical_interface(mac)
        self.assertEqual(added_interface, interface)

    def test_add_physical_interface_attached_another_node_raises_error(self):
        """Adding a MAC address that's already in use in another node should
        fail"""
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node2)
        mac = unicode(interface.mac_address)
        self.assertRaises(
            ValidationError, node1.add_physical_interface, mac)

    def test_add_physical_interface_adds_interface(self):
        mac = factory.make_mac_address()
        node = factory.make_Node()
        node.add_physical_interface(mac)
        ifaces = PhysicalInterface.objects.filter(mac_address=mac)
        self.assertEqual(1, ifaces.count())
        self.assertEqual('eth0', ifaces.first().name)

    def test_add_physical_interface_adds_interfaces(self):
        node = factory.make_Node()
        node.add_physical_interface(factory.make_mac_address())
        node.add_physical_interface(factory.make_mac_address())
        ifaces = PhysicalInterface.objects.all()
        self.assertEqual(2, ifaces.count())
        self.assertEqual(
            ['eth0', 'eth1'], list(ifaces.order_by('id').values_list(
                'name', flat=True)))

    def test_add_physical_interface_adds_with_sequential_names(self):
        node = factory.make_Node()
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, name='eth4000')
        node.add_physical_interface(factory.make_mac_address())
        ifaces = PhysicalInterface.objects.all()
        self.assertEqual(2, ifaces.count())
        self.assertEqual(
            ['eth4000', 'eth4001'], list(ifaces.order_by('id').values_list(
                'name', flat=True)))

    def test_add_physical_interface_removes_matching_unknown_interface(self):
        mac = factory.make_mac_address()
        factory.make_Interface(INTERFACE_TYPE.UNKNOWN, mac_address=mac)
        node = factory.make_Node()
        node.add_physical_interface(mac)
        interfaces = PhysicalInterface.objects.filter(
            mac_address=mac).count()
        self.assertEqual(1, interfaces)
        interfaces = UnknownInterface.objects.filter(
            mac_address=mac).count()
        self.assertEqual(0, interfaces)

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

    def test_delete_node_deletes_related_interface(self):
        node = factory.make_Node()
        interface = node.add_physical_interface('AA:BB:CC:DD:EE:FF')
        node.delete()
        self.assertIsNone(reload_object(interface))

    def test_can_delete_allocated_node(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        system_id = node.system_id
        node.delete()
        self.assertItemsEqual([], Node.objects.filter(system_id=system_id))

    def test_set_random_hostname_set_hostname(self):
        node = factory.make_Node()
        original_hostname = node.hostname
        node.set_random_hostname()
        self.assertNotEqual(original_hostname, node.hostname)
        self.assertNotEqual("", node.hostname)

    def test_set_random_hostname_checks_hostname_existence(self):
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
        node.add_physical_interface(mac)
        self.assertEqual(
            mac, node.get_effective_power_parameters()['mac_address'])

    def test_get_effective_power_parameters_adds_no_mac_if_params_set(self):
        node = factory.make_Node(power_parameters={'foo': 'bar'})
        mac = factory.make_mac_address()
        node.add_physical_interface(mac)
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
        node = factory.make_Node(status=NODE_STATUS.READY, with_boot_disk=True)
        user = factory.make_User()
        token = create_auth_token(user)
        agent_name = factory.make_name('agent-name')
        node.acquire(user, token, agent_name)
        self.assertEqual(
            (user, NODE_STATUS.ALLOCATED, agent_name),
            (node.owner, node.status, node.agent_name))

    def test_acquire_calls_set_storage_layout(self):
        node = factory.make_Node(status=NODE_STATUS.READY, with_boot_disk=True)
        user = factory.make_User()
        token = create_auth_token(user)
        agent_name = factory.make_name('agent-name')
        mock_set_storage_layout = self.patch(node, "set_storage_layout")
        node.acquire(
            user, token, agent_name, storage_layout=sentinel.layout,
            storage_layout_params=sentinel.params)
        self.assertThat(
            mock_set_storage_layout,
            MockCalledOnceWith(sentinel.layout, params=sentinel.params))

    def test_set_storage_layout_calls_configure_on_layout(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        mock_get_layout = self.patch(
            node_module, "get_storage_layout_for_node")
        layout_object = MagicMock()
        mock_get_layout.return_value = layout_object
        allow_fallback = factory.pick_bool()
        node.set_storage_layout(
            sentinel.layout, sentinel.params, allow_fallback=allow_fallback)
        self.assertThat(
            mock_get_layout,
            MockCalledOnceWith(sentinel.layout, node, params=sentinel.params))
        self.assertThat(
            layout_object.configure,
            MockCalledOnceWith(allow_fallback=allow_fallback))

    def test_set_storage_layout_logs_success(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        mock_get_layout = self.patch(
            node_module, "get_storage_layout_for_node")
        maaslog = self.patch(node_module, 'maaslog')
        used_layout = factory.make_name("layout")
        layout_object = MagicMock()
        layout_object.configure.return_value = used_layout
        mock_get_layout.return_value = layout_object
        node.set_storage_layout(
            sentinel.layout, sentinel.params)
        self.assertThat(
            maaslog.info,
            MockCalledOnceWith(
                "%s: storage layout was set to %s.",
                node.hostname, used_layout))

    def test_set_storage_layout_logs_error_when_missing_boot_disk(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        mock_get_layout = self.patch(
            node_module, "get_storage_layout_for_node")
        maaslog = self.patch(node_module, 'maaslog')
        layout_object = MagicMock()
        layout_object.configure.side_effect = (
            StorageLayoutMissingBootDiskError())
        mock_get_layout.return_value = layout_object
        with ExpectedException(StorageLayoutMissingBootDiskError):
            node.set_storage_layout(
                sentinel.layout, sentinel.params)
        self.assertThat(
            maaslog.error,
            MockCalledOnceWith(
                "%s: missing boot disk; no storage layout can be "
                "applied.", node.hostname))

    def test_set_storage_layout_logs_error_when_layout_fails(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        mock_get_layout = self.patch(
            node_module, "get_storage_layout_for_node")
        maaslog = self.patch(node_module, 'maaslog')
        layout_object = MagicMock()
        exception = StorageLayoutError(factory.make_name("error"))
        layout_object.configure.side_effect = exception
        mock_get_layout.return_value = layout_object
        with ExpectedException(StorageLayoutError):
            node.set_storage_layout(
                sentinel.layout, sentinel.params)
        self.assertThat(
            maaslog.error,
            MockCalledOnceWith(
                "%s: failed to configure storage layout: %s",
                node.hostname, exception))

    def test_set_storage_layout_logs_error_when_unknown_layout(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        mock_get_layout = self.patch(
            node_module, "get_storage_layout_for_node")
        maaslog = self.patch(node_module, 'maaslog')
        mock_get_layout.return_value = None
        unknown_layout = factory.make_name("layout")
        with ExpectedException(StorageLayoutError):
            node.set_storage_layout(
                unknown_layout, sentinel.params)
        self.assertThat(
            maaslog.error,
            MockCalledOnceWith(
                "%s: unable to configure storage layout; unknown storage "
                "layout '%s'.", node.hostname, unknown_layout))

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
            node.system_id, status=NODE_STATUS.FAILED_DISK_ERASING))

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

    def test_start_disk_erasing_sets_status_on_post_commit_error(self):
        # When start_disk_erasing encounters an error in its post-commit hook,
        # it will set the node's status to FAILED_DISK_ERASING.
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        # Patch out some things that we don't want to do right now.
        self.patch(node, 'start').return_value = None
        # Fake an error during the post-commit hook.
        error_message = factory.make_name("error")
        error_type = factory.make_exception_type()
        _start_async = self.patch_autospec(node, "_start_disk_erasing_async")
        _start_async.side_effect = error_type(error_message)
        # Capture calls to _set_status.
        self.patch_autospec(Node, "_set_status")

        with LoggerFixture("maas") as logger:
            with ExpectedException(error_type):
                with post_commit_hooks:
                    node.start_disk_erasing(admin)

        # The status is set to be reverted to its initial status.
        self.assertThat(node._set_status, MockCalledOnceWith(
            node, node.system_id, status=NODE_STATUS.FAILED_DISK_ERASING))
        # It's logged too.
        self.assertThat(logger.output, Contains(
            "%s: Could not start node for disk erasure: %s\n"
            % (node.hostname, error_message)))

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

    def test_abort_operation_aborts_deployment(self):
        agent_name = factory.make_name('agent-name')
        user = factory.make_admin()
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            agent_name=agent_name)
        abort_deploying = self.patch_autospec(node, 'abort_deploying')
        node.abort_operation(user)
        self.assertThat(abort_deploying, MockCalledOnceWith(user))

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
            node_module.post_commit_do, MockCallsMatch(
                # A call to power off the node is first scheduled.
                call(
                    node_module.power_off_node, node.system_id, node.hostname,
                    node.nodegroup.uuid, expected_power_info),
                # Also a call to deallocate AUTO IP addresses.
                call(
                    reactor.callLater, 0, deferToThread,
                    node.release_auto_ips),
            ))

    def test_release_node_that_has_power_off(self):
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=owner, agent_name=agent_name)
        self.patch(node, 'stop')
        self.patch(node, 'start_transition_monitor')
        node.power_state = POWER_STATE.OFF
        with post_commit_hooks:
            node.release()
        self.expectThat(node.stop, MockNotCalled())
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
        with post_commit_hooks:
            node.release()
        self.assertEquals(
            [], list(NodeResult.objects.filter(
                node=node, result_type=RESULT_TYPE.INSTALLATION)))

    def test_dynamic_ip_addresses_from_ip_address_table(self):
        node = factory.make_Node()
        interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            for _ in range(3)
        ]
        ip_addresses = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, interface=interface)
            for interface in interfaces[:2]
        ]
        # Empty ip should not appear
        factory.make_StaticIPAddress(
            ip="", alloc_type=IPADDRESS_TYPE.DISCOVERED,
            interface=interfaces[2])
        self.assertItemsEqual(
            [ip.ip for ip in ip_addresses], node.dynamic_ip_addresses())

    def test_static_ip_addresses_returns_static_ip_addresses(self):
        node = factory.make_Node()
        [interface1, interface2] = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            for _ in range(2)
        ]
        ip1 = factory.make_StaticIPAddress(interface=interface1)
        ip2 = factory.make_StaticIPAddress(interface=interface2)
        # Create another node with a static IP address.
        other_node = factory.make_Node(
            nodegroup=node.nodegroup, interface=True)
        factory.make_StaticIPAddress(interface=other_node.get_boot_interface())
        self.assertItemsEqual([ip1.ip, ip2.ip], node.static_ip_addresses())

    def test_ip_addresses_returns_static_ip_addresses_if_allocated(self):
        # If both static and dynamic IP addresses are present, the static
        # addresses take precedence: they are allocated and deallocated in
        # a synchronous fashion whereas the dynamic addresses are updated
        # periodically.
        node = factory.make_Node(interface=True, disable_ipv4=False)
        interface = node.get_boot_interface()
        ip = factory.make_StaticIPAddress(interface=interface)
        self.assertItemsEqual([ip.ip], node.ip_addresses())

    def test_ip_addresses_returns_dynamic_ip_if_no_static_ip(self):
        node = factory.make_Node(disable_ipv4=False)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, interface=interface)
        self.assertItemsEqual([ip.ip], node.ip_addresses())

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

    def test_get_interfaces_returns_all_connected_interfaces(self):
        node = factory.make_Node()
        phy1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        phy2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        phy3 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        vlan = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[phy1])
        bond = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[phy2, phy3])
        vlan_bond = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[bond])

        self.assertItemsEqual(
            [phy1, phy2, phy3, vlan, bond, vlan_bond],
            node.interface_set.all())

    def test_get_interfaces_ignores_interface_on_other_nodes(self):
        other_node = factory.make_Node()
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=other_node)
        node = factory.make_Node()
        phy = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        vlan = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[phy])

        self.assertItemsEqual(
            [phy, vlan], node.interface_set.all())

    def test_get_interface_names_returns_interface_name(self):
        node = factory.make_Node()
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, name="eth0")
        self.assertEquals(['eth0'], node.get_interface_names())

    def test_get_next_ifname_names_returns_sane_default(self):
        node = factory.make_Node()
        self.assertEquals('eth0', node.get_next_ifname(ifnames=[]))

    def test_get_next_ifname_names_returns_next_available(self):
        node = factory.make_Node()
        self.assertEquals('eth2', node.get_next_ifname(
            ifnames=['eth0', 'eth1']))

    def test_get_next_ifname_names_returns_next_in_sequence(self):
        node = factory.make_Node()
        self.assertEquals('eth12', node.get_next_ifname(
            ifnames=['eth10', 'eth11']))

    def test_release_turns_on_netboot(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        node.set_netboot(on=False)
        with post_commit_hooks:
            node.release()
        self.assertTrue(node.netboot)

    def test_release_clears_osystem_and_distro_series(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        node.osystem = factory.make_name('os')
        node.distro_series = factory.make_name('series')
        with post_commit_hooks:
            node.release()
        self.assertEqual("", node.osystem)
        self.assertEqual("", node.distro_series)

    def test_release_powers_off_node_when_on(self):
        user = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=user, power_type='virsh',
            power_state=POWER_STATE.ON)
        self.patch(node, 'start_transition_monitor')
        node_stop = self.patch(node, 'stop')
        node.release()
        self.assertThat(
            node_stop, MockCalledOnceWith(user))

    def test_release_doesnt_power_off_node_when_off(self):
        user = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=user, power_type='virsh',
            power_state=POWER_STATE.OFF)
        self.patch(node, 'start_transition_monitor')
        node_stop = self.patch(node, 'stop')
        with post_commit_hooks:
            node.release()
        self.assertThat(node_stop, MockNotCalled())

    def test_release_releases_auto_ips_when_node_is_off(self):
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=user, status=NODE_STATUS.ALLOCATED,
            power_state=POWER_STATE.OFF)
        release_auto_ips_later = self.patch_autospec(
            node, "release_auto_ips_later")
        self.patch(node, 'start_transition_monitor')
        node.release()
        self.assertThat(
            release_auto_ips_later, MockCalledOnceWith())

    def test_release_release_auto_ips_when_node_cannot_be_queried(self):
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=user, status=NODE_STATUS.ALLOCATED,
            power_state=POWER_STATE.ON, power_type='ether_wake')
        release_auto_ips_later = self.patch_autospec(
            node, "release_auto_ips_later")
        self.patch(node, 'start_transition_monitor')
        node.release()
        self.assertThat(
            release_auto_ips_later, MockCalledOnceWith())

    def test_release_doesnt_release_auto_ips_when_node_releasing(self):
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=user, status=NODE_STATUS.ALLOCATED,
            power_state=POWER_STATE.ON, power_type='virsh')
        release_auto_ips_later = self.patch_autospec(
            node, "release_auto_ips_later")
        self.patch_autospec(node, 'stop')
        self.patch(node, 'start_transition_monitor')
        node.release()
        self.assertThat(
            release_auto_ips_later, MockNotCalled())

    def test_release_logs_and_raises_errors_in_stopping(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, power_state=POWER_STATE.ON)
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
            power_state=POWER_STATE.ON,
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

    def test_release_calls__clear_storage_configuration(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        mock_clear = self.patch(node, "_clear_storage_configuration")
        with post_commit_hooks:
            node.release()
        self.assertThat(mock_clear, MockCalledOnceWith())

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
            interface=True, status=NODE_STATUS.NEW, power_type='ether_wake')
        node_start = self.patch(node, 'start')
        # Return a post-commit hook from Node.start().
        node_start.side_effect = lambda user, user_data: post_commit()
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

    def test_start_commissioning_reverts_status_on_post_commit_error(self):
        # When start_commissioning encounters an error in its post-commit
        # hook, it will revert the node to its previous status.
        admin = factory.make_admin()
        status = random.choice(
            (NODE_STATUS.NEW, NODE_STATUS.READY,
             NODE_STATUS.FAILED_COMMISSIONING))
        node = factory.make_Node(status=status)
        # Patch out some things that we don't want to do right now.
        self.patch(node, '_start_transition_monitor_async')
        self.patch(node, 'start').return_value = None
        # Fake an error during the post-commit hook.
        error_message = factory.make_name("error")
        error_type = factory.make_exception_type()
        _start_async = self.patch_autospec(node, "_start_commissioning_async")
        _start_async.side_effect = error_type(error_message)
        # Capture calls to _set_status.
        self.patch_autospec(Node, "_set_status")

        with LoggerFixture("maas") as logger:
            with ExpectedException(error_type):
                with post_commit_hooks:
                    node.start_commissioning(admin)

        # The status is set to be reverted to its initial status.
        self.assertThat(node._set_status, MockCalledOnceWith(
            node, node.system_id, status=status))
        # It's logged too.
        self.assertThat(logger.output, Contains(
            "%s: Could not start node for commissioning: %s\n"
            % (node.hostname, error_message)))

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
            node.system_id, status=NODE_STATUS.NEW))

    def test_abort_commissioning_errors_if_node_is_not_commissioning(self):
        unaccepted_statuses = set(map_enum(NODE_STATUS).values())
        unaccepted_statuses.remove(NODE_STATUS.COMMISSIONING)
        for status in unaccepted_statuses:
            node = factory.make_Node(
                status=status, power_type='virsh')
            self.assertRaises(
                NodeStateViolation, node.abort_commissioning,
                factory.make_admin())

    def test_start_commissioning_sets_owner(self):
        node = factory.make_Node(
            status=NODE_STATUS.NEW, power_type='ether_wake',
            enable_ssh=True)
        node_start = self.patch(node, 'start')
        # Return a post-commit hook from Node.start().
        node_start.side_effect = lambda user, user_data: post_commit()
        admin = factory.make_admin()
        node.start_commissioning(admin)
        post_commit_hooks.reset()  # Ignore these for now.
        node = reload_object(node)
        expected_attrs = {
            'status': NODE_STATUS.COMMISSIONING,
            'owner': admin,
        }
        self.expectThat(node.owner, Equals(admin))
        self.assertAttributes(node, expected_attrs)

    def test_abort_commissioning_unsets_owner(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, power_type='virsh',
            enable_ssh=True)
        admin = factory.make_admin()

        node_stop = self.patch(node, 'stop')
        # Return a post-commit hook from Node.stop().
        node_stop.side_effect = lambda user: post_commit()
        self.patch(Node, "_set_status")

        with post_commit_hooks:
            node.abort_commissioning(admin)

        self.assertThat(node_stop, MockCalledOnceWith(admin))
        self.assertThat(node._set_status, MockCalledOnceWith(
            node.system_id, status=NODE_STATUS.NEW))
        self.assertThat(node.owner, Is(None))

    def test_full_clean_logs_node_status_transition(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING, owner=factory.make_User())
        node.status = NODE_STATUS.DEPLOYED

        with LoggerFixture("maas") as logger:
            node.full_clean()

        stat = map_enum_reverse(NODE_STATUS)
        self.assertThat(logger.output.strip(), Equals(
            "%s: Status transition from %s to %s" % (
                node.hostname, stat[NODE_STATUS.DEPLOYING],
                stat[NODE_STATUS.DEPLOYED])
            )
        )

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

    def test_fqdn_if_dns_not_managed_and_has_domain_name(self):
        nodegroup = factory.make_NodeGroup(
            name=factory.make_string(),
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        hostname_with_domain = '%s.%s' % (
            factory.make_string(), factory.make_string())
        node = factory.make_Node(
            nodegroup=nodegroup, hostname=hostname_with_domain)
        self.assertEqual(hostname_with_domain, node.fqdn)

    def test_fqdn_if_dns_not_managed_and_no_domain_name(self):
        domain = factory.make_name('domain')
        nodegroup = factory.make_NodeGroup(
            name=domain,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        hostname_without_domain = factory.make_string()
        node = factory.make_Node(
            nodegroup=nodegroup, hostname=hostname_without_domain)
        self.assertEqual(
            "%s.%s" % (hostname_without_domain, domain), node.fqdn)

    def test_fqdn_replaces_hostname_if_dns_is_managed(self):
        hostname_without_domain = factory.make_name('hostname')
        hostname_with_domain = '%s.%s' % (
            hostname_without_domain, factory.make_string())
        domain = factory.make_name('domain')
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            name=domain,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        node = factory.make_Node(
            hostname=hostname_with_domain, nodegroup=nodegroup)
        expected_hostname = '%s.%s' % (hostname_without_domain, domain)
        self.assertEqual(expected_hostname, node.fqdn)

    def test_boot_type_has_fastpath_set_by_default(self):
        node = Node()
        self.assertEqual(NODE_BOOT.FASTPATH, node.boot_type)

    def test_split_arch_returns_arch_as_tuple(self):
        main_arch = factory.make_name('arch')
        sub_arch = factory.make_name('subarch')
        full_arch = '%s/%s' % (main_arch, sub_arch)
        node = factory.make_Node(architecture=full_arch)
        self.assertEqual((main_arch, sub_arch), node.split_arch())

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

    def test_update_power_state_sets_last_updated_field(self):
        node = factory.make_Node(power_state_updated=None)
        self.assertIsNone(node.power_state_updated)
        state = factory.pick_enum(POWER_STATE)
        node.update_power_state(state)
        self.assertEqual(now(), reload_object(node).power_state_updated)

    def test_update_power_state_readies_node_if_releasing(self):
        node = factory.make_Node(
            power_state=POWER_STATE.ON, status=NODE_STATUS.RELEASING,
            owner=None)
        self.patch(node, 'stop_transition_monitor')
        with post_commit_hooks:
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
        with post_commit_hooks:
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

    def test_update_power_state_release_auto_ips_if_releasing(self):
        node = factory.make_Node(
            power_state=POWER_STATE.ON, status=NODE_STATUS.RELEASING,
            owner=None)
        release_auto_ips_later = self.patch_autospec(
            node, 'release_auto_ips_later')
        self.patch(node, 'stop_transition_monitor')
        node.update_power_state(POWER_STATE.OFF)
        self.assertThat(
            release_auto_ips_later, MockCalledOnceWith())

    def test_update_power_state_doesnt_release_auto_ips_if_not_off(self):
        node = factory.make_Node(
            power_state=POWER_STATE.OFF, status=NODE_STATUS.ALLOCATED)
        release_auto_ips_later = self.patch_autospec(
            node, 'release_auto_ips_later')
        node.update_power_state(POWER_STATE.ON)
        self.assertThat(release_auto_ips_later, MockNotCalled())

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

    def test_boot_interface_default_is_none(self):
        node = factory.make_Node()
        self.assertIsNone(node.boot_interface)

    def test_get_boot_interface_returns_boot_interface_if_set(self):
        node = factory.make_Node(interface=True)
        node.boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        node.save()
        self.assertEqual(node.boot_interface, node.get_boot_interface())

    def test_get_boot_interface_returns_first_interface_if_unset(self):
        node = factory.make_Node(interface=True)
        for _ in range(3):
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        self.assertEqual(
            node.interface_set.order_by('id').first(),
            node.get_boot_interface())

    def test_boot_interface_deletion_does_not_delete_node(self):
        node = factory.make_Node(interface=True)
        node.boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        node.save()
        node.boot_interface.delete()
        self.assertThat(reload_object(node), Not(Is(None)))

    def test_get_pxe_mac_vendor_returns_vendor(self):
        node = factory.make_Node()
        node.boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, mac_address='ec:a8:6b:fd:ae:3f',
            node=node)
        node.save()
        self.assertEqual(
            "ELITEGROUP COMPUTER SYSTEMS CO., LTD.",
            node.get_pxe_mac_vendor())

    def test_get_extra_macs_returns_all_but_boot_interface_mac(self):
        node = factory.make_Node()
        interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            for _ in xrange(3)
        ]
        # Do not set the boot interface to the first interface to make sure the
        # boot interface (and not the first created) is excluded from the list
        # returned by `get_extra_macs`.
        boot_interface_index = 1
        node.boot_interface = interfaces[boot_interface_index]
        node.save()
        del interfaces[boot_interface_index]
        self.assertItemsEqual([
            interface.mac_address
            for interface in interfaces
            ], node.get_extra_macs())

    def test_get_extra_macs_returns_all_but_first_interface_if_not_boot(self):
        node = factory.make_Node()
        interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            for _ in xrange(3)
        ]
        self.assertItemsEqual([
            interface.mac_address
            for interface in interfaces[1:]
            ], node.get_extra_macs())

    def test__clear_storage_configuration_removes_all_related_objects(self):
        node = factory.make_Node()
        physical_block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000 ** 3)
            for _ in range(3)
            ]
        filesystem = factory.make_Filesystem(
            block_device=physical_block_devices[0])
        partition_table = factory.make_PartitionTable(
            block_device=physical_block_devices[1])
        partition = factory.make_Partition(partition_table=partition_table)
        fslvm = factory.make_Filesystem(
            block_device=physical_block_devices[2],
            fstype=FILESYSTEM_TYPE.LVM_PV)
        vgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, filesystems=[fslvm])
        vbd1 = factory.make_VirtualBlockDevice(
            filesystem_group=vgroup, size=2 * 1000 ** 3)
        vbd2 = factory.make_VirtualBlockDevice(
            filesystem_group=vgroup, size=3 * 1000 ** 3)
        filesystem_on_vbd1 = factory.make_Filesystem(
            block_device=vbd1, fstype=FILESYSTEM_TYPE.LVM_PV)
        vgroup_on_vgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            filesystems=[filesystem_on_vbd1])
        vbd3_on_vbd1 = factory.make_VirtualBlockDevice(
            filesystem_group=vgroup_on_vgroup, size=1 * 1000 ** 3)
        node._clear_storage_configuration()
        for pbd in physical_block_devices:
            self.expectThat(
                reload_object(pbd), Not(Is(None)),
                "Physical block device should not have been deleted.")
        self.expectThat(
            reload_object(filesystem), Is(None),
            "Filesystem should have been removed.")
        self.expectThat(
            reload_object(partition_table), Is(None),
            "PartitionTable should have been removed.")
        self.expectThat(
            reload_object(partition), Is(None),
            "Partition should have been removed.")
        self.expectThat(
            reload_object(fslvm), Is(None),
            "LVM PV Filesystem should have been removed.")
        self.expectThat(
            reload_object(vgroup), Is(None),
            "Volume group should have been removed.")
        self.expectThat(
            reload_object(vbd1), Is(None),
            "Virtual block device should have been removed.")
        self.expectThat(
            reload_object(vbd2), Is(None),
            "Virtual block device should have been removed.")
        self.expectThat(
            reload_object(filesystem_on_vbd1), Is(None),
            "Filesystem on virtual block device should have been removed.")
        self.expectThat(
            reload_object(vgroup_on_vgroup), Is(None),
            "Volume group on virtual block device should have been removed.")
        self.expectThat(
            reload_object(vbd3_on_vbd1), Is(None),
            "Virtual block device on another virtual block device should have "
            "been removed.")

    def test_boot_interface_displays_error_if_not_hosts_interface(self):
        node0 = factory.make_Node(interface=True)
        node1 = factory.make_Node()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node1)
        node0.boot_interface = interface
        exception = self.assertRaises(ValidationError, node0.save)
        msg = {'boot_interface': ["Must be one of the node's interfaces."]}
        self.assertEqual(msg, exception.message_dict)

    def test_boot_interface_accepts_valid_interface(self):
        node = factory.make_Node()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        node.boot_interface = interface
        node.save()


class TestNodeIsBootInterfaceOnManagedInterface(MAASServerTestCase):

    def test__returns_true_if_managed(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        self.assertTrue(node.is_boot_interface_on_managed_interface())

    def test__returns_false_if_no_boot_interface(self):
        node = factory.make_Node()
        self.assertFalse(node.is_boot_interface_on_managed_interface())

    def test__returns_false_if_no_attached_cluster_interface(self):
        node = factory.make_Node()
        node.boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        node.save()
        self.assertFalse(node.is_boot_interface_on_managed_interface())

    def test__returns_false_if_cluster_interface_unmanaged(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        self.assertFalse(node.is_boot_interface_on_managed_interface())


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
        with post_commit_hooks:
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
        done = threading.Event()
        rpc_fixture = self.prepare_rpc()
        now = datetime.now(tz=amp.utc)
        self.patch_datetime_now(now)
        node = factory.make_Node()

        def handle(self, monitors):
            done.set()  # Tell the calling thread.
            return defer.succeed({})

        cluster = rpc_fixture.makeCluster(node.nodegroup, StartMonitors)
        cluster.StartMonitors.side_effect = handle

        monitor_timeout = random.randint(1, 100)
        node.start_transition_monitor(monitor_timeout)
        post_commit_hooks.fire()

        self.assertTrue(done.wait(5))
        self.assertThat(
            cluster.StartMonitors,
            MockCalledOnceWith(ANY, monitors=[{
                'deadline': now + timedelta(seconds=monitor_timeout),
                'id': node.system_id,
                'context': {
                    'timeout': monitor_timeout,
                    'node_status': node.status,
                },
            }]))


class TestNodeNetworking(MAASServerTestCase):
    """Tests for methods on the `Node` related to networking."""

    def test_release_leases_calls_remove_host_maps_with_leases(self):
        node = factory.make_Node()
        interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            for _ in range(3)
        ]
        removal_mappings = {}
        for interface in interfaces:
            subnet = factory.make_Subnet(vlan=interface.vlan)
            nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
            factory.make_NodeGroupInterface(
                nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
                subnet=subnet)
            lease_ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=lease_ip,
                subnet=subnet, interface=interface)
            removal_mappings[nodegroup] = set([lease_ip])
        mock_remove_host_maps = self.patch(node_module, "remove_host_maps")
        node.release_leases()
        self.assertThat(
            mock_remove_host_maps, MockCalledOnceWith(removal_mappings))

    def test_claim_auto_ips_calls_claim_auto_ips_on_all_interfaces(self):
        node = factory.make_Node()
        interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            for _ in range(3)
        ]
        mock_claim_auto_ips = self.patch_autospec(Interface, "claim_auto_ips")
        node.claim_auto_ips()
        # Since the interfaces are not ordered, which they dont need to be
        # we extract the passed interface to each call.
        observed_interfaces = [
            call[0][0]
            for call in mock_claim_auto_ips.call_args_list
        ]
        self.assertItemsEqual(interfaces, observed_interfaces)

    def test_release_auto_ips_calls_release_auto_ips_on_all_interfaces(self):
        node = factory.make_Node()
        interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            for _ in range(3)
        ]
        mock_release_auto_ips = self.patch_autospec(
            Interface, "release_auto_ips")
        node.release_auto_ips()
        # Since the interfaces are not ordered, which they dont need to be
        # we extract the passed interface to each call.
        observed_interfaces = [
            call[0][0]
            for call in mock_release_auto_ips.call_args_list
        ]
        self.assertItemsEqual(interfaces, observed_interfaces)

    def test_release_auto_ips_later_calls_with_post_commit_do(self):
        mock_post_commit_do = self.patch_autospec(
            node_module, "post_commit_do")
        node = factory.make_Node()
        node.release_auto_ips_later()
        self.assertThat(
            mock_post_commit_do,
            MockCalledOnceWith(
                reactor.callLater, 0,
                deferToThread, node.release_auto_ips))

    def test__clear_networking_configuration(self):
        node = factory.make_Node()
        nic0 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        nic1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        dhcp_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP, ip="", interface=nic0)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=nic0)
        auto_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="", interface=nic1)
        mock_unlink_ip_address = self.patch_autospec(
            Interface, "unlink_ip_address")
        node._clear_networking_configuration()
        # Since the interfaces are not ordered, which they dont need to be
        # we extract the passed interface to each call.
        observed_interfaces = set(
            call[0][0]
            for call in mock_unlink_ip_address.call_args_list
        )
        # Since the IP address are not ordered, which they dont need to be
        # we extract the passed IP address to each call.
        observed_ip_address = [
            call[0][1]
            for call in mock_unlink_ip_address.call_args_list
        ]
        # Check that clearing_config is always sent as true.
        clearing_config = set(
            call[1]['clearing_config']
            for call in mock_unlink_ip_address.call_args_list
        )
        self.assertItemsEqual([nic0, nic1], observed_interfaces)
        self.assertItemsEqual(
            [dhcp_ip, static_ip, auto_ip], observed_ip_address)
        self.assertEquals(set([True]), clearing_config)

    def test_set_initial_networking_configuration_auto_on_boot_nic(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        boot_interface = node.get_boot_interface()
        subnet = boot_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.DISCOVERED).first().subnet
        node._clear_networking_configuration()
        node.set_initial_networking_configuration()
        boot_interface = reload_object(boot_interface)
        auto_ip = boot_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO).first()
        self.assertIsNotNone(auto_ip)
        self.assertEquals(subnet, auto_ip.subnet)

    def test_set_initial_networking_configuration_auto_on_managed_subnet(self):
        node = factory.make_Node()
        boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        subnet = factory.make_Subnet(vlan=boot_interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        node.set_initial_networking_configuration()
        boot_interface = reload_object(boot_interface)
        auto_ip = boot_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO).first()
        self.assertIsNotNone(auto_ip)
        self.assertEquals(subnet, auto_ip.subnet)

    def test_set_initial_networking_configuration_link_up_on_enabled(self):
        node = factory.make_Node()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        enabled_interfaces = [
            factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=node, enabled=True)
            for _ in range(3)
        ]
        for _ in range(3):
            factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=node, enabled=False)
        mock_ensure_link_up = self.patch_autospec(Interface, "ensure_link_up")
        node.set_initial_networking_configuration()
        # Since the interfaces are not ordered, which they dont need to be
        # we extract the passed interface to each call.
        observed_interfaces = set(
            call[0][0]
            for call in mock_ensure_link_up.call_args_list
        )
        self.assertItemsEqual(enabled_interfaces, observed_interfaces)


class TestGetBestGuessForDefaultGateways(MAASServerTestCase):
    """Tests for `Node.get_best_guess_for_default_gateways`."""

    def test__simple(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY, disable_ipv4=False)
        boot_interface = node.get_boot_interface()
        managed_subnet = boot_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO).first().subnet
        gateway_ip = managed_subnet.gateway_ip
        self.assertEquals(
            [(boot_interface.id, managed_subnet.id, gateway_ip)],
            node.get_best_guess_for_default_gateways())

    def test__ipv4_and_ipv6(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        node = factory.make_Node(
            status=NODE_STATUS.READY, nodegroup=nodegroup, disable_ipv4=False)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=unicode(network_v4.cidr))
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet_v4)
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=unicode(network_v6.cidr))
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet_v6)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v4),
            subnet=subnet_v4, interface=interface)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v6),
            subnet=subnet_v6, interface=interface)
        self.assertItemsEqual([
            (interface.id, subnet_v4.id, subnet_v4.gateway_ip),
            (interface.id, subnet_v6.id, subnet_v6.gateway_ip),
            ], node.get_best_guess_for_default_gateways())

    def test__only_one(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY, disable_ipv4=False)
        boot_interface = node.get_boot_interface()
        managed_subnet = boot_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO).first().subnet
        # Give it two IP addresses on the same subnet.
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(managed_subnet.get_ipnetwork()),
            subnet=managed_subnet, interface=boot_interface)
        gateway_ip = managed_subnet.gateway_ip
        self.assertEquals(
            [(boot_interface.id, managed_subnet.id, gateway_ip)],
            node.get_best_guess_for_default_gateways())

    def test__managed_subnet_over_unmanaged(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        node = factory.make_Node(
            status=NODE_STATUS.READY, nodegroup=nodegroup, disable_ipv4=False)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        unmanaged_network = factory.make_ipv4_network()
        unmanaged_subnet = factory.make_Subnet(
            cidr=unicode(unmanaged_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(unmanaged_network),
            subnet=unmanaged_subnet, interface=interface)
        managed_network = factory.make_ipv4_network()
        managed_subnet = factory.make_Subnet(
            cidr=unicode(managed_network.cidr))
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=managed_subnet)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(managed_network),
            subnet=managed_subnet, interface=interface)
        gateway_ip = managed_subnet.gateway_ip
        self.assertEquals(
            [(interface.id, managed_subnet.id, gateway_ip)],
            node.get_best_guess_for_default_gateways())

    def test__bond_over_physical_interface(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        node = factory.make_Node(
            status=NODE_STATUS.READY, nodegroup=nodegroup, disable_ipv4=False)
        physical_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        physical_network = factory.make_ipv4_network()
        physical_subnet = factory.make_Subnet(
            cidr=unicode(physical_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(physical_network),
            subnet=physical_subnet, interface=physical_interface)
        parent_interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            for _ in range(2)
        ]
        bond_interface = factory.make_Interface(
            INTERFACE_TYPE.BOND, node=node, parents=parent_interfaces)
        bond_network = factory.make_ipv4_network()
        bond_subnet = factory.make_Subnet(
            cidr=unicode(bond_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(bond_network),
            subnet=bond_subnet, interface=bond_interface)
        gateway_ip = bond_subnet.gateway_ip
        self.assertEquals(
            [(bond_interface.id, bond_subnet.id, gateway_ip)],
            node.get_best_guess_for_default_gateways())

    def test__physical_over_vlan_interface(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        node = factory.make_Node(
            status=NODE_STATUS.READY, nodegroup=nodegroup, disable_ipv4=False)
        physical_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        physical_network = factory.make_ipv4_network()
        physical_subnet = factory.make_Subnet(
            cidr=unicode(physical_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(physical_network),
            subnet=physical_subnet, interface=physical_interface)
        vlan_interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, node=node, parents=[physical_interface])
        vlan_network = factory.make_ipv4_network()
        vlan_subnet = factory.make_Subnet(
            cidr=unicode(vlan_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(vlan_network),
            subnet=vlan_subnet, interface=vlan_interface)
        gateway_ip = physical_subnet.gateway_ip
        self.assertEquals(
            [(physical_interface.id, physical_subnet.id, gateway_ip)],
            node.get_best_guess_for_default_gateways())

    def test__boot_interface_over_other_interfaces(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        node = factory.make_Node(
            status=NODE_STATUS.READY, nodegroup=nodegroup, disable_ipv4=False)
        physical_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        physical_network = factory.make_ipv4_network()
        physical_subnet = factory.make_Subnet(
            cidr=unicode(physical_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(physical_network),
            subnet=physical_subnet, interface=physical_interface)
        boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        boot_network = factory.make_ipv4_network()
        boot_subnet = factory.make_Subnet(
            cidr=unicode(boot_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(boot_network),
            subnet=boot_subnet, interface=boot_interface)
        node.boot_interface = boot_interface
        node.save()
        gateway_ip = boot_subnet.gateway_ip
        self.assertEquals(
            [(boot_interface.id, boot_subnet.id, gateway_ip)],
            node.get_best_guess_for_default_gateways())

    def test__sticky_ip_over_user_reserved(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        node = factory.make_Node(
            status=NODE_STATUS.READY, nodegroup=nodegroup, disable_ipv4=False)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        sticky_network = factory.make_ipv4_network()
        sticky_subnet = factory.make_Subnet(
            cidr=unicode(sticky_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(sticky_network),
            subnet=sticky_subnet, interface=interface)
        user_reserved_network = factory.make_ipv4_network()
        user_reserved_subnet = factory.make_Subnet(
            cidr=unicode(user_reserved_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=factory.make_User(),
            ip=factory.pick_ip_in_network(user_reserved_network),
            subnet=user_reserved_subnet, interface=interface)
        gateway_ip = sticky_subnet.gateway_ip
        self.assertEquals(
            [(interface.id, sticky_subnet.id, gateway_ip)],
            node.get_best_guess_for_default_gateways())

    def test__user_reserved_ip_over_auto(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        node = factory.make_Node(
            status=NODE_STATUS.READY, nodegroup=nodegroup, disable_ipv4=False)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        user_reserved_network = factory.make_ipv4_network()
        user_reserved_subnet = factory.make_Subnet(
            cidr=unicode(user_reserved_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=factory.make_User(),
            ip=factory.pick_ip_in_network(user_reserved_network),
            subnet=user_reserved_subnet, interface=interface)
        auto_network = factory.make_ipv4_network()
        auto_subnet = factory.make_Subnet(
            cidr=unicode(auto_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_network(auto_network),
            subnet=auto_subnet, interface=interface)
        gateway_ip = user_reserved_subnet.gateway_ip
        self.assertEquals(
            [(interface.id, user_reserved_subnet.id, gateway_ip)],
            node.get_best_guess_for_default_gateways())


class TestGetDefaultGateways(MAASServerTestCase):
    """Tests for `Node.get_default_gateways`."""

    def test__return_set_ipv4_and_ipv6(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        node = factory.make_Node(
            status=NODE_STATUS.READY, nodegroup=nodegroup, disable_ipv4=False)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=unicode(network_v4.cidr))
        network_v4_2 = factory.make_ipv4_network()
        subnet_v4_2 = factory.make_Subnet(cidr=unicode(network_v4_2.cidr))
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet_v4_2)
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=unicode(network_v6.cidr))
        network_v6_2 = factory.make_ipv6_network()
        subnet_v6_2 = factory.make_Subnet(cidr=unicode(network_v6_2.cidr))
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet_v6_2)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v4),
            subnet=subnet_v4, interface=interface)
        link_v4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v4_2),
            subnet=subnet_v4_2, interface=interface)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v6),
            subnet=subnet_v6, interface=interface)
        link_v6 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v6_2),
            subnet=subnet_v6_2, interface=interface)
        node.gateway_link_ipv4 = link_v4
        node.gateway_link_ipv6 = link_v6
        node.save()
        self.assertEquals((
            (interface.id, subnet_v4_2.id, subnet_v4_2.gateway_ip),
            (interface.id, subnet_v6_2.id, subnet_v6_2.gateway_ip),
            ), node.get_default_gateways())

    def test__return_set_ipv4_and_guess_ipv6(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        node = factory.make_Node(
            status=NODE_STATUS.READY, nodegroup=nodegroup, disable_ipv4=False)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=unicode(network_v4.cidr))
        network_v4_2 = factory.make_ipv4_network()
        subnet_v4_2 = factory.make_Subnet(cidr=unicode(network_v4_2.cidr))
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet_v4_2)
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=unicode(network_v6.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v4),
            subnet=subnet_v4, interface=interface)
        link_v4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v4_2),
            subnet=subnet_v4_2, interface=interface)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v6),
            subnet=subnet_v6, interface=interface)
        node.gateway_link_ipv4 = link_v4
        node.save()
        self.assertEquals((
            (interface.id, subnet_v4_2.id, subnet_v4_2.gateway_ip),
            (interface.id, subnet_v6.id, subnet_v6.gateway_ip),
            ), node.get_default_gateways())

    def test__return_set_ipv6_and_guess_ipv4(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        node = factory.make_Node(
            status=NODE_STATUS.READY, nodegroup=nodegroup, disable_ipv4=False)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=unicode(network_v4.cidr))
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=unicode(network_v6.cidr))
        network_v6_2 = factory.make_ipv6_network()
        subnet_v6_2 = factory.make_Subnet(cidr=unicode(network_v6_2.cidr))
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet_v6_2)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v4),
            subnet=subnet_v4, interface=interface)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v6),
            subnet=subnet_v6, interface=interface)
        link_v6 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v6_2),
            subnet=subnet_v6_2, interface=interface)
        node.gateway_link_ipv6 = link_v6
        node.save()
        self.assertEquals((
            (interface.id, subnet_v4.id, subnet_v4.gateway_ip),
            (interface.id, subnet_v6_2.id, subnet_v6_2.gateway_ip),
            ), node.get_default_gateways())

    def test__return_guess_ipv4_and_ipv6(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        node = factory.make_Node(
            status=NODE_STATUS.READY, nodegroup=nodegroup, disable_ipv4=False)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=unicode(network_v4.cidr))
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=unicode(network_v6.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v4),
            subnet=subnet_v4, interface=interface)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v6),
            subnet=subnet_v6, interface=interface)
        self.assertEquals((
            (interface.id, subnet_v4.id, subnet_v4.gateway_ip),
            (interface.id, subnet_v6.id, subnet_v6.gateway_ip),
            ), node.get_default_gateways())


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

    def make_acquired_node_with_interface(self, user, nodegroup=None):
        node = factory.make_Node_with_Interface_on_Subnet(
            nodegroup=nodegroup, status=NODE_STATUS.READY, with_boot_disk=True)
        self.prepare_rpc_to_cluster(node.nodegroup)
        node.acquire(user)
        return node

    def test__sets_user_data(self):
        user = factory.make_User()
        nodegroup = factory.make_NodeGroup()
        self.prepare_rpc_to_cluster(nodegroup)
        node = self.make_acquired_node_with_interface(user, nodegroup)
        user_data = factory.make_bytes()

        with post_commit_hooks:
            node.start(user, user_data=user_data)

        nud = NodeUserData.objects.get(node=node)
        self.assertEqual(user_data, nud.data)

    def test__resets_user_data(self):
        user = factory.make_User()
        nodegroup = factory.make_NodeGroup()
        self.prepare_rpc_to_cluster(nodegroup)
        node = self.make_acquired_node_with_interface(user, nodegroup)
        user_data = factory.make_bytes()
        NodeUserData.objects.set_user_data(node, user_data)

        with post_commit_hooks:
            node.start(user, user_data=None)

        self.assertFalse(NodeUserData.objects.filter(node=node).exists())

    def test__claims_auto_ip_addresses(self):
        user = factory.make_User()
        nodegroup = factory.make_NodeGroup()
        self.prepare_rpc_to_cluster(nodegroup)
        node = self.make_acquired_node_with_interface(user, nodegroup)

        claim_auto_ips = self.patch_autospec(
            node, "claim_auto_ips")

        with post_commit_hooks:
            node.start(user)

        self.expectThat(
            claim_auto_ips, MockCalledOnceWith())

    def test__only_claims_auto_addresses_when_allocated(self):
        user = factory.make_User()
        nodegroup = factory.make_NodeGroup()
        self.prepare_rpc_to_cluster(nodegroup)
        node = self.make_acquired_node_with_interface(user, nodegroup)
        node.status = NODE_STATUS.BROKEN
        node.save()

        claim_auto_ips = self.patch_autospec(
            node, "claim_auto_ips", spec_set=False)

        with post_commit_hooks:
            node.start(user)

        # No calls are made to claim_auto_ips, since the node
        # isn't ALLOCATED.
        self.assertThat(claim_auto_ips, MockNotCalled())

    def test__set_zone(self):
        """Verifies whether the set_zone sets the node's zone"""
        zone = factory.make_Zone()
        node = factory.make_Node()
        node.set_zone(zone)
        self.assertEqual(node.zone, zone)

    def test__starts_nodes(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(user)
        power_info = node.get_effective_power_info()

        power_on_node = self.patch(node_module, "power_on_node")
        power_on_node.return_value = defer.succeed(None)
        self.patch_autospec(node, '_start_transition_monitor_async')

        with post_commit_hooks:
            node.start(user)

        # If the following fails the diff is big, but it's useful.
        self.maxDiff = None

        self.expectThat(power_on_node, MockCalledOnceWith(
            node.system_id, node.hostname, node.nodegroup.uuid,
            power_info))

        # A transition monitor was started.
        self.expectThat(
            node._start_transition_monitor_async,
            MockCalledOnceWith(ANY, node.hostname))

    def test__raises_failures_when_power_action_fails(self):
        class PraiseBeToJTVException(Exception):
            """A nonsense exception for this test.

            (Though jtv is praiseworthy, and that's worth noting).
            """

        mock_getClientFor = self.patch(power_module, 'getClientFor')
        mock_getClientFor.return_value = defer.fail(
            PraiseBeToJTVException("Defiance is futile"))

        user = factory.make_User()
        node = self.make_acquired_node_with_interface(user)

        with ExpectedException(PraiseBeToJTVException):
            with post_commit_hooks:
                node.start(user)

    def test__marks_allocated_node_as_deploying(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(user)
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
            owner=user, interface=True)
        power_on_node = self.patch(node_module, "power_on_node")
        power_on_node.return_value = defer.succeed(None)
        with post_commit_hooks:
            node.start(user)
        self.assertEqual(
            NODE_STATUS.DEPLOYED, reload_object(node).status)

    def test__does_not_try_to_start_nodes_that_cant_be_started_by_MAAS(self):
        user = factory.make_User()
        node = self.make_acquired_node_with_interface(user)
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
        node = self.make_acquired_node_with_interface(owner)

        user = factory.make_User()
        with ExpectedException(PermissionDenied):
            node.start(user)
            self.assertThat(power_on_node, MockNotCalled())

    def test__allows_admin_to_start_any_node(self):
        power_on_node = self.patch_autospec(node_module, "power_on_node")
        owner = factory.make_User()
        node = self.make_acquired_node_with_interface(owner)

        admin = factory.make_admin()
        with post_commit_hooks:
            node.start(admin)

        self.expectThat(
            power_on_node, MockCalledOnceWith(
                node.system_id, node.hostname, node.nodegroup.uuid,
                node.get_effective_power_info()))

    def test__releases_auto_ips_when_power_action_fails(self):
        exception_type = factory.make_exception_type()

        mock_getClientFor = self.patch(power_module, 'getClientFor')
        mock_getClientFor.return_value = defer.fail(
            exception_type("He's fallen in the water!"))

        user = factory.make_User()
        node = self.make_acquired_node_with_interface(user)

        release_auto_ips = self.patch_autospec(
            node, "release_auto_ips")

        with ExpectedException(exception_type):
            with post_commit_hooks:
                node.start(user)

        self.assertThat(release_auto_ips, MockCalledOnceWith())


class TestNode_Stop(MAASServerTestCase):
    """Tests for Node.stop()."""

    def make_node_with_interface(
            self, user, nodegroup=None, power_type="virsh"):
        node = factory.make_Node_with_Interface_on_Subnet(
            nodegroup=nodegroup, status=NODE_STATUS.READY,
            power_type=power_type, with_boot_disk=True)
        node.acquire(user)
        return node

    def test__stops_nodes(self):
        power_off_node = self.patch_autospec(node_module, "power_off_node")

        user = factory.make_User()
        node = self.make_node_with_interface(user)
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
        node = self.make_node_with_interface(owner)

        user = factory.make_User()
        self.assertRaises(PermissionDenied, node.stop, user)
        self.assertThat(power_off_node, MockNotCalled())

    def test__allows_admin_to_stop_any_node(self):
        power_off_node = self.patch_autospec(node_module, "power_off_node")
        owner = factory.make_User()
        node = self.make_node_with_interface(owner)
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
        node = self.make_node_with_interface(user)
        node.power_type = ""
        node.save()

        power_off_node = self.patch_autospec(node_module, "power_off_node")
        node.stop(user)
        self.assertThat(power_off_node, MockNotCalled())

    def test__does_not_attempt_power_off_if_cannot_be_stopped(self):
        # If the node has a power_type that doesn't allow MAAS to power
        # the node off, stop() won't attempt to send the power command.
        user = factory.make_User()
        node = self.make_node_with_interface(user, power_type="ether_wake")
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
        node = self.make_node_with_interface(user)

        with ExpectedException(fake_exception_type):
            with post_commit_hooks:
                node.stop(user)

    def test__returns_None_if_power_action_not_sent(self):
        user = factory.make_User()
        node = self.make_node_with_interface(user, power_type="")

        self.patch_autospec(node_module, "power_off_node")
        self.assertThat(node.stop(user), Is(None))

    def test__returns_Deferred_if_power_action_sent(self):
        user = factory.make_User()
        node = self.make_node_with_interface(user, power_type="virsh")

        self.patch_autospec(node_module, "power_off_node")
        with post_commit_hooks:
            self.assertThat(node.stop(user), IsInstance(defer.Deferred))


class TestDevice(MAASServerTestCase):
    def test_node_devices_returns_devices(self):
        node = factory.make_Node()
        node.save()
        device = factory.make_Device()
        device.save()

        devices = Node.devices.all()
        self.expectThat(devices, HasLength(1))
        # XXX Technical debt: bug #1443410
        # self.expectThat(devices[0], Equals(device))

    def test_device_ojects_retrns_devices(self):
        node = factory.make_Node()
        node.save()
        device = factory.make_Device()
        device.save()

        devices = Device.objects.all()
        self.expectThat(devices, HasLength(1))
        self.expectThat(devices[0], Equals(device))

    def test_node_objects_returns_nodes_and_devices(self):
        node = factory.make_Node()
        node.save()
        device = factory.make_Device()
        device.save()

        nodes_and_devices = Node.objects.all()
        self.expectThat(nodes_and_devices, HasLength(2))
        # XXX Technical debt: bug #1443410
        # self.assertItemsEqual([node, device], nodes_and_devices)
