# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver models."""

__all__ = []

from datetime import datetime
import random

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.db import transaction
from fixtures import LoggerFixture
from maasserver import preseed as preseed_module
from maasserver.clusterrpc.power import (
    power_off_node,
    power_on_node,
)
from maasserver.clusterrpc.power_parameters import get_power_types
from maasserver.clusterrpc.testing.boot_images import make_rpc_boot_image
from maasserver.enum import (
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_PERMISSION,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_STATUS_CHOICES_DICT,
    NODE_TYPE,
    POWER_STATE,
)
from maasserver.exceptions import NodeStateViolation
from maasserver.models import (
    bmc as bmc_module,
    BondInterface,
    Config,
    Device,
    Domain,
    Fabric,
    Interface,
    LicenseKey,
    Machine,
    Node,
    node as node_module,
    PhysicalInterface,
    RackController,
    RegionController,
    RegionRackRPCConnection,
    Space,
    Subnet,
    UnknownInterface,
    VLAN,
    VLANInterface,
)
from maasserver.models.bmc import BMC
from maasserver.models.event import Event
from maasserver.models.node import (
    PowerInfo,
    typecast_node,
    typecast_to_node_type,
)
from maasserver.models.signals import power as node_query
from maasserver.models.timestampedmodel import now
from maasserver.models.user import create_auth_token
from maasserver.node_status import (
    NODE_FAILURE_STATUS_TRANSITIONS,
    NODE_TRANSITIONS,
)
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
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import (
    post_commit,
    post_commit_hooks,
    reload_object,
)
from maasserver.utils.threads import deferToDatabase
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.twisted import always_succeed_with
from metadataserver.enum import RESULT_TYPE
from metadataserver.fields import Bin
from metadataserver.models import (
    NodeKey,
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
from provisioningserver.events import (
    EVENT_DETAILS,
    EVENT_TYPES,
)
from provisioningserver.power import QUERY_POWER_TYPES
from provisioningserver.power.schema import JSON_POWER_TYPE_PARAMETERS
from provisioningserver.rpc import cluster as cluster_module
from provisioningserver.rpc.cluster import (
    AddChassis,
    RefreshRackControllerInfo,
)
from provisioningserver.rpc.exceptions import (
    NoConnectionsAvailable,
    UnknownPowerType,
)
from provisioningserver.rpc.testing.doubles import DummyConnection
from provisioningserver.utils import znums
from provisioningserver.utils.enum import (
    map_enum,
    map_enum_reverse,
)
from testtools import ExpectedException
from testtools.matchers import (
    AfterPreprocessing,
    Contains,
    Equals,
    HasLength,
    Is,
    IsInstance,
    MatchesSetwise,
    MatchesStructure,
    Not,
)
from twisted.internet import (
    defer,
    reactor,
)


class TestTypeCastNode(MAASServerTestCase):
    def test_all_node_types_can_be_casted(self):
        node = factory.make_Node()
        cast_to = random.choice(
            [Device, Machine, Node, RackController, RegionController])
        typecast_node(node, cast_to)
        self.assertIsInstance(node, cast_to)

    def test_rejects_casting_to_non_node_type_objects(self):
        node = factory.make_Node()
        self.assertRaises(AssertionError, typecast_node, node, object)

    def test_rejects_casting_non_node_type(self):
        node = object()
        cast_to = random.choice(
            [Device, Machine, Node, RackController, RegionController])
        self.assertRaises(AssertionError, typecast_node, node, cast_to)


class TestTypeCastToNodeType(MAASServerTestCase):
    def test_cast_to_machine(self):
        node = factory.make_Node(node_type=NODE_TYPE.MACHINE)
        machine = typecast_to_node_type(node)
        self.assertIsInstance(machine, Machine)

    def test_cast_to_rack_controller(self):
        node = factory.make_Node(node_type=NODE_TYPE.RACK_CONTROLLER)
        rack = typecast_to_node_type(node)
        self.assertIsInstance(rack, RackController)

    def test_cast_to_region_and_rack_controller(self):
        node = factory.make_Node(
            node_type=NODE_TYPE.REGION_AND_RACK_CONTROLLER)
        rack = typecast_to_node_type(node)
        self.assertIsInstance(rack, RackController)

    def test_cast_to_region_controller(self):
        node = factory.make_Node(node_type=NODE_TYPE.REGION_CONTROLLER)
        region = typecast_to_node_type(node)
        self.assertIsInstance(region, RegionController)

    def test_cast_to_device(self):
        node = factory.make_Node(node_type=NODE_TYPE.DEVICE)
        device = typecast_to_node_type(node)
        self.assertIsInstance(device, Device)

    def test_throws_exception_on_unknown_type(self):
        node = factory.make_Node(node_type=random.randint(10, 10000))
        self.assertRaises(NotImplementedError, typecast_to_node_type, node)


class TestNodeManager(MAASServerTestCase):
    def test_node_lists_all_node_types(self):
        # Create machines.
        machines = [factory.make_Node(node_type=NODE_TYPE.MACHINE)
                    for _ in range(3)]
        # Create devices.
        devices = [factory.make_Device() for _ in range(3)]
        # Create rack_controllers.
        rack_controllers = [
            factory.make_Node(
                node_type=NODE_TYPE.RACK_CONTROLLER)
            for _ in range(3)]
        self.assertItemsEqual(
            machines + devices + rack_controllers, Node.objects.all())


class TestMachineManager(MAASServerTestCase):
    def make_machine(self, user=None, **kwargs):
        """Create a machine, allocated to `user` if given."""
        if user is None:
            status = NODE_STATUS.READY
        else:
            status = NODE_STATUS.ALLOCATED
        return factory.make_Node(status=status, owner=user, **kwargs)

    def test_machine_lists_node_type_machine(self):
        # Create machines.
        machines = [factory.make_Node(node_type=NODE_TYPE.MACHINE)
                    for _ in range(3)]
        # Create devices.
        [factory.make_Device() for _ in range(3)]
        # Create rack_controllers.
        [factory.make_Node(node_type=NODE_TYPE.RACK_CONTROLLER)
         for _ in range(3)]
        self.assertItemsEqual(machines, Machine.objects.all())

    def test_get_available_machines_finds_available_machines(self):
        user = factory.make_User()
        machine1 = self.make_machine(None)
        machine2 = self.make_machine(None)
        self.assertItemsEqual(
            [machine1, machine2],
            Machine.objects.get_available_machines_for_acquisition(user))

    def test_get_available_machines_returns_empty_list_if_empty(self):
        user = factory.make_User()
        self.assertEqual(
            [],
            list(Machine.objects.get_available_machines_for_acquisition(user)))

    def test_get_available_machines_ignores_taken_machines(self):
        user = factory.make_User()
        available_status = NODE_STATUS.READY
        unavailable_statuses = (
            set(NODE_STATUS_CHOICES_DICT) - set([available_status]))
        for status in unavailable_statuses:
            factory.make_Node(status=status)
        self.assertEqual(
            [],
            list(Machine.objects.get_available_machines_for_acquisition(user)))

    def test_get_available_machines_ignores_invisible_machines(self):
        user = factory.make_User()
        machine = self.make_machine()
        machine.owner = factory.make_User()
        machine.save()
        self.assertEqual(
            [],
            list(Machine.objects.get_available_machines_for_acquisition(user)))


class TestControllerManager(MAASServerTestCase):
    def test_controller_lists_node_type_rack_and_region(self):
        racks_and_regions = set()
        for _ in range(3):
            factory.make_Node(node_type=NODE_TYPE.MACHINE)
            factory.make_Device()
            for node_type in (
                    NODE_TYPE.RACK_CONTROLLER, NODE_TYPE.REGION_CONTROLLER,
                    NODE_TYPE.REGION_AND_RACK_CONTROLLER):
                racks_and_regions.add(factory.make_Node(node_type=node_type))
        self.assertItemsEqual(racks_and_regions, Node.controllers.all())

    def test_get_running_controller(self):
        rack = factory.make_RackController()
        get_maas_id = self.patch(node_module, 'get_maas_id')
        get_maas_id.return_value = rack.system_id
        self.assertEquals(rack, Node.controllers.get_running_controller())


class TestRackControllerManager(MAASServerTestCase):

    def make_rack_controller_with_ip(self, subnet=None):
        rack = factory.make_RackController(subnet=subnet)
        # factory.make_Node_with_Interface_on_Subnet gives the rack an
        # interface on the specified subnet a static IP but doesn't actually
        # set one. Setting one in the factory breaks a number of other tests.
        static_ip = rack.boot_interface.ip_addresses.first()
        if subnet is None:
            subnet = static_ip.subnet
        static_ip.ip = factory.pick_ip_in_Subnet(subnet)
        static_ip.save()
        return rack

    def test_rack_controller_lists_node_type_rack_controller(self):
        # Create machines.
        [factory.make_Node(node_type=NODE_TYPE.MACHINE) for _ in range(3)]
        # Create devices.
        [factory.make_Device() for _ in range(3)]
        # Create rack_controllers.
        rack_controllers = [
            factory.make_Node(
                node_type=NODE_TYPE.RACK_CONTROLLER)
            for _ in range(3)]
        self.assertItemsEqual(rack_controllers, RackController.objects.all())

    def test_filter_by_url_accessible_finds_correct_racks(self):
        accessible_subnet = factory.make_Subnet()
        accessible_racks = set()
        for _ in range(3):
            accessible_racks.add(
                self.make_rack_controller_with_ip(accessible_subnet))
            self.make_rack_controller_with_ip()
        url = factory.pick_ip_in_Subnet(accessible_subnet)
        mock_getaddr_info = self.patch(node_module.socket, "getaddrinfo")
        mock_getaddr_info.return_value = (('', '', '', '', (url,)),)
        self.assertItemsEqual(
            accessible_racks,
            RackController.objects.filter_by_url_accessible(url, False))

    def test_filter_by_url_accessible_parses_full_url(self):
        hostname = factory.make_hostname()
        url = "%s://%s:%s@%s:%d/%s" % (
            factory.make_name('protocol'),
            factory.make_name('username'),
            factory.make_name('password'),
            hostname,
            random.randint(0, 65535),
            factory.make_name('path'),
        )
        accessible_subnet = factory.make_Subnet()
        accessible_rack = self.make_rack_controller_with_ip(accessible_subnet)
        factory.make_RackController()
        ip = factory.pick_ip_in_Subnet(accessible_subnet)
        mock_getaddr_info = self.patch(node_module.socket, "getaddrinfo")
        mock_getaddr_info.return_value = (('', '', '', '', (ip,)),)
        self.assertItemsEqual(
            (accessible_rack,),
            RackController.objects.filter_by_url_accessible(url, False))
        self.assertThat(mock_getaddr_info, MockCalledOnceWith(hostname, None))

    def test_filter_by_url_accessible_parses_host_port(self):
        hostname = factory.make_hostname()
        url = "%s:%d" % (hostname, random.randint(0, 65535))
        accessible_subnet = factory.make_Subnet()
        accessible_rack = self.make_rack_controller_with_ip(accessible_subnet)
        factory.make_RackController()
        ip = factory.pick_ip_in_Subnet(accessible_subnet)
        mock_getaddr_info = self.patch(node_module.socket, "getaddrinfo")
        mock_getaddr_info.return_value = (('', '', '', '', (ip,)),)
        self.assertItemsEqual(
            (accessible_rack,),
            RackController.objects.filter_by_url_accessible(url, False))
        self.assertThat(mock_getaddr_info, MockCalledOnceWith(hostname, None))

    def test_filter_by_url_accessible_parses_host_user_pass(self):
        hostname = factory.make_hostname()
        url = "%s:%s@%s" % (
            factory.make_name('username'),
            factory.make_name('password'),
            hostname,
        )
        accessible_subnet = factory.make_Subnet()
        accessible_rack = self.make_rack_controller_with_ip(accessible_subnet)
        factory.make_RackController()
        ip = factory.pick_ip_in_Subnet(accessible_subnet)
        mock_getaddr_info = self.patch(node_module.socket, "getaddrinfo")
        mock_getaddr_info.return_value = (('', '', '', '', (ip,)),)
        self.assertItemsEqual(
            (accessible_rack,),
            RackController.objects.filter_by_url_accessible(url, False))
        self.assertThat(mock_getaddr_info, MockCalledOnceWith(hostname, None))

    def test_filter_by_url_finds_self_with_loopback(self):
        rack = self.make_rack_controller_with_ip()
        mock_getaddr_info = self.patch(node_module.socket, "getaddrinfo")
        ip = random.choice(['127.0.0.1', '::1'])
        mock_getaddr_info.return_value = (('', '', '', '', (ip,)),)
        get_maas_id = self.patch(node_module, 'get_maas_id')
        get_maas_id.return_value = rack.system_id
        self.assertEquals(
            [rack, ],
            RackController.objects.filter_by_url_accessible(ip, False))

    def test_filter_by_url_only_returns_connected_controllers(self):
        subnet = factory.make_Subnet()
        accessible_racks = set()
        connections = list()
        for _ in range(3):
            accessible_rack = self.make_rack_controller_with_ip(subnet=subnet)
            accessible_racks.add(accessible_rack)
            conn = DummyConnection()
            conn.ident = accessible_rack.system_id
            connections.append(conn)
            self.make_rack_controller_with_ip()
        ip = factory.pick_ip_in_Subnet(subnet)
        mock_getaddr_info = self.patch(node_module.socket, "getaddrinfo")
        mock_getaddr_info.return_value = (('', '', '', '', (ip,)),)
        mock_getallclients = self.patch(node_module, "getAllClients")
        mock_getallclients.return_value = connections
        self.assertItemsEqual(
            accessible_racks,
            RackController.objects.filter_by_url_accessible(ip, True))

    def test_get_accessible_by_url(self):
        accessible_subnet = factory.make_Subnet()
        accessible_racks = set()
        for _ in range(3):
            accessible_racks.add(
                self.make_rack_controller_with_ip(accessible_subnet))
            factory.make_RackController()
        url = factory.pick_ip_in_Subnet(accessible_subnet)
        mock_getaddr_info = self.patch(
            node_module.socket, "getaddrinfo")
        mock_getaddr_info.return_value = (('', '', '', '', (url,)),)
        self.assertIn(
            RackController.objects.get_accessible_by_url(url, False),
            accessible_racks)

    def test_get_accessible_by_url_returns_none_when_not_found(self):
        accessible_subnet = factory.make_Subnet()
        for _ in range(3):
            factory.make_RackController()
        url = factory.pick_ip_in_Subnet(accessible_subnet)
        mock_getaddr_info = self.patch(
            node_module.socket, "getaddrinfo")
        mock_getaddr_info.return_value = (('', '', '', '', (url,)),)
        self.assertEquals(
            None, RackController.objects.get_accessible_by_url(url, False))


class TestDeviceManager(MAASServerTestCase):

    def test_device_lists_node_type_devices(self):
        # Create machines.
        [factory.make_Node(node_type=NODE_TYPE.MACHINE) for _ in range(3)]
        # Create devices.
        devices = [factory.make_Device() for _ in range(3)]
        # Create rack_controllers.
        [factory.make_Node(node_type=NODE_TYPE.RACK_CONTROLLER)
         for _ in range(3)]
        self.assertItemsEqual(devices, Device.objects.all())

    def test_empty_architecture_accepted_for_type_device(self):
        device = factory.make_Device(architecture='')
        self.assertThat(device, IsInstance(Device))
        self.assertEqual('', device.architecture)


class TestNode(MAASServerTestCase):

    def setUp(self):
        super(TestNode, self).setUp()
        self.patch_autospec(node_module, 'power_driver_check')

    def disable_node_query(self):
        self.addCleanup(node_query.signals.enable)
        node_query.signals.disable()

    def test_is_controller_machine(self):
        machine = factory.make_Node()
        self.assertFalse(machine.is_controller)

    def test_is_controller_device(self):
        device = factory.make_Device()
        self.assertFalse(device.is_controller)

    def test_is_controller_region_controller(self):
        region = factory.make_RegionController()
        self.assertTrue(region.is_controller)

    def test_is_controller_region_rack_controller(self):
        region_rack = factory.make_RegionRackController()
        self.assertTrue(region_rack.is_controller)

    def test_is_controller_rack_controller(self):
        rack = factory.make_RackController()
        self.assertTrue(rack.is_controller)

    def test_system_id_is_a_valid_znum(self):
        node = factory.make_Node()
        self.assertThat(
            node.system_id, AfterPreprocessing(
                znums.to_int, IsInstance(int)))

    def test_system_id_is_exactly_6_characters(self):
        node = factory.make_Node()
        self.assertThat(node.system_id, HasLength(6))

    def test_empty_architecture_rejected_for_type_node(self):
        self.assertRaises(
            ValidationError,
            factory.make_Node, node_type=NODE_TYPE.MACHINE, architecture='')

    def test_empty_architecture_rejected_for_type_rack_controller(self):
        self.assertRaises(
            ValidationError,
            factory.make_Node, node_type=NODE_TYPE.RACK_CONTROLLER,
            architecture='')

    def test_hostname_is_validated(self):
        bad_hostname = '-_?!@*-'
        self.assertRaises(
            ValidationError,
            factory.make_Node, hostname=bad_hostname)

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
        node = factory.make_Node(with_boot_disk=False)
        device = factory.make_PhysicalBlockDevice(node=node)
        factory.make_BlockDevice(node=node)
        factory.make_PhysicalBlockDevice()
        self.assertItemsEqual([device], node.physicalblockdevice_set.all())

    def test_storage_returns_size_of_physicalblockdevices_in_mb(self):
        node = factory.make_Node(with_boot_disk=False)
        for _ in range(3):
            factory.make_PhysicalBlockDevice(node=node, size=50 * (1000 ** 2))
        self.assertEqual(50 * 3, node.storage)

    def test_display_storage_returns_decimal_less_than_1000(self):
        node = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(node=node, size=500 * (1000 ** 2))
        self.assertEqual('0.5', node.display_storage())

    def test_display_storage_returns_value_divided_by_1000(self):
        node = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(node=node, size=2000 * (1000 ** 2))
        self.assertEqual('2', node.display_storage())

    def test_get_boot_disk_returns_set_boot_disk(self):
        node = factory.make_Node(with_boot_disk=False)
        # First disk.
        factory.make_PhysicalBlockDevice(node=node)
        boot_disk = factory.make_PhysicalBlockDevice(node=node)
        node.boot_disk = boot_disk
        node.save()
        self.assertEqual(boot_disk, node.get_boot_disk())

    def test_get_boot_disk_returns_first(self):
        node = factory.make_Node(with_boot_disk=False)
        boot_disk = factory.make_PhysicalBlockDevice(node=node)
        # Second disk.
        factory.make_PhysicalBlockDevice(node=node)
        factory.make_PhysicalBlockDevice(node=node)
        self.assertEqual(boot_disk, node.get_boot_disk())

    def test_get_boot_disk_returns_None(self):
        node = factory.make_Node(with_boot_disk=False)
        self.assertIsNone(node.get_boot_disk())

    def test_get_bios_boot_method_returns_pxe(self):
        node = factory.make_Node(bios_boot_method="pxe")
        self.assertEqual("pxe", node.get_bios_boot_method())

    def test_get_bios_boot_method_returns_uefi(self):
        node = factory.make_Node(bios_boot_method="uefi")
        self.assertEqual("uefi", node.get_bios_boot_method())

    def test_get_bios_boot_method_returns_powernv(self):
        node = factory.make_Node(bios_boot_method="powernv")
        self.assertEqual("powernv", node.get_bios_boot_method())

    def test_get_bios_boot_method_returns_powerkvm(self):
        node = factory.make_Node(bios_boot_method="powerkvm")
        self.assertEqual("powerkvm", node.get_bios_boot_method())

    def test_get_bios_boot_method_fallback_to_pxe(self):
        node = factory.make_Node(bios_boot_method=factory.make_name("boot"))
        self.assertEqual("pxe", node.get_bios_boot_method())

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
        mac = str(interface.mac_address)
        added_interface = node.add_physical_interface(mac)
        self.assertEqual(added_interface, interface)

    def test_add_physical_interface_attached_another_node_raises_error(self):
        """Adding a MAC address that's already in use in another node should
        fail"""
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node2)
        mac = str(interface.mac_address)
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
            node_module.petname, "Generate").side_effect = hostnames

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
        node = factory.make_Node(power_type="manual")
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

    def test_get_effective_power_info_can_be_False_for_manual(self):
        node = factory.make_Node(power_type="manual")
        gepp = self.patch(node, "get_effective_power_parameters")
        # For manual the power can never be turned off or on.
        gepp.return_value = {}
        self.assertEqual(
            (False, False, False, "manual", {}),
            node.get_effective_power_info())

    def test_get_effective_power_info_cant_be_queried(self):
        all_power_types = {
            power_type_details['name']
            for power_type_details in JSON_POWER_TYPE_PARAMETERS
        }
        uncontrolled_power_types = all_power_types.difference(
            QUERY_POWER_TYPES)
        for power_type in uncontrolled_power_types:
            node = factory.make_Node(power_type=power_type)
            gepp = self.patch(node, "get_effective_power_parameters")
            self.assertEqual(
                PowerInfo(
                    power_type != 'manual', power_type != 'manual',
                    False, power_type, gepp()),
                node.get_effective_power_info())

    def test_get_effective_power_info_can_be_queried(self):
        power_type = random.choice(QUERY_POWER_TYPES)
        node = factory.make_Node(power_type=power_type)
        gepp = self.patch(node, "get_effective_power_parameters")
        self.assertEqual(
            PowerInfo(
                True, power_type != 'manual', True,
                power_type, gepp()),
            node.get_effective_power_info())

    def test_get_effective_power_info_returns_named_tuple(self):
        node = factory.make_Node(power_type="manual")
        gepp = self.patch(node, "get_effective_power_parameters")
        gepp.return_value = {}
        self.assertThat(
            node.get_effective_power_info(),
            MatchesStructure.byEquality(
                can_be_started=False,
                can_be_stopped=False,
                can_be_queried=False,
                power_type="manual",
                power_parameters={},
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

    def test_acquire_calls__create_acquired_filesystems(self):
        node = factory.make_Node(status=NODE_STATUS.READY, with_boot_disk=True)
        user = factory.make_User()
        token = create_auth_token(user)
        agent_name = factory.make_name('agent-name')
        mock_create_acquired_filesystems = self.patch_autospec(
            node, "_create_acquired_filesystems")
        node.acquire(user, token, agent_name)
        self.assertThat(mock_create_acquired_filesystems, MockCalledOnceWith())

    def test_acquire_logs_user_request(self):
        node = factory.make_Node(status=NODE_STATUS.READY, with_boot_disk=True)
        user = factory.make_User()
        token = create_auth_token(user)
        agent_name = factory.make_name('agent-name')
        register_event = self.patch(node, '_register_request_event')
        node.acquire(user, token, agent_name)
        self.assertThat(register_event, MockCalledOnceWith(
            user, EVENT_TYPES.REQUEST_NODE_ACQUIRE, action='acquire',
            comment=None))

    def test_set_default_storage_layout_does_nothing_if_skip_storage(self):
        node = factory.make_Node(skip_storage=True)
        mock_set_storage_layout = self.patch(node, "set_storage_layout")
        node.set_default_storage_layout()
        self.assertThat(
            mock_set_storage_layout, MockNotCalled())

    def test_set_default_storage_layout_uses_default(self):
        node = factory.make_Node()
        default_layout = Config.objects.get_config("default_storage_layout")
        mock_set_storage_layout = self.patch(node, "set_storage_layout")
        node.set_default_storage_layout()
        self.assertThat(
            mock_set_storage_layout, MockCalledOnceWith(default_layout))

    def test_set_default_storage_layout_logs_error_missing_boot_disk(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        mock_get_layout = self.patch(
            node_module, "get_storage_layout_for_node")
        maaslog = self.patch(node_module, 'maaslog')
        layout_object = MagicMock()
        layout_object.configure.side_effect = (
            StorageLayoutMissingBootDiskError())
        mock_get_layout.return_value = layout_object
        node.set_default_storage_layout()
        self.assertThat(
            maaslog.error,
            MockCalledOnceWith(
                "%s: Unable to set any default storage layout because "
                "it has no writable disks.", node.hostname))

    def test_set_default_storage_layout_logs_error_when_layout_fails(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        mock_get_layout = self.patch(
            node_module, "get_storage_layout_for_node")
        maaslog = self.patch(node_module, 'maaslog')
        layout_object = MagicMock()
        exception = StorageLayoutError(factory.make_name("error"))
        layout_object.configure.side_effect = exception
        mock_get_layout.return_value = layout_object
        node.set_default_storage_layout()
        self.assertThat(
            maaslog.error,
            MockCalledOnceWith(
                "%s: Failed to configure storage layout: %s",
                node.hostname, exception))

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
                "%s: Storage layout was set to %s.",
                node.hostname, used_layout))

    def test_set_storage_layout_raises_error_when_unknown_layout(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        mock_get_layout = self.patch(
            node_module, "get_storage_layout_for_node")
        mock_get_layout.return_value = None
        unknown_layout = factory.make_name("layout")
        with ExpectedException(StorageLayoutError):
            node.set_storage_layout(
                unknown_layout, sentinel.params)

    def test_start_disk_erasing_changes_state_and_starts_node(self):
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=owner, agent_name=agent_name)
        node_start = self.patch(node, '_start')
        # Return a post-commit hook from Node.start().
        node_start.side_effect = lambda user, user_data: post_commit()
        with post_commit_hooks:
            node.start_disk_erasing(owner)
        self.expectThat(node.owner, Equals(owner))
        self.expectThat(node.status, Equals(NODE_STATUS.DISK_ERASING))
        self.expectThat(node.agent_name, Equals(agent_name))
        self.assertThat(
            node_start, MockCalledOnceWith(owner, ANY))

    def test_start_disk_erasing_logs_user_request(self):
        owner = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=owner)
        node_start = self.patch(node, '_start')
        # Return a post-commit hook from Node.start().
        node_start.side_effect = lambda user, user_data: post_commit()
        register_event = self.patch(node, '_register_request_event')
        with post_commit_hooks:
            node.start_disk_erasing(owner)
        self.assertThat(
            node_start, MockCalledOnceWith(owner, ANY))
        self.assertThat(register_event, MockCalledOnceWith(
            owner, EVENT_TYPES.REQUEST_NODE_ERASE_DISK,
            action='start disk erasing', comment=None))

    def test_abort_disk_erasing_changes_state_and_stops_node(self):
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, owner=owner,
            agent_name=agent_name)
        node_stop = self.patch(node, '_stop')
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

    def test_abort_disk_erasing_logs_user_request(self):
        owner = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.DISK_ERASING, owner=owner)
        node_stop = self.patch(node, '_stop')
        # Return a post-commit hook from Node.stop().
        node_stop.side_effect = lambda user: post_commit()
        self.patch(Node, "_set_status")
        register_event = self.patch(node, '_register_request_event')
        with post_commit_hooks:
            node.abort_disk_erasing(owner)
        self.assertThat(register_event, MockCalledOnceWith(
            owner, EVENT_TYPES.REQUEST_NODE_ABORT_ERASE_DISK,
            action='abort disk erasing', comment=None))

    def test_start_disk_erasing_reverts_to_sane_state_on_error(self):
        # If start_disk_erasing encounters an error when calling start(), it
        # will transition the node to a sane state. Failures encountered in
        # one call to start_disk_erasing() won't affect subsequent calls.
        self.disable_node_query()
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        generate_user_data = self.patch(disk_erasing, 'generate_user_data')
        node_start = self.patch(node, '_start')
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
                admin, generate_user_data.return_value))
        self.assertEqual(NODE_STATUS.FAILED_DISK_ERASING, node.status)

    def test_start_disk_erasing_sets_status_on_post_commit_error(self):
        # When start_disk_erasing encounters an error in its post-commit hook,
        # it will set the node's status to FAILED_DISK_ERASING.
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        # Patch out some things that we don't want to do right now.
        self.patch(node, '_start').return_value = None
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
            node.system_id, status=NODE_STATUS.FAILED_DISK_ERASING))
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
        self.patch(node, '_start').side_effect = exception
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
        self.assertThat(abort_commissioning, MockCalledOnceWith(user, None))

    def test_abort_operation_aborts_disk_erasing(self):
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, owner=owner,
            agent_name=agent_name)
        abort_disk_erasing = self.patch_autospec(node, 'abort_disk_erasing')
        node.abort_operation(owner)
        self.assertThat(abort_disk_erasing, MockCalledOnceWith(owner, None))

    def test_abort_operation_aborts_deployment(self):
        agent_name = factory.make_name('agent-name')
        user = factory.make_admin()
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            agent_name=agent_name)
        abort_deploying = self.patch_autospec(node, 'abort_deploying')
        node.abort_operation(user)
        self.assertThat(abort_deploying, MockCalledOnceWith(user, None))

    def test_abort_deployment_logs_user_request(self):
        agent_name = factory.make_name('agent-name')
        admin = factory.make_admin()
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            agent_name=agent_name)
        self.patch(Node, "_clear_status_expires")
        self.patch(Node, "_set_status")
        self.patch(Node, "_stop").return_value = None
        register_event = self.patch(node, '_register_request_event')
        with post_commit_hooks:
            node.abort_deploying(admin)
        self.assertThat(register_event, MockCalledOnceWith(
            admin, EVENT_TYPES.REQUEST_NODE_ABORT_DEPLOYMENT,
            action='abort deploying', comment=None))

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
        node_stop = self.patch(node, '_stop')
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
        self.patch(node, '_stop').side_effect = exception
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
        rack = factory.make_RackController()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.ALLOCATED, owner=owner, agent_name=agent_name,
            power_type="virsh", primary_rack=rack)
        self.patch(Node, '_set_status_expires')
        self.patch(node_module, "post_commit_do")
        node.power_state = POWER_STATE.ON
        with post_commit_hooks:
            node.release()
        self.expectThat(
            Node._set_status_expires,
            MockCalledOnceWith(node.system_id, node.get_releasing_time()))
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
                Node._power_control_node, power_off_node,
                node.system_id, node.hostname,
                [], [rack.system_id], expected_power_info,
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
        # manual cannot be stopped, so discard this option.
        uncontrolled_power_types.discard("manual")
        power_type = random.choice(list(uncontrolled_power_types))
        self.assertNotEqual("manual", power_type)
        rack = factory.make_RackController()
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.ALLOCATED, owner=owner, agent_name=agent_name,
            power_type=power_type, primary_rack=rack)
        self.patch(Node, '_set_status_expires')
        self.patch(node_module, "post_commit_do")
        node.power_state = POWER_STATE.ON
        node.release()
        self.expectThat(Node._set_status_expires, MockNotCalled())
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
            node_module.post_commit_do, MockCallsMatch(
                # A call to power off the node is first scheduled.
                call(
                    Node._power_control_node, power_off_node,
                    node.system_id, node.hostname,
                    [], [rack.system_id], expected_power_info),
                # Also a call to deallocate AUTO IP addresses.
                call(
                    reactor.callLater, 0, deferToDatabase,
                    node._release_to_ready),
            ))

    def test_release_node_that_has_power_off(self):
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=owner, agent_name=agent_name)
        self.patch(node, '_stop')
        self.patch(Node, '_set_status_expires')
        node.power_state = POWER_STATE.OFF
        with post_commit_hooks:
            node.release()
        self.expectThat(node._stop, MockNotCalled())
        self.expectThat(Node._set_status_expires, MockNotCalled())
        self.expectThat(node.status, Equals(NODE_STATUS.RELEASING))
        self.expectThat(node.owner, Equals(owner))
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
        self.patch(Node, '_set_status_expires')
        self.patch(node, '_stop').return_value = None
        node_result = factory.make_NodeResult_for_installation(node=node)
        self.assertEqual(
            [node_result], list(NodeResult.objects.filter(
                node=node, result_type=RESULT_TYPE.INSTALLATION)))
        with post_commit_hooks:
            node.release()
        self.assertEqual(
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
        other_node = factory.make_Node(interface=True)
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
        self.assertEqual(['eth0'], node.get_interface_names())

    def test_get_next_ifname_names_returns_sane_default(self):
        node = factory.make_Node()
        self.assertEqual('eth0', node.get_next_ifname(ifnames=[]))

    def test_get_next_ifname_names_returns_next_available(self):
        node = factory.make_Node()
        self.assertEqual('eth2', node.get_next_ifname(
            ifnames=['eth0', 'eth1']))

    def test_get_next_ifname_names_returns_next_in_sequence(self):
        node = factory.make_Node()
        self.assertEqual('eth12', node.get_next_ifname(
            ifnames=['eth10', 'eth11']))

    def test_get_next_ifname_ignores_vlans_in_names(self):
        node = factory.make_Node()
        self.assertEqual('eth12', node.get_next_ifname(
            ifnames=['eth10.1', 'eth11.2']))

    def test_get_next_ifname_ignores_aliases_in_names(self):
        node = factory.make_Node()
        self.assertEqual('eth12', node.get_next_ifname(
            ifnames=['eth10:5', 'eth11:bob']))

    def test_release_turns_on_netboot(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        self.patch(node, '_stop').return_value = None
        node.set_netboot(on=False)
        with post_commit_hooks:
            node.release()
        self.assertTrue(node.netboot)

    def test_release_logs_user_request(self):
        owner = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=owner)
        self.patch(node, "_stop").return_value = None
        register_event = self.patch(node, '_register_request_event')
        with post_commit_hooks:
            node.release(owner)
        self.assertThat(register_event, MockCalledOnceWith(
            owner, EVENT_TYPES.REQUEST_NODE_RELEASE, action='release',
            comment=None))

    def test_release_clears_osystem_and_distro_series(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        node.osystem = factory.make_name('os')
        node.distro_series = factory.make_name('series')
        self.patch(node, "_stop").return_value = None
        with post_commit_hooks:
            node.release()
        self.assertEqual("", node.osystem)
        self.assertEqual("", node.distro_series)

    def test_release_powers_off_node_when_on(self):
        user = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=user, power_type='virsh',
            power_state=POWER_STATE.ON)
        self.patch(Node, '_set_status_expires')
        node_stop = self.patch(node, '_stop')
        with post_commit_hooks:
            node.release()
        self.assertThat(
            node_stop, MockCalledOnceWith(user))

    def test_release_doesnt_power_off_node_when_off(self):
        user = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=user, power_type='virsh',
            power_state=POWER_STATE.OFF)
        self.patch(Node, '_set_status_expires')
        node_stop = self.patch(node, '_stop')
        with post_commit_hooks:
            node.release()
        self.assertThat(node_stop, MockNotCalled())

    def test_release_does_not_release_ips_when_node_is_off(self):
        """Releasing a powered down node does not call `release_auto_ips`."""
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=user, status=NODE_STATUS.ALLOCATED,
            power_state=POWER_STATE.OFF)
        release_auto_ips = self.patch_autospec(
            node, "release_auto_ips")
        self.patch(Node, '_set_status_expires')
        with post_commit_hooks:
            node.release()
        self.assertThat(release_auto_ips, MockNotCalled())

    def test_release_does_not_release_ips_when_node_cant_be_queried(self):
        """Releasing a node that can't be queried does not call
        `release_auto_ips`."""
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=user, status=NODE_STATUS.ALLOCATED,
            power_state=POWER_STATE.ON, power_type='manual')
        release = self.patch_autospec(
            node, "release_auto_ips")
        self.patch(Node, '_set_status_expires')
        with post_commit_hooks:
            node.release()
        self.assertThat(release, MockNotCalled())

    def test_release_doesnt_release_auto_ips_when_node_releasing(self):
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=user, status=NODE_STATUS.ALLOCATED,
            power_state=POWER_STATE.ON, power_type='virsh')
        release = self.patch_autospec(node, "release_auto_ips")
        self.patch_autospec(node, '_stop')
        self.patch(Node, '_set_status_expires')
        with post_commit_hooks:
            node.release()
        self.assertThat(release, MockNotCalled())

    def test_release_logs_and_raises_errors_in_stopping(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, power_state=POWER_STATE.ON)
        maaslog = self.patch(node_module, 'maaslog')
        exception_class = factory.make_exception_type()
        exception = exception_class(factory.make_name())
        self.patch(node, '_stop').side_effect = exception
        self.assertRaises(exception_class, node.release)
        self.assertEqual(NODE_STATUS.DEPLOYED, node.status)
        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "%s: Unable to shut node down: %s",
                node.hostname, str(exception)))

    def test_release_reverts_to_sane_state_on_error(self):
        # If release() encounters an error when stopping the node, it
        # will leave the node in its previous state (i.e. DEPLOYED).
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, power_type="virsh",
            power_state=POWER_STATE.ON,
            owner=factory.make_User())
        node_stop = self.patch(node, '_stop')
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

    def test_release_calls__clear_acquired_filesystems(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        mock_clear = self.patch(node, "_clear_acquired_filesystems")
        self.patch(node, "_stop").return_value = None
        with post_commit_hooks:
            node.release()
        self.assertThat(mock_clear, MockCalledOnceWith())

    def test_accept_enlistment_gets_node_out_of_declared_state(self):
        # If called on a node in New state, accept_enlistment()
        # changes the node's status, and returns the node.
        target_state = NODE_STATUS.COMMISSIONING

        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.NEW, owner=user)
        self.patch(Node, '_set_status_expires')
        self.patch(Node, '_start').return_value = None
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
            interface=True, status=NODE_STATUS.NEW, power_type='manual')
        node_start = self.patch(node, '_start')
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
        self.assertThat(node_start, MockCalledOnceWith(admin, ANY))

    def test_start_commissioning_sets_options(self):
        rack = factory.make_RackController()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.NEW, power_type='virsh',
            bmc_connected_to=rack)
        node_start = self.patch(node, '_start')
        # Return a post-commit hook from Node.start().
        node_start.side_effect = lambda user, user_data: post_commit()
        admin = factory.make_admin()
        enable_ssh = factory.pick_bool()
        skip_networking = factory.pick_bool()
        skip_storage = factory.pick_bool()
        node.start_commissioning(
            admin, enable_ssh=enable_ssh, skip_networking=skip_networking,
            skip_storage=skip_storage)
        post_commit_hooks.reset()  # Ignore these for now.
        node = reload_object(node)
        expected_attrs = {
            'enable_ssh': enable_ssh,
            'skip_networking': skip_networking,
            'skip_storage': skip_storage,
        }
        self.assertAttributes(node, expected_attrs)

    def test_start_commissioning_sets_user_data(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node_start = self.patch(node, '_start')
        node_start.side_effect = lambda user, user_data: post_commit()
        user_data = factory.make_string().encode('ascii')
        generate_user_data = self.patch(
            commissioning, 'generate_user_data')
        generate_user_data.return_value = user_data
        admin = factory.make_admin()
        node.start_commissioning(admin)
        post_commit_hooks.reset()  # Ignore these for now.
        self.assertThat(node_start, MockCalledOnceWith(admin, user_data))

    def test_start_commissioning_sets_min_hwe_kernel(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node_start = self.patch(node, '_start')
        node_start.side_effect = lambda user, user_data: post_commit()
        user_data = factory.make_string().encode('ascii')
        generate_user_data = self.patch(
            commissioning, 'generate_user_data')
        generate_user_data.return_value = user_data
        admin = factory.make_admin()
        Config.objects.set_config('default_min_hwe_kernel', 'hwe-v')
        node.start_commissioning(admin)
        post_commit_hooks.reset()  # Ignore these for now.
        self.assertEqual('hwe-v', node.min_hwe_kernel)

    def test_start_commissioning_clears_node_commissioning_results(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node_start = self.patch(node, '_start')
        node_start.side_effect = lambda user, user_data: post_commit()
        NodeResult.objects.store_data(
            node, factory.make_string(),
            random.randint(0, 10),
            RESULT_TYPE.COMMISSIONING,
            Bin(factory.make_bytes()))
        with post_commit_hooks:
            node.start_commissioning(factory.make_admin())
        self.assertItemsEqual([], node.noderesult_set.all())

    def test_start_commissioning_clears_storage_configuration(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node_start = self.patch(node, '_start')
        node_start.side_effect = lambda user, user_data: post_commit()
        clear_storage = self.patch_autospec(
            node, '_clear_full_storage_configuration')
        admin = factory.make_admin()
        node.start_commissioning(admin, skip_storage=False)
        post_commit_hooks.reset()  # Ignore these for now.
        self.assertThat(clear_storage, MockCalledOnceWith())

    def test_start_commissioning_doesnt_clear_storage_configuration(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node_start = self.patch(node, '_start')
        node_start.side_effect = lambda user, user_data: post_commit()
        clear_storage = self.patch_autospec(
            node, '_clear_full_storage_configuration')
        admin = factory.make_admin()
        node.start_commissioning(admin, skip_storage=True)
        post_commit_hooks.reset()  # Ignore these for now.
        self.assertThat(clear_storage, MockNotCalled())

    def test_start_commissioning_calls__clear_networking_configuration(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node_start = self.patch(node, '_start')
        node_start.side_effect = lambda user, user_data: post_commit()
        clear_networking = self.patch_autospec(
            node, '_clear_networking_configuration')
        admin = factory.make_admin()
        node.start_commissioning(admin, skip_networking=False)
        post_commit_hooks.reset()  # Ignore these for now.
        self.assertThat(clear_networking, MockCalledOnceWith())

    def test_start_commissioning_doesnt_call__clear_networking(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node_start = self.patch(node, '_start')
        node_start.side_effect = lambda user, user_data: post_commit()
        clear_networking = self.patch_autospec(
            node, '_clear_networking_configuration')
        admin = factory.make_admin()
        node.start_commissioning(admin, skip_networking=True)
        post_commit_hooks.reset()  # Ignore these for now.
        self.assertThat(clear_networking, MockNotCalled())

    def test_start_commissioning_ignores_other_commissioning_results(self):
        node = factory.make_Node()
        filename = factory.make_string()
        data = factory.make_bytes()
        script_result = random.randint(0, 10)
        NodeResult.objects.store_data(
            node, filename, script_result, RESULT_TYPE.COMMISSIONING,
            Bin(data))
        other_node = factory.make_Node(status=NODE_STATUS.NEW)
        self.patch(Node, "_start").return_value = None
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
        node_start = self.patch(node, '_start')
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
            MockCalledOnceWith(admin, generate_user_data.return_value))
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
        self.patch(Node, '_set_status_expires')
        self.patch(node, '_start').return_value = None
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
            node.system_id, status=status))
        # It's logged too.
        self.assertThat(logger.output, Contains(
            "%s: Could not start node for commissioning: %s\n"
            % (node.hostname, error_message)))

    def test_start_commissioning_logs_and_raises_errors_in_starting(self):
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.NEW)
        maaslog = self.patch(node_module, 'maaslog')
        exception = NoConnectionsAvailable(factory.make_name())
        self.patch(node, '_start').side_effect = exception
        self.assertRaises(
            NoConnectionsAvailable, node.start_commissioning, admin)
        self.assertEqual(NODE_STATUS.NEW, node.status)
        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "%s: Could not start node for commissioning: %s",
                node.hostname, exception))

    def test_start_commissioning_logs_user_request(self):
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.NEW, power_type='manual')
        register_event = self.patch(node, '_register_request_event')
        node_start = self.patch(node, '_start')
        # Return a post-commit hook from Node.start().
        node_start.side_effect = lambda user, user_data: post_commit()
        admin = factory.make_admin()
        node.start_commissioning(admin)
        post_commit_hooks.reset()  # Ignore these for now.
        node = reload_object(node)
        self.assertThat(register_event, MockCalledOnceWith(
            admin, EVENT_TYPES.REQUEST_NODE_START_COMMISSIONING,
            action='start commissioning'))

    def test_abort_commissioning_reverts_to_sane_state_on_error(self):
        # If abort commissioning hits an error when trying to stop the
        # node, it will revert the node to the state it was in before
        # abort_commissioning() was called.
        admin = factory.make_admin()
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, power_type="virsh")
        node_stop = self.patch(node, '_stop')
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

    def test_start_commissioning_sets_status_expired(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        admin = factory.make_admin()

        timeout = random.randint(1, 100)
        set_status_expires = self.patch_autospec(
            Node, "_set_status_expires")

        self.patch(Node, "_start").return_value = None
        self.patch(node, 'get_commissioning_time')
        node.get_commissioning_time.return_value = timeout

        with post_commit_hooks:
            node.start_commissioning(admin)

        self.assertThat(
            set_status_expires, MockCalledOnceWith(node.system_id, timeout))

    def test_abort_commissioning_clears_status_expires(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        admin = factory.make_admin()
        self.patch(Node, "_stop").return_value = None
        clear_status_expires = self.patch_autospec(
            Node, "_clear_status_expires")
        self.patch(Node, "_set_status")
        with post_commit_hooks:
            node.abort_commissioning(admin)
        self.assertThat(
            clear_status_expires, MockCalledOnceWith(node.system_id))

    def test_abort_commissioning_logs_user_request(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        admin = factory.make_admin()
        self.patch(Node, "_clear_status_expires")
        self.patch(Node, "_set_status")
        self.patch(Node, "_stop").return_value = None
        register_event = self.patch(node, '_register_request_event')
        with post_commit_hooks:
            node.abort_commissioning(admin)
        self.assertThat(register_event, MockCalledOnceWith(
            admin, EVENT_TYPES.REQUEST_NODE_ABORT_COMMISSIONING,
            action='abort commissioning', comment=None))

    def test_abort_commissioning_logs_and_raises_errors_in_stopping(self):
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        maaslog = self.patch(node_module, 'maaslog')
        exception_class = factory.make_exception_type()
        exception = exception_class(factory.make_name())
        self.patch(node, '_stop').side_effect = exception
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

        node_stop = self.patch(node, '_stop')
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
            status=NODE_STATUS.NEW, power_type='manual',
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

        node_stop = self.patch(node, '_stop')
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
        self.assertRaisesRegex(
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
        self.assertRaisesRegex(
            NodeStateViolation,
            "Invalid transition: Retired -> Allocated.",
            node.save)

    def test_full_clean_checks_architecture_for_installable_nodes(self):
        device = factory.make_Device(architecture='')
        # Set type here so we don't cause exception while creating object
        node = typecast_node(device, Node)
        node.node_type = factory.pick_enum(
            NODE_TYPE, but_not=[NODE_TYPE.DEVICE])
        exception = self.assertRaises(ValidationError, node.full_clean)
        self.assertEqual(
            exception.message_dict,
            {'architecture':
                ['Architecture must be defined for installable nodes.']})

    def test_netboot_defaults_to_True(self):
        node = Node()
        self.assertTrue(node.netboot)

    def test_fqdn_validation_failure_if_nonexistant(self):
        hostname_with_domain = '%s.%s' % (
            factory.make_string(), factory.make_string())
        self.assertRaises(
            ValidationError,
            factory.make_Node, hostname=hostname_with_domain)

    def test_fqdn_default_domain_if_not_given(self):
        domain = Domain.objects.get_default_domain()
        domain.name = factory.make_name('domain')
        domain.save()
        hostname_without_domain = factory.make_string()
        hostname = "%s.%s" % (hostname_without_domain, domain.name)
        node = factory.make_Node(hostname=hostname_without_domain)
        self.assertEqual(hostname, node.fqdn)

    def test_fqdn_if_specified(self):
        # instantiate the default domain name
        Domain.objects.get_default_domain()
        # one for us.
        domain = factory.make_Domain()
        hostname_without_domain = factory.make_string()
        hostname = "%s.%s" % (hostname_without_domain, domain.name)
        node = factory.make_Node(hostname=hostname)
        self.assertEqual(hostname, node.fqdn)

    def test_split_arch_doesnt_raise_on_missing_arch(self):
        # Method can be called from partition.py, etc, when arch is None.
        node = factory.make_Node(architecture=None)
        self.assertEqual(('', ''), node.split_arch())

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
            node.mark_failed(None, factory.make_name('error-description'))
        self.assertEqual(
            NODE_FAILURE_STATUS_TRANSITIONS,
            {status: node.status for status, node in nodes_mapping.items()})

    def test_mark_failed_logs_user_request(self):
        owner = factory.make_User()
        self.disable_node_query()
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING, owner=owner)
        description = factory.make_name('error-description')
        register_event = self.patch(node, '_register_request_event')
        node.mark_failed(owner, description)
        self.assertThat(register_event, MockCalledOnceWith(
            owner, EVENT_TYPES.REQUEST_NODE_MARK_FAILED, action='mark_failed',
            comment=description))

    def test_mark_failed_updates_error_description(self):
        self.disable_node_query()
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        description = factory.make_name('error-description')
        node.mark_failed(None, description)
        self.assertEqual(description, reload_object(node).error_description)

    def test_mark_failed_raises_for_unauthorized_node_status(self):
        but_not = list(NODE_FAILURE_STATUS_TRANSITIONS.keys())
        but_not.extend(NODE_FAILURE_STATUS_TRANSITIONS.values())
        but_not.append(NODE_STATUS.NEW)
        status = factory.pick_choice(NODE_STATUS_CHOICES, but_not=but_not)
        node = factory.make_Node(status=status)
        description = factory.make_name('error-description')
        self.assertRaises(
            NodeStateViolation, node.mark_failed, None, description)

    def test_mark_failed_ignores_if_already_failed(self):
        status = random.choice([
            NODE_STATUS.FAILED_DEPLOYMENT, NODE_STATUS.FAILED_COMMISSIONING])
        node = factory.make_Node(status=status)
        description = factory.make_name('error-description')
        node.mark_failed(None, description)
        self.assertEqual(status, node.status)

    def test_mark_failed_ignores_if_status_is_NEW(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        description = factory.make_name('error-description')
        node.mark_failed(None, description)
        self.assertEqual(NODE_STATUS.NEW, node.status)

    def test_mark_broken_changes_status_to_broken(self):
        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.NEW, owner=user)
        node.mark_broken(user, factory.make_name('error-description'))
        self.assertEqual(NODE_STATUS.BROKEN, reload_object(node).status)

    def test_mark_broken_logs_user_request(self):
        owner = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.NEW, owner=owner)
        description = factory.make_name('error-description')
        register_event = self.patch(node, '_register_request_event')
        node.mark_broken(owner, description)
        self.assertThat(register_event, MockCalledOnceWith(
            owner, EVENT_TYPES.REQUEST_NODE_MARK_BROKEN, action='mark broken',
            comment=description))

    def test_mark_broken_releases_allocated_node(self):
        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=user)
        err_desc = factory.make_name('error-description')
        release = self.patch(node, '_release')
        node.mark_broken(user, err_desc)
        self.expectThat(node.owner, Is(None))
        self.assertThat(release, MockCalledOnceWith(user))

    def test_mark_fixed_sets_default_osystem_and_distro_series(self):
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        node.osystem = factory.make_name('osystem')
        node.distro_series = factory.make_name('distro_series')
        node.mark_fixed(factory.make_User())
        expected_osystem = expected_distro_series = ''
        self.expectThat(expected_osystem, Equals(node.osystem))
        self.expectThat(expected_distro_series, Equals(node.distro_series))

    def test_mark_fixed_changes_status(self):
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        node.mark_fixed(factory.make_User())
        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)

    def test_mark_fixed_logs_user_request(self):
        owner = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.BROKEN, owner=owner)
        register_event = self.patch(node, '_register_request_event')
        node.mark_fixed(owner)
        self.assertThat(register_event, MockCalledOnceWith(
            owner, EVENT_TYPES.REQUEST_NODE_MARK_FIXED, action='mark fixed',
            comment=None))

    def test_mark_fixed_updates_error_description(self):
        description = factory.make_name('error-description')
        node = factory.make_Node(
            status=NODE_STATUS.BROKEN, error_description=description)
        node.mark_fixed(factory.make_User())
        self.assertEqual('', reload_object(node).error_description)

    def test_mark_fixed_fails_if_node_isnt_broken(self):
        status = factory.pick_choice(
            NODE_STATUS_CHOICES, but_not=[NODE_STATUS.BROKEN])
        node = factory.make_Node(status=status)
        self.assertRaises(
            NodeStateViolation, node.mark_fixed, factory.make_User())

    def test_mark_fixed_clears_installation_results(self):
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        node_result = factory.make_NodeResult_for_installation(node=node)
        self.assertEqual(
            [node_result], list(NodeResult.objects.filter(
                node=node, result_type=RESULT_TYPE.INSTALLATION)))
        node.mark_fixed(factory.make_User())
        self.assertEqual(
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
        self.patch(Node, '_clear_status_expires')
        with post_commit_hooks:
            node.update_power_state(POWER_STATE.OFF)
        self.expectThat(node.status, Equals(NODE_STATUS.READY))
        self.expectThat(node.owner, Is(None))

    def test_update_power_state_does_not_change_status_if_not_releasing(self):
        node = factory.make_Node(
            power_state=POWER_STATE.ON, status=NODE_STATUS.ALLOCATED)
        node.update_power_state(POWER_STATE.OFF)
        self.assertThat(node.status, Equals(NODE_STATUS.ALLOCATED))

    def test_update_power_state_clear_status_expires_if_releasing(self):
        node = factory.make_Node(
            power_state=POWER_STATE.ON, status=NODE_STATUS.RELEASING,
            owner=None, status_expires=datetime.now())
        node.update_power_state(POWER_STATE.OFF)
        self.assertIsNone(node.status_expires)

    def test_update_power_state_does_not_clear_expires_if_not_releasing(self):
        node = factory.make_Node(
            power_state=POWER_STATE.ON, status=NODE_STATUS.ALLOCATED)
        self.patch(Node, '_clear_status_expires')
        node.update_power_state(POWER_STATE.OFF)
        self.assertThat(Node._clear_status_expires, MockNotCalled())

    def test_update_power_state_does_not_change_status_if_not_off(self):
        node = factory.make_Node(
            power_state=POWER_STATE.OFF, status=NODE_STATUS.ALLOCATED)
        node.update_power_state(POWER_STATE.ON)
        self.expectThat(node.status, Equals(NODE_STATUS.ALLOCATED))

    def test_update_power_state_release_auto_ips_if_releasing(self):
        node = factory.make_Node(
            power_state=POWER_STATE.ON, status=NODE_STATUS.RELEASING,
            owner=None)
        release = self.patch_autospec(node, 'release_auto_ips')
        self.patch(Node, '_clear_status_expires')
        node.update_power_state(POWER_STATE.OFF)
        self.assertThat(release, MockCalledOnceWith())

    def test_update_power_state_doesnt_release_auto_ips_if_not_off(self):
        node = factory.make_Node(
            power_state=POWER_STATE.OFF, status=NODE_STATUS.ALLOCATED)
        release = self.patch_autospec(node, 'release_auto_ips')
        node.update_power_state(POWER_STATE.ON)
        self.assertThat(release, MockNotCalled())

    def test_end_deployment_changes_state(self):
        self.disable_node_query()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        node.end_deployment()
        self.assertEqual(NODE_STATUS.DEPLOYED, reload_object(node).status)

    def test_start_deployment_changes_state(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.ALLOCATED)
        node._start_deployment()
        self.assertEqual(NODE_STATUS.DEPLOYING, reload_object(node).status)

    def test_start_deployment_logs_user_request(self):
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=admin)
        register_event = self.patch(node, '_register_request_event')
        self.patch(node, 'on_network').return_value = True
        self.patch(Node, "_start").return_value = None
        node.start(admin)
        self.assertThat(register_event, MockCalledOnceWith(
            admin, EVENT_TYPES.REQUEST_NODE_START_DEPLOYMENT, action='start',
            comment=None))

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
            ("xinstall", {"status": NODE_STATUS.DEPLOYING, "netboot": True}),
            ("local", {"status": NODE_STATUS.DEPLOYING, "netboot": False}),
            ("local", {"status": NODE_STATUS.DEPLOYED}),
            ("poweroff", {"status": NODE_STATUS.RETIRED}),
        ]
        node = factory.make_Node()
        mock_get_boot_images_for = self.patch(
            preseed_module, 'get_boot_images_for')
        for purpose, parameters in options:
            boot_image = make_rpc_boot_image(purpose=purpose)
            mock_get_boot_images_for.return_value = [boot_image]
            for name, value in parameters.items():
                setattr(node, name, value)
            self.assertEqual(purpose, node.get_boot_purpose())

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
            for _ in range(3)
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
            for _ in range(3)
        ]
        self.assertItemsEqual([
            interface.mac_address
            for interface in interfaces[1:]
            ], node.get_extra_macs())

    def test__clear_full_storage_configuration_removes_related_objects(self):
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
        node._clear_full_storage_configuration()
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

    def test__create_acquired_filesystems(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        filesystem = factory.make_Filesystem(
            block_device=block_device, fstype=FILESYSTEM_TYPE.EXT4)
        node._create_acquired_filesystems()
        self.assertIsNotNone(
            reload_object(filesystem),
            "Original filesystem on should not have been deleted.")
        self.assertIsNot(
            filesystem, block_device.get_effective_filesystem(),
            "Filesystem on block device should now be a different object.")
        self.assertTrue(
            block_device.get_effective_filesystem().acquired,
            "Filesystem on block device should have acquired set.")

    def test__create_acquired_filesystems_calls_clear(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        mock_clear_acquired_filesystems = self.patch_autospec(
            node, "_clear_acquired_filesystems")
        node._create_acquired_filesystems()
        self.assertThat(mock_clear_acquired_filesystems, MockCalledOnceWith())

    def test__clear_acquired_filesystems_only_removes_acquired(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        filesystem = factory.make_Filesystem(
            block_device=block_device, fstype=FILESYSTEM_TYPE.EXT4)
        acquired_filesystem = factory.make_Filesystem(
            block_device=block_device, fstype=FILESYSTEM_TYPE.EXT4,
            acquired=True)
        node._clear_acquired_filesystems()
        self.expectThat(
            reload_object(acquired_filesystem), Is(None),
            "Acquired filesystem should have been deleted.")
        self.expectThat(
            reload_object(filesystem), Not(Is(None)),
            "Non-acquired filesystem should not have been deleted.")

    def test_boot_disk_removes_formatable_filesystem(self):
        node = factory.make_Node()
        new_boot_disk = factory.make_PhysicalBlockDevice(node=node)
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.EXT4, block_device=new_boot_disk)
        node.boot_disk = new_boot_disk
        node.save()
        self.assertIsNone(reload_object(filesystem))

    def test_boot_disk_displays_error_if_in_filesystem_group(self):
        node = factory.make_Node()
        new_boot_disk = factory.make_PhysicalBlockDevice(node=node)
        pv_filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, block_device=new_boot_disk)
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            filesystems=[pv_filesystem])
        node.boot_disk = new_boot_disk
        error = self.assertRaises(ValidationError, node.save)
        self.assertEqual({
            'boot_disk': [
                "Cannot be set as the boot disk; already in-use in %s "
                "'%s'." % (
                    filesystem_group.get_nice_name(),
                    filesystem_group.name,
                    )]},
            error.message_dict)

    def test_boot_disk_displays_error_if_in_cache_set(self):
        node = factory.make_Node()
        new_boot_disk = factory.make_PhysicalBlockDevice(node=node)
        cache_set = factory.make_CacheSet(block_device=new_boot_disk)
        node.boot_disk = new_boot_disk
        error = self.assertRaises(ValidationError, node.save)
        self.assertEqual({
            'boot_disk': [
                "Cannot be set as the boot disk; already in-use in cache set "
                "'%s'." % (
                    cache_set.name,
                    )]},
            error.message_dict)

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

    def test__register_request_event_saves_event(self):
        node = factory.make_Node()
        user = factory.make_User()
        log_mock = self.patch_autospec(
            Event.objects, 'register_event_and_event_type')
        event_name = EVENT_TYPES.REQUEST_NODE_START
        event_action = factory.make_name('action')
        event_details = EVENT_DETAILS[event_name]
        comment = factory.make_name("comment")
        event_description = "(%s) - %s" % (user.username, comment)
        node._register_request_event(user, event_name, event_action, comment)
        self.assertThat(log_mock, MockCalledOnceWith(
            node.system_id,
            EVENT_TYPES.REQUEST_NODE_START,
            type_level=event_details.level,
            type_description=event_details.description,
            event_action=event_action,
            event_description=event_description))

    def test__register_request_event_with_none_user_saves_no_event(self):
        node = factory.make_Node()
        log_mock = self.patch_autospec(
            Event.objects, 'register_event_and_event_type')
        event_name = EVENT_TYPES.REQUEST_NODE_START
        comment = factory.make_name("comment")
        node._register_request_event(None, event_name, comment)
        self.assertThat(log_mock, MockNotCalled())

    def test__status_message_returns_most_recent_event(self):
        # The first event won't be returned.
        event = factory.make_Event(description="Uninteresting event")
        node = event.node
        # The second (and last) event will be returned.
        message = "Interesting event"
        factory.make_Event(description=message, node=node)
        self.assertEqual(message, node.status_message())

    def test__status_message_returns_none_for_new_node(self):
        node = factory.make_Node()
        self.assertIsNone(node.status_message())


class TestNodePowerParameters(MAASServerTestCase):

    def setUp(self):
        super(TestNodePowerParameters, self).setUp()
        self.patch_autospec(node_module, 'power_driver_check')

    def test_power_parameters_are_stored(self):
        node = factory.make_Node(power_type='')
        parameters = dict(user="tarquin", address="10.1.2.3")
        node.power_parameters = parameters
        node.save()
        node = reload_object(node)
        self.assertEqual(parameters, node.power_parameters)

    def test_power_parameters_default(self):
        node = factory.make_Node(power_type='')
        self.assertEqual({}, node.power_parameters)

    def test_power_type_and_bmc_power_parameters_stored_in_bmc(self):
        node = factory.make_Node(power_type='hmc')
        ip_address = factory.make_ipv4_address()
        bmc_parameters = dict(power_address=ip_address)
        node_parameters = dict(server_name=factory.make_string())
        parameters = {**bmc_parameters, **node_parameters}
        node.power_parameters = parameters
        node.save()
        node = reload_object(node)
        self.assertEqual(parameters, node.power_parameters)
        self.assertEqual(node_parameters, node.instance_power_parameters)
        self.assertEqual(bmc_parameters, node.bmc.power_parameters)
        self.assertEqual('hmc', node.bmc.power_type)
        self.assertEqual(node.power_type, node.bmc.power_type)
        self.assertEqual(ip_address, node.bmc.ip_address.ip)

    def test_power_parameters_are_stored_in_proper_scopes(self):
        node = factory.make_Node(power_type='virsh')
        bmc_parameters = dict(
            power_address="qemu+ssh://trapnine@10.0.2.1/system",
            power_pass=factory.make_string(),
            )
        node_parameters = dict(
            power_id="maas-x",
            )
        parameters = {**bmc_parameters, **node_parameters}
        node.power_parameters = parameters
        node.save()
        node = reload_object(node)
        self.assertEqual(parameters, node.power_parameters)
        self.assertEqual(node_parameters, node.instance_power_parameters)
        self.assertEqual(bmc_parameters, node.bmc.power_parameters)
        self.assertEqual("10.0.2.1", node.bmc.ip_address.ip)

    def test_unknown_power_parameter_stored_on_node(self):
        node = factory.make_Node(power_type='hmc')
        bmc_parameters = dict(power_address=factory.make_ipv4_address())
        node_parameters = dict(server_name=factory.make_string())
        # This random parameters will be stored on the node instance.
        node_parameters[factory.make_string()] = factory.make_string()
        parameters = {**bmc_parameters, **node_parameters}
        node.power_parameters = parameters
        node.save()
        node = reload_object(node)
        self.assertEqual(parameters, node.power_parameters)
        self.assertEqual(node_parameters, node.instance_power_parameters)
        self.assertEqual(bmc_parameters, node.bmc.power_parameters)

    def test_bmc_consolidation(self):
        nodes = []
        for _ in range(3):
            bmc_parameters = dict(power_address=factory.make_ipv4_address())
            node_parameters = dict(power_id=factory.make_string())
            parameters = {**bmc_parameters, **node_parameters}
            node = factory.make_Node(power_type='fence_cdu')
            node.power_parameters = parameters
            node.save()
            node = reload_object(node)
            self.assertEqual(parameters, node.power_parameters)
            self.assertEqual(node_parameters, node.instance_power_parameters)
            self.assertEqual(bmc_parameters, node.bmc.power_parameters)
            self.assertEqual('fence_cdu', node.bmc.power_type)
            nodes.append(node)

        # Make sure there are now 3 different BMC's.
        self.assertEqual(3, BMC.objects.count())
        self.assertNotEqual(nodes[0].bmc_id, nodes[1].bmc_id)
        self.assertNotEqual(nodes[0].bmc_id, nodes[2].bmc_id)

        # Set equivalent bmc power_parameters, and confirm BMC count decrease,
        # even when the Node's instance_power_parameter varies.
        parameters['power_id'] = factory.make_string()
        nodes[0].power_parameters = parameters
        nodes[0].save()
        nodes[0] = reload_object(nodes[0])
        # 0 now shares a BMC with 2.
        self.assertEqual(2, BMC.objects.count())
        self.assertNotEqual(nodes[0].bmc_id, nodes[1].bmc_id)
        self.assertEqual(nodes[0].bmc_id, nodes[2].bmc_id)

        parameters['power_id'] = factory.make_string()
        nodes[1].power_parameters = parameters
        nodes[1].save()
        nodes[1] = reload_object(nodes[1])
        # All 3 share the same BMC, and only one exists.
        self.assertEqual(1, BMC.objects.count())
        self.assertEqual(nodes[0].bmc_id, nodes[1].bmc_id)
        self.assertEqual(nodes[0].bmc_id, nodes[2].bmc_id)

        # Now change parameters and confirm the count doesn't change,
        # as changing the one linked BMC should affect all linked nodes.
        parameters['power_address'] = factory.make_ipv4_address()
        nodes[1].power_parameters = parameters
        nodes[1].save()
        nodes[1] = reload_object(nodes[1])
        self.assertEqual(1, BMC.objects.count())
        self.assertEqual(nodes[0].bmc_id, nodes[1].bmc_id)
        self.assertEqual(nodes[0].bmc_id, nodes[2].bmc_id)

        # Now change type and confirm the count goes up,
        # as changing the type makes a new linked BMC.
        parameters['power_address'] = factory.make_ipv4_address()
        nodes[1].power_type = 'virsh'
        nodes[1].power_parameters = parameters
        nodes[1].save()
        nodes[1] = reload_object(nodes[1])
        self.assertEqual(2, BMC.objects.count())
        self.assertNotEqual(nodes[0].bmc_id, nodes[1].bmc_id)
        self.assertEqual(nodes[0].bmc_id, nodes[2].bmc_id)

        # Set new BMC's values back to match original BMC, and make
        # sure the BMC count decreases as they consolidate.
        nodes[1].power_type = nodes[0].power_type
        parameters = nodes[0].power_parameters
        parameters['power_id'] = factory.make_string()
        nodes[1].power_parameters = parameters
        nodes[1].save()
        nodes[1] = reload_object(nodes[1])
        # 1 now shares a BMC with 0 and 2.
        self.assertEqual(nodes[0].bmc_id, nodes[1].bmc_id)
        self.assertEqual(nodes[0].bmc_id, nodes[2].bmc_id)
        self.assertEqual(1, BMC.objects.count())

    def test_power_parameters_ip_address_extracted(self):
        node = factory.make_Node(power_type='hmc')
        ip_address = factory.make_ipv4_address()
        parameters = dict(power_address=ip_address)
        node.power_parameters = parameters
        node.save()
        self.assertEqual(parameters, node.power_parameters)
        self.assertEqual(ip_address, node.bmc.ip_address.ip)

    def test_power_parameters_unexpected_values_tolerated(self):
        node = factory.make_Node(power_type='virsh')
        parameters = {factory.make_string(): factory.make_string()}
        node.power_parameters = parameters
        node.save()
        self.assertEqual(parameters, node.power_parameters)
        self.assertEqual(None, node.bmc.ip_address)

    def test_power_parameters_blank_ip_address_tolerated(self):
        node = factory.make_Node(power_type='hmc')
        parameters = dict(power_address='')
        node.power_parameters = parameters
        node.save()
        self.assertEqual(parameters, node.power_parameters)
        self.assertEqual(None, node.bmc.ip_address)

    def test_power_parameters_non_ip_address_tolerated(self):
        node = factory.make_Node(power_type='hmc')
        power_address = factory.make_string()
        parameters = dict(power_address=power_address)
        maaslog = self.patch(bmc_module, "maaslog")
        node.power_parameters = parameters
        node.save()
        self.assertEqual(parameters, node.power_parameters)
        self.assertEqual(None, node.bmc.ip_address)
        self.assertThat(
            maaslog.info, MockCalledOnceWith(
                "BMC could not save extracted IP "
                "address '%s': '%s'", power_address, ANY))

    def test_power_parameters_ip_address_reset(self):
        node = factory.make_Node(power_type='hmc')
        ip_address = factory.make_ipv4_address()
        parameters = dict(power_address=ip_address)
        node.power_parameters = parameters
        node.save()
        self.assertEqual(parameters, node.power_parameters)
        self.assertEqual(ip_address, node.bmc.ip_address.ip)

        # StaticIPAddress can be changed after being set.
        ip_address = factory.make_ipv4_address()
        parameters = dict(power_address=ip_address)
        node.power_parameters = parameters
        node.save()
        self.assertEqual(parameters, node.power_parameters)
        self.assertEqual(ip_address, node.bmc.ip_address.ip)

        # StaticIPAddress can be made None after being set.
        ip_address = factory.make_ipv4_address()
        parameters = dict(power_address='')
        node.power_parameters = parameters
        node.save()
        self.assertEqual(parameters, node.power_parameters)
        self.assertEqual(None, node.bmc.ip_address)

        # StaticIPAddress can be changed after being made None.
        ip_address = factory.make_ipv4_address()
        parameters = dict(power_address=ip_address)
        node.power_parameters = parameters
        node.save()
        self.assertEqual(parameters, node.power_parameters)
        self.assertEqual(ip_address, node.bmc.ip_address.ip)


class NodeTransitionsTests(MAASServerTestCase):
    """Test the structure of NODE_TRANSITIONS."""

    def test_NODE_TRANSITIONS_initial_states(self):
        allowed_states = set(list(NODE_STATUS_CHOICES_DICT.keys()) + [None])

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

    def test_filter_nodes_by_spaces(self):
        # Create a throwaway node and a throwaway space.
        # (to ensure they are filtered out.)
        factory.make_Space()
        factory.make_Node_with_Interface_on_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False)
        iface = node.get_boot_interface()
        ip = iface.ip_addresses.first()
        space = ip.subnet.space
        self.assertItemsEqual(
            [node], Node.objects.filter_by_spaces([space]))

    def test_filter_nodes_by_not_spaces(self):
        factory.make_Space()
        extra_node = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False)
        node = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False)
        iface = node.get_boot_interface()
        ip = iface.ip_addresses.first()
        space = ip.subnet.space
        self.assertItemsEqual(
            [extra_node], Node.objects.exclude_spaces([space]))

    def test_filter_nodes_by_fabrics(self):
        fabric = factory.make_Fabric()
        factory.make_Space()
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False)
        node = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, fabric=fabric)
        iface = node.get_boot_interface()
        fabric = iface.vlan.fabric
        self.assertItemsEqual(
            [node], Node.objects.filter_by_fabrics([fabric]))

    def test_filter_nodes_by_not_fabrics(self):
        fabric = factory.make_Fabric()
        extra_node = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False)
        node = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, fabric=fabric)
        iface = node.get_boot_interface()
        fabric = iface.vlan.fabric
        self.assertItemsEqual(
            [extra_node], Node.objects.exclude_fabrics([fabric]))

    def test_filter_nodes_by_fabric_classes(self):
        fabric1 = factory.make_Fabric(class_type="10g")
        fabric2 = factory.make_Fabric(class_type="1g")
        node1 = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, fabric=fabric1)
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, fabric=fabric2)
        self.assertItemsEqual(
            [node1], Node.objects.filter_by_fabric_classes(["10g"]))

    def test_filter_nodes_by_not_fabric_classes(self):
        fabric1 = factory.make_Fabric(class_type="10g")
        fabric2 = factory.make_Fabric(class_type="1g")
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, fabric=fabric1)
        node2 = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, fabric=fabric2)
        self.assertItemsEqual(
            [node2], Node.objects.exclude_fabric_classes(["10g"]))

    def test_filter_nodes_by_vids(self):
        vlan1 = factory.make_VLAN(vid=1)
        vlan2 = factory.make_VLAN(vid=2)
        node1 = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, vlan=vlan1)
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, vlan=vlan2)
        self.assertItemsEqual(
            [node1], Node.objects.filter_by_vids([1]))

    def test_filter_nodes_by_not_vids(self):
        vlan1 = factory.make_VLAN(vid=1)
        vlan2 = factory.make_VLAN(vid=2)
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, vlan=vlan1)
        node2 = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, vlan=vlan2)
        self.assertItemsEqual(
            [node2], Node.objects.exclude_vids([1]))

    def test_filter_nodes_by_subnet(self):
        subnet1 = factory.make_Subnet()
        subnet2 = factory.make_Subnet()
        node1 = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet1)
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet2)
        self.assertItemsEqual(
            [node1], Node.objects.filter_by_subnets([subnet1]))

    def test_filter_nodes_by_not_subnet(self):
        subnet1 = factory.make_Subnet()
        subnet2 = factory.make_Subnet()
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet1)
        node2 = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet2)
        self.assertItemsEqual(
            [node2], Node.objects.exclude_subnets([subnet1]))

    def test_filter_nodes_by_subnet_cidr(self):
        subnet1 = factory.make_Subnet(cidr='192.168.1.0/24')
        subnet2 = factory.make_Subnet(cidr='192.168.2.0/24')
        node1 = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet1)
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet2)
        self.assertItemsEqual(
            [node1], Node.objects.filter_by_subnet_cidrs(['192.168.1.0/24']))

    def test_filter_nodes_by_not_subnet_cidr(self):
        subnet1 = factory.make_Subnet(cidr='192.168.1.0/24')
        subnet2 = factory.make_Subnet(cidr='192.168.2.0/24')
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet1)
        node2 = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet2)
        self.assertItemsEqual(
            [node2], Node.objects.exclude_subnet_cidrs(
                ['192.168.1.0/24']))

    def test_filter_fabric_subnet_filter_chain(self):
        fabric1 = factory.make_Fabric()
        subnet1 = factory.make_Subnet(cidr='192.168.1.0/24', fabric=fabric1)
        subnet2 = factory.make_Subnet(cidr='192.168.2.0/24', fabric=fabric1)
        factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet1, fabric=fabric1)
        node2 = factory.make_Node_with_Interface_on_Subnet(
            with_dhcp_rack_primary=False, subnet=subnet2, fabric=fabric1)
        self.assertItemsEqual(
            [node2], Node.objects
                         .filter_by_fabrics([fabric1])
                         .exclude_subnet_cidrs(['192.168.1.0/24']))

    def test_get_node_or_404_ok(self):
        """get_node_or_404 fetches nodes by system_id."""
        user = factory.make_User()
        node = self.make_node(user)
        self.assertEqual(
            node,
            Node.objects.get_node_or_404(
                node.system_id, user, NODE_PERMISSION.VIEW))

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
        node.release_or_erase(owner)
        self.assertThat(erase_mock, MockCalledOnceWith(owner, None))
        self.assertThat(release_mock, MockNotCalled())

    def test_release_or_erase_releases_when_disabled(self):
        owner = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=owner)
        Config.objects.set_config(
            'enable_disk_erasing_on_release', False)
        erase_mock = self.patch_autospec(node, 'start_disk_erasing')
        release_mock = self.patch_autospec(node, 'release')
        node.release_or_erase(owner)
        self.assertThat(release_mock, MockCalledOnceWith(owner, None))
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
        self.patch(Node, "_stop").return_value = None
        owner = factory.make_User()
        # Create children.
        parent = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=owner)
        [factory.make_Node(parent=parent) for _ in range(3)]
        other_nodes = [factory.make_Node() for _ in range(3)]
        with post_commit_hooks:
            parent.release()
        self.assertItemsEqual([], parent.children.all())
        self.assertItemsEqual(other_nodes + [parent], Node.objects.all())


class TestNodeNetworking(MAASServerTestCase):
    """Tests for methods on the `Node` related to networking."""

    def test_claim_auto_ips_works_with_multiple_auto_on_the_same_subnet(self):
        node = factory.make_Node()
        vlan = factory.make_VLAN()
        interfaces = [
            factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan)
            for _ in range(3)
        ]
        subnet = factory.make_Subnet(
            vlan=vlan, host_bits=random.randint(4, 12))
        for interface in interfaces:
            for _ in range(2):
                factory.make_StaticIPAddress(
                    alloc_type=IPADDRESS_TYPE.AUTO, ip="",
                    subnet=subnet, interface=interface)
        # No serialization error should be raised.
        node.claim_auto_ips()
        # Each interface should have assigned AUTO IP addresses and none
        # should overlap.
        assigned_ips = set()
        for interface in interfaces:
            for auto_ip in interface.ip_addresses.filter(
                    alloc_type=IPADDRESS_TYPE.AUTO):
                assigned_ips.add(str(auto_ip.ip))
        self.assertEqual(6, len(assigned_ips))

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
        self.assertEqual(set([True]), clearing_config)

    def test_set_initial_net_config_does_nothing_if_skip_networking(self):
        node = factory.make_Node_with_Interface_on_Subnet(skip_networking=True)
        boot_interface = node.get_boot_interface()
        node.set_initial_networking_configuration()
        boot_interface = reload_object(boot_interface)
        auto_ip = boot_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO).first()
        self.assertIsNone(auto_ip)

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
        self.assertEqual(subnet, auto_ip.subnet)

    def test_set_initial_networking_configuration_auto_on_managed_subnet(self):
        node = factory.make_Node()
        boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        subnet = factory.make_Subnet(vlan=boot_interface.vlan, dhcp_on=True)
        node.set_initial_networking_configuration()
        boot_interface = reload_object(boot_interface)
        auto_ip = boot_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO).first()
        self.assertIsNotNone(auto_ip)
        self.assertEqual(subnet, auto_ip.subnet)

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
        self.assertEqual(
            [(boot_interface.id, managed_subnet.id, gateway_ip)],
            node.get_best_guess_for_default_gateways())

    def test__ipv4_and_ipv6(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, disable_ipv4=False)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=str(network_v4.cidr))
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=str(network_v6.cidr))
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
        self.assertEqual(
            [(boot_interface.id, managed_subnet.id, gateway_ip)],
            node.get_best_guess_for_default_gateways())

    def test__managed_subnet_over_unmanaged(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, disable_ipv4=False)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        unmanaged_network = factory.make_ipv4_network()
        unmanaged_subnet = factory.make_Subnet(
            cidr=str(unmanaged_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(unmanaged_network),
            subnet=unmanaged_subnet, interface=interface)
        managed_network = factory.make_ipv4_network()
        managed_subnet = factory.make_ipv4_Subnet_with_IPRanges(
            cidr=str(managed_network.cidr), dhcp_on=True)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(managed_network),
            subnet=managed_subnet, interface=interface)
        gateway_ip = managed_subnet.gateway_ip
        self.assertEqual(
            [(interface.id, managed_subnet.id, gateway_ip)],
            node.get_best_guess_for_default_gateways())

    def test__bond_over_physical_interface(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, disable_ipv4=False)
        physical_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        physical_network = factory.make_ipv4_network()
        physical_subnet = factory.make_Subnet(
            cidr=str(physical_network.cidr))
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
            cidr=str(bond_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(bond_network),
            subnet=bond_subnet, interface=bond_interface)
        gateway_ip = bond_subnet.gateway_ip
        self.assertEqual(
            [(bond_interface.id, bond_subnet.id, gateway_ip)],
            node.get_best_guess_for_default_gateways())

    def test__physical_over_vlan_interface(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, disable_ipv4=False)
        physical_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        physical_network = factory.make_ipv4_network()
        physical_subnet = factory.make_Subnet(
            cidr=str(physical_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(physical_network),
            subnet=physical_subnet, interface=physical_interface)
        vlan_interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, node=node, parents=[physical_interface])
        vlan_network = factory.make_ipv4_network()
        vlan_subnet = factory.make_Subnet(
            cidr=str(vlan_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(vlan_network),
            subnet=vlan_subnet, interface=vlan_interface)
        gateway_ip = physical_subnet.gateway_ip
        self.assertEqual(
            [(physical_interface.id, physical_subnet.id, gateway_ip)],
            node.get_best_guess_for_default_gateways())

    def test__boot_interface_over_other_interfaces(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, disable_ipv4=False)
        physical_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        physical_network = factory.make_ipv4_network()
        physical_subnet = factory.make_Subnet(
            cidr=str(physical_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(physical_network),
            subnet=physical_subnet, interface=physical_interface)
        boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        boot_network = factory.make_ipv4_network()
        boot_subnet = factory.make_Subnet(
            cidr=str(boot_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(boot_network),
            subnet=boot_subnet, interface=boot_interface)
        node.boot_interface = boot_interface
        node.save()
        gateway_ip = boot_subnet.gateway_ip
        self.assertEqual(
            [(boot_interface.id, boot_subnet.id, gateway_ip)],
            node.get_best_guess_for_default_gateways())

    def test__sticky_ip_over_user_reserved(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, disable_ipv4=False)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        sticky_network = factory.make_ipv4_network()
        sticky_subnet = factory.make_Subnet(
            cidr=str(sticky_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(sticky_network),
            subnet=sticky_subnet, interface=interface)
        user_reserved_network = factory.make_ipv4_network()
        user_reserved_subnet = factory.make_Subnet(
            cidr=str(user_reserved_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=factory.make_User(),
            ip=factory.pick_ip_in_network(user_reserved_network),
            subnet=user_reserved_subnet, interface=interface)
        gateway_ip = sticky_subnet.gateway_ip
        self.assertEqual(
            [(interface.id, sticky_subnet.id, gateway_ip)],
            node.get_best_guess_for_default_gateways())

    def test__user_reserved_ip_over_auto(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, disable_ipv4=False)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        user_reserved_network = factory.make_ipv4_network()
        user_reserved_subnet = factory.make_Subnet(
            cidr=str(user_reserved_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=factory.make_User(),
            ip=factory.pick_ip_in_network(user_reserved_network),
            subnet=user_reserved_subnet, interface=interface)
        auto_network = factory.make_ipv4_network()
        auto_subnet = factory.make_Subnet(
            cidr=str(auto_network.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_network(auto_network),
            subnet=auto_subnet, interface=interface)
        gateway_ip = user_reserved_subnet.gateway_ip
        self.assertEqual(
            [(interface.id, user_reserved_subnet.id, gateway_ip)],
            node.get_best_guess_for_default_gateways())


class TestGetDefaultGateways(MAASServerTestCase):
    """Tests for `Node.get_default_gateways`."""

    def test__return_set_ipv4_and_ipv6(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, disable_ipv4=False)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=str(network_v4.cidr))
        network_v4_2 = factory.make_ipv4_network()
        subnet_v4_2 = factory.make_Subnet(
            cidr=str(network_v4_2.cidr), dhcp_on=True)
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=str(network_v6.cidr))
        network_v6_2 = factory.make_ipv6_network()
        subnet_v6_2 = factory.make_Subnet(
            cidr=str(network_v6_2.cidr), dhcp_on=True)
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
        self.assertEqual((
            (interface.id, subnet_v4_2.id, subnet_v4_2.gateway_ip),
            (interface.id, subnet_v6_2.id, subnet_v6_2.gateway_ip),
            ), node.get_default_gateways())

    def test__return_set_ipv4_and_guess_ipv6(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, disable_ipv4=False)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=str(network_v4.cidr))
        network_v4_2 = factory.make_ipv4_network()
        subnet_v4_2 = factory.make_Subnet(
            cidr=str(network_v4_2.cidr), dhcp_on=True)
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=str(network_v6.cidr))
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
        self.assertEqual((
            (interface.id, subnet_v4_2.id, subnet_v4_2.gateway_ip),
            (interface.id, subnet_v6.id, subnet_v6.gateway_ip),
            ), node.get_default_gateways())

    def test__return_set_ipv6_and_guess_ipv4(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, disable_ipv4=False)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=str(network_v4.cidr))
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=str(network_v6.cidr))
        network_v6_2 = factory.make_ipv6_network()
        subnet_v6_2 = factory.make_Subnet(
            cidr=str(network_v6_2.cidr), dhcp_on=True)
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
        self.assertEqual((
            (interface.id, subnet_v4.id, subnet_v4.gateway_ip),
            (interface.id, subnet_v6_2.id, subnet_v6_2.gateway_ip),
            ), node.get_default_gateways())

    def test__return_guess_ipv4_and_ipv6(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, disable_ipv4=False)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=str(network_v4.cidr))
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=str(network_v6.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v4),
            subnet=subnet_v4, interface=interface)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network_v6),
            subnet=subnet_v6, interface=interface)
        self.assertEqual((
            (interface.id, subnet_v4.id, subnet_v4.gateway_ip),
            (interface.id, subnet_v6.id, subnet_v6.gateway_ip),
            ), node.get_default_gateways())


class TestNode_Start(MAASServerTestCase):
    """Tests for Node.start()."""

    def setUp(self):
        super(TestNode_Start, self).setUp()
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        self.rpc_fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        self.patch_autospec(node_module, 'power_driver_check')

    def prepare_rpc_to_rack_controller(self, rack_controller):
        protocol = self.rpc_fixture.makeCluster(
            rack_controller,
            cluster_module.PowerOn)
        protocol.PowerOn.side_effect = always_succeed_with({})
        return protocol

    def make_acquired_node_with_interface(self, user, bmc_connected_to=None):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY, with_boot_disk=True,
            bmc_connected_to=bmc_connected_to)
        node.acquire(user)
        return node

    def test__sets_user_data(self):
        user = factory.make_User()
        rack_controller = factory.make_RackController()
        self.prepare_rpc_to_rack_controller(rack_controller)
        node = self.make_acquired_node_with_interface(user, rack_controller)
        self.patch(node, 'on_network').return_value = True
        user_data = factory.make_bytes()

        with post_commit_hooks:
            node.start(user, user_data=user_data)

        nud = NodeUserData.objects.get(node=node)
        self.assertEqual(user_data, nud.data)

    def test__resets_user_data(self):
        user = factory.make_User()
        rack_controller = factory.make_RackController()
        self.prepare_rpc_to_rack_controller(rack_controller)
        node = self.make_acquired_node_with_interface(user, rack_controller)
        self.patch(node, 'on_network').return_value = True
        user_data = factory.make_bytes()
        NodeUserData.objects.set_user_data(node, user_data)

        with post_commit_hooks:
            node.start(user, user_data=None)

        self.assertFalse(NodeUserData.objects.filter(node=node).exists())

    def test__claims_auto_ip_addresses(self):
        user = factory.make_User()
        rack_controller = factory.make_RackController()
        self.prepare_rpc_to_rack_controller(rack_controller)
        node = self.make_acquired_node_with_interface(user, rack_controller)
        self.patch(node, 'on_network').return_value = True

        claim_auto_ips = self.patch_autospec(
            node, "claim_auto_ips")

        with post_commit_hooks:
            node.start(user)

        self.expectThat(
            claim_auto_ips, MockCalledOnceWith())

    def test__only_claims_auto_addresses_when_allocated(self):
        user = factory.make_User()
        rack_controller = factory.make_RackController()
        self.prepare_rpc_to_rack_controller(rack_controller)
        node = self.make_acquired_node_with_interface(user, rack_controller)
        node.status = NODE_STATUS.BROKEN
        node.save()

        self.patch(node, "_get_bmc_client_connection_info").return_value = (
            [], [])
        self.patch(Node, "_power_control_node")
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
        rack_controller = factory.make_RackController()
        node = self.make_acquired_node_with_interface(
            user, bmc_connected_to=rack_controller)
        power_info = node.get_effective_power_info()

        power_control_node = self.patch(Node, "_power_control_node")
        power_control_node.return_value = defer.succeed(None)
        self.patch(Node, '_set_status_expires')

        with post_commit_hooks:
            node.start(user)

        # If the following fails the diff is big, but it's useful.
        self.maxDiff = None

        client_idents, fallback_idents = node._get_bmc_client_connection_info()
        self.expectThat(power_control_node, MockCalledOnceWith(
            power_on_node, node.system_id, node.hostname,
            client_idents, fallback_idents,
            power_info))

        # Set status expires was called.
        self.expectThat(
            Node._set_status_expires,
            MockCalledOnceWith(node.system_id, ANY))

    def test__node_start_checks_power_driver(self):
        client = MagicMock()
        client.ident = sentinel.ident
        mock_getClientFromIdentifiers = self.patch(
            node_module, "getClientFromIdentifiers")
        mock_getClientFromIdentifiers.return_value = defer.succeed(client)

        user = factory.make_User()
        rack_controller = factory.make_RackController()
        node = self.make_acquired_node_with_interface(
            user, bmc_connected_to=rack_controller)
        driver_check = self.patch(node_module, "power_driver_check")
        with post_commit_hooks:
            node.start(user)
        self.expectThat(driver_check, MockCalledOnceWith(
            client, node.get_effective_power_type()))

    def test__start_logs_user_request(self):
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.NEW, owner=admin)
        self.patch(node, '_start')
        register_event = self.patch(node, '_register_request_event')
        node.start(admin)
        self.assertThat(register_event, MockCalledOnceWith(
            admin, EVENT_TYPES.REQUEST_NODE_START, action='start',
            comment=None))

    def test__raises_failures_when_power_action_fails(self):
        class PraiseBeToJTVException(Exception):
            """A nonsense exception for this test.

            (Though jtv is praiseworthy, and that's worth noting).
            """

        power_control_node = self.patch(Node, '_power_control_node')
        power_control_node.return_value = defer.fail(
            PraiseBeToJTVException("Defiance is futile"))

        user = factory.make_User()
        rack_controller = factory.make_RackController()
        node = self.make_acquired_node_with_interface(
            user, bmc_connected_to=rack_controller)

        with ExpectedException(PraiseBeToJTVException):
            with post_commit_hooks:
                node.start(user)

    def test__marks_allocated_node_as_deploying(self):
        self.patch(Node, '_power_control_node')
        user = factory.make_User()
        rack_controller = factory.make_RackController()
        node = self.make_acquired_node_with_interface(
            user, bmc_connected_to=rack_controller)
        with post_commit_hooks:
            node.start(user)
        self.assertEqual(
            NODE_STATUS.DEPLOYING, reload_object(node).status)

    def test__does_not_change_state_of_deployed_node(self):
        self.patch(Node, "_power_control_node")
        user = factory.make_User()
        # Create a node that we can execute power actions on, so that we
        # exercise the whole of start().
        rack_controller = factory.make_RackController()
        node = factory.make_Node(
            power_type='manual', status=NODE_STATUS.DEPLOYED,
            owner=user, interface=True)
        boot_interface = node.get_boot_interface()
        boot_interface.vlan.dhcp_on = True
        boot_interface.vlan.primary_rack = rack_controller
        boot_interface.vlan.save()
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
        power_control_node = self.patch_autospec(Node, "_power_control_node")
        node.start(user)
        self.assertThat(power_control_node, MockNotCalled())

    def test__does_not_start_nodes_the_user_cannot_edit(self):
        power_control_node = self.patch_autospec(Node, "_power_control_node")
        owner = factory.make_User()
        node = self.make_acquired_node_with_interface(owner)

        user = factory.make_User()
        with ExpectedException(PermissionDenied):
            node.start(user)
            self.assertThat(power_control_node, MockNotCalled())

    def test__allows_admin_to_start_any_node(self):
        power_control_node = self.patch_autospec(Node, "_power_control_node")
        owner = factory.make_User()
        rack_controller = factory.make_RackController()
        node = self.make_acquired_node_with_interface(
            owner, bmc_connected_to=rack_controller)

        admin = factory.make_admin()
        with post_commit_hooks:
            node.start(admin)

        client_idents, fallback_idents = node._get_bmc_client_connection_info()
        self.expectThat(
            power_control_node, MockCalledOnceWith(
                power_on_node, node.system_id, node.hostname,
                client_idents, fallback_idents,
                node.get_effective_power_info()))

    def test__releases_auto_ips_when_power_action_fails(self):
        exception_type = factory.make_exception_type()

        power_control_node = self.patch(Node, '_power_control_node')
        power_control_node.return_value = defer.fail(
            exception_type("He's fallen in the water!"))

        user = factory.make_User()
        rack_controller = factory.make_RackController()
        node = self.make_acquired_node_with_interface(
            user, bmc_connected_to=rack_controller)

        release_auto_ips = self.patch_autospec(
            node, "release_auto_ips")

        with ExpectedException(exception_type):
            with post_commit_hooks:
                node.start(user)

        self.assertThat(release_auto_ips, MockCalledOnceWith())

    def test_on_network_returns_true_when_connected(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.ALLOCATED)
        self.assertTrue(node.on_network())

    def test_on_network_returns_false_when_not_connected(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        self.assertFalse(node.on_network())

    def test_storage_layout_issues_is_valid_when_flat(self):
        node = factory.make_Node()
        self.assertEqual([], node.storage_layout_issues())

    def test_storage_layout_issues_returns_valid_with_boot_and_bcache(self):
        node = factory.make_Node(with_boot_disk=False)
        boot_partition = factory.make_Partition(node=node)
        factory.make_Filesystem(partition=boot_partition, mount_point='/boot')
        fs_group = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.BCACHE)
        bcache = fs_group.virtual_device
        factory.make_Filesystem(block_device=bcache, mount_point="/")
        self.assertEqual([], node.storage_layout_issues())

    def test_storage_layout_issues_returns_invalid_when_no_disk(self):
        node = factory.make_Node(with_boot_disk=False)
        self.assertEqual(
            ["Specify a storage device to be able to deploy this node.",
             "Mount the root '/' filesystem to be able to deploy this node."],
            node.storage_layout_issues())

    def test_storage_layout_issues_returns_invalid_when_root_on_bcache(self):
        node = factory.make_Node(with_boot_disk=False)
        factory.make_Partition(node=node)
        fs_group = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.BCACHE)
        bcache = fs_group.virtual_device
        factory.make_Filesystem(block_device=bcache, mount_point="/")
        self.assertEqual(
            ["This node cannot be deployed because it cannot boot from a "
             "bcache volume. Mount /boot on a non-bcache device to be able to "
             "deploy this node."], node.storage_layout_issues())


class TestNode_Stop(MAASServerTestCase):
    """Tests for Node.stop()."""

    def setUp(self):
        super(TestNode_Stop, self).setUp()
        self.patch_autospec(node_module, 'power_driver_check')

    def make_node_with_interface(
            self, user, power_type="virsh", bmc_connected_to=None):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY,
            power_type=power_type, with_boot_disk=True,
            bmc_connected_to=bmc_connected_to)
        node.acquire(user)
        return node

    def test__stops_nodes(self):
        power_control_node = self.patch_autospec(
            Node, "_power_control_node")

        user = factory.make_User()
        rack_controller = factory.make_RackController()
        node = self.make_node_with_interface(
            user, bmc_connected_to=rack_controller)
        expected_power_info = node.get_effective_power_info()

        stop_mode = factory.make_name('stop-mode')
        expected_power_info.power_parameters['power_off_mode'] = stop_mode
        with post_commit_hooks:
            node.stop(user, stop_mode)

        # If the following fails the diff is big, but it's useful.
        self.maxDiff = None

        client_idents, fallback_idents = node._get_bmc_client_connection_info()
        self.expectThat(
            power_control_node, MockCalledOnceWith(
                power_off_node, node.system_id, node.hostname,
                client_idents, fallback_idents,
                expected_power_info))

    def test__fallback_to_pxe_rack_controllers(self):
        client = MagicMock()
        client.ident = sentinel.ident
        mock_getClientFromIdentifiers = self.patch(
            node_module, "getClientFromIdentifiers")
        mock_getClientFromIdentifiers.side_effect = [
            defer.fail(NoConnectionsAvailable()),
            defer.succeed(client),
        ]

        user = factory.make_User()
        rack_controller = factory.make_RackController()
        node = self.make_node_with_interface(user)
        boot_interface = node.get_boot_interface()
        boot_interface.vlan.dhcp_on = True
        boot_interface.vlan.primary_rack = rack_controller
        boot_interface.vlan.save()

        driver_check = self.patch(node_module, "power_driver_check")
        with post_commit_hooks:
            node.stop(user, factory.make_name('stop-mode'))
        self.expectThat(driver_check, MockCalledOnceWith(
            client, node.get_effective_power_type()))
        self.expectThat(mock_getClientFromIdentifiers, MockCallsMatch(
            call([]),
            call([rack_controller.system_id])))

    def test__node_stop_checks_power_driver(self):
        client = MagicMock()
        client.ident = sentinel.ident
        mock_getClientFromIdentifiers = self.patch(
            node_module, "getClientFromIdentifiers")
        mock_getClientFromIdentifiers.return_value = defer.succeed(client)

        user = factory.make_User()
        rack_controller = factory.make_RackController()
        node = self.make_node_with_interface(
            user, bmc_connected_to=rack_controller)
        driver_check = self.patch(node_module, "power_driver_check")
        with post_commit_hooks:
            node.stop(user, factory.make_name('stop-mode'))
        self.expectThat(driver_check, MockCalledOnceWith(
            client, node.get_effective_power_type()))

    def test__does_not_stop_nodes_the_user_cannot_edit(self):
        power_off_node = self.patch_autospec(node_module, "power_off_node")
        owner = factory.make_User()
        node = self.make_node_with_interface(owner)

        user = factory.make_User()
        self.assertRaises(PermissionDenied, node.stop, user)
        self.assertThat(power_off_node, MockNotCalled())

    def test_stop_logs_user_request(self):
        admin = factory.make_admin()
        rack_controller = factory.make_RackController()
        node = self.make_node_with_interface(
            admin, bmc_connected_to=rack_controller)
        self.patch_autospec(Node, "_power_control_node")
        register_event = self.patch(node, '_register_request_event')
        with post_commit_hooks:
            node.stop(admin)
        self.assertThat(register_event, MockCalledOnceWith(
            admin, EVENT_TYPES.REQUEST_NODE_STOP, action='stop', comment=None))

    def test__allows_admin_to_stop_any_node(self):
        power_control_node = self.patch_autospec(
            Node, "_power_control_node")
        owner = factory.make_User()
        rack_controller = factory.make_RackController()
        node = self.make_node_with_interface(
            owner, bmc_connected_to=rack_controller)
        expected_power_info = node.get_effective_power_info()

        stop_mode = factory.make_name('stop-mode')
        expected_power_info.power_parameters['power_off_mode'] = stop_mode

        admin = factory.make_admin()
        with post_commit_hooks:
            node.stop(admin, stop_mode)

        client_idents, fallback_idents = node._get_bmc_client_connection_info()
        self.expectThat(
            power_control_node, MockCalledOnceWith(
                power_off_node, node.system_id, node.hostname,
                client_idents, fallback_idents, expected_power_info))

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
        node = self.make_node_with_interface(user, power_type="manual")
        node.save()

        power_off_node = self.patch_autospec(node_module, "power_off_node")
        node.stop(user)
        self.assertThat(power_off_node, MockNotCalled())

    def test__propagates_failures_when_power_action_fails(self):
        fake_exception_type = factory.make_exception_type()

        mock_getClientFromIdentifiers = self.patch(
            node_module, 'getClientFromIdentifiers')
        mock_getClientFromIdentifiers.return_value = defer.fail(
            fake_exception_type("Soon be the weekend!"))

        user = factory.make_User()
        rack_controller = factory.make_RackController()
        node = self.make_node_with_interface(
            user, bmc_connected_to=rack_controller)

        with ExpectedException(fake_exception_type):
            with post_commit_hooks:
                node.stop(user)

    def test__returns_Deferred_if_power_action_sent(self):
        user = factory.make_User()
        rack_controller = factory.make_RackController()
        node = self.make_node_with_interface(
            user, power_type="virsh", bmc_connected_to=rack_controller)

        self.patch_autospec(Node, "_power_control_node")
        with post_commit_hooks:
            self.assertThat(node.stop(user), IsInstance(defer.Deferred))


class TestRackControllerUpdateInterfaces(MAASServerTestCase):

    def create_empty_rack_controller(self):
        node = factory.make_Node(
            node_type=NODE_TYPE.RACK_CONTROLLER)
        return typecast_node(node, RackController)

    def test__all_new_physical_interfaces_no_links(self):
        rack = self.create_empty_rack_controller()
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth1": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": False,
            },
        }
        rack.update_interfaces(interfaces)
        eth0 = Interface.objects.get(name="eth0", node=rack)
        self.assertThat(
            eth0, MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
            ))
        self.assertThat(list(eth0.parents.all()), Equals([]))
        eth1 = Interface.objects.get(name="eth1", node=rack)
        self.assertThat(
            eth1, MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth1",
                mac_address=interfaces["eth1"]["mac_address"],
                enabled=False,
            ))
        self.assertThat(list(eth1.parents.all()), Equals([]))
        # Since order is not kept in dictionary and it doesn't matter in this
        # case, we check that at least two different VLANs and one is the
        # default from the default fabric.
        observed_vlans = {eth0.vlan, eth1.vlan}
        self.assertThat(observed_vlans, HasLength(2))
        self.assertThat(
            observed_vlans,
            Contains(Fabric.objects.get_default_fabric().get_default_vlan()))

    def test__new_physical_with_new_subnet_link(self):
        rack = self.create_empty_rack_controller()
        network = factory.make_ip4_or_6_network()
        ip = factory.pick_ip_in_network(network)
        gateway_ip = factory.pick_ip_in_network(network, but_not=[ip])
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [{
                    "mode": "static",
                    "address": "%s/%d" % (str(ip), network.prefixlen),
                    "gateway": str(gateway_ip),
                }],
                "enabled": True,
            },
        }
        rack.update_interfaces(interfaces)
        eth0 = Interface.objects.get(name="eth0", node=rack)
        default_vlan = Fabric.objects.get_default_fabric().get_default_vlan()
        self.assertThat(
            eth0, MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
                vlan=default_vlan,
            ))
        subnet = Subnet.objects.get(cidr=str(network.cidr))
        self.assertThat(
            subnet, MatchesStructure.byEquality(
                name=str(network.cidr),
                cidr=str(network.cidr),
                vlan=default_vlan,
                space=Space.objects.get_default_space(),
                gateway_ip=gateway_ip,
            ))
        eth0_addresses = list(eth0.ip_addresses.all())
        self.assertThat(eth0_addresses, HasLength(1))
        self.assertThat(
            eth0_addresses[0], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=ip,
                subnet=subnet,
            ))

    def test__new_physical_with_dhcp_link(self):
        rack = self.create_empty_rack_controller()
        network = factory.make_ip4_or_6_network()
        ip = factory.pick_ip_in_network(network)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [{
                    "mode": "dhcp",
                    "address": "%s/%d" % (str(ip), network.prefixlen),
                }],
                "enabled": True,
            },
        }
        rack.update_interfaces(interfaces)
        eth0 = Interface.objects.get(name="eth0", node=rack)
        default_vlan = Fabric.objects.get_default_fabric().get_default_vlan()
        self.assertThat(
            eth0, MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
                vlan=default_vlan,
            ))
        dhcp_addresses = list(eth0.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.DHCP))
        self.assertThat(dhcp_addresses, HasLength(1))
        self.assertThat(
            dhcp_addresses[0], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DHCP,
                ip=None,
            ))
        subnet = Subnet.objects.get(cidr=str(network.cidr))
        self.assertThat(
            subnet, MatchesStructure.byEquality(
                name=str(network.cidr),
                cidr=str(network.cidr),
                vlan=default_vlan,
                space=Space.objects.get_default_space(),
            ))
        discovered_addresses = list(eth0.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.DISCOVERED))
        self.assertThat(discovered_addresses, HasLength(1))
        self.assertThat(
            discovered_addresses[0], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DISCOVERED,
                ip=ip,
                subnet=subnet,
            ))

    def test__new_physical_with_multiple_dhcp_link(self):
        rack = self.create_empty_rack_controller()
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [
                    {
                        "mode": "dhcp",
                    },
                    {
                        "mode": "dhcp",
                    },
                ],
                "enabled": True,
            },
        }
        rack.update_interfaces(interfaces)
        eth0 = Interface.objects.get(name="eth0", node=rack)
        default_vlan = Fabric.objects.get_default_fabric().get_default_vlan()
        self.assertThat(
            eth0, MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
                vlan=default_vlan,
            ))
        eth0_addresses = list(eth0.ip_addresses.all())
        self.assertThat(eth0_addresses, HasLength(2))
        self.assertThat(
            eth0_addresses[0], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DHCP,
                ip=None,
            ))
        self.assertThat(
            eth0_addresses[1], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DHCP,
                ip=None,
            ))

    def test__new_physical_with_existing_subnet_link_with_gateway(self):
        rack = self.create_empty_rack_controller()
        subnet = factory.make_Subnet()
        network = subnet.get_ipnetwork()
        gateway_ip = factory.pick_ip_in_network(network)
        subnet.gateway_ip = gateway_ip
        subnet.save()
        ip = factory.pick_ip_in_network(network, but_not=[gateway_ip])
        diff_gateway_ip = factory.pick_ip_in_network(
            network, but_not=[gateway_ip, ip])
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [{
                    "mode": "static",
                    "address": "%s/%d" % (str(ip), network.prefixlen),
                    "gateway": str(diff_gateway_ip),
                }],
                "enabled": True,
            },
        }
        rack.update_interfaces(interfaces)
        eth0 = Interface.objects.get(name="eth0", node=rack)
        self.assertThat(
            eth0, MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
                vlan=subnet.vlan,
            ))
        # Check that the gateway IP didn't change.
        self.assertThat(
            subnet, MatchesStructure.byEquality(
                gateway_ip=gateway_ip,
            ))
        eth0_addresses = list(eth0.ip_addresses.all())
        self.assertThat(eth0_addresses, HasLength(1))
        self.assertThat(
            eth0_addresses[0], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=ip,
                subnet=subnet,
            ))

    def test__new_physical_with_existing_subnet_link_without_gateway(self):
        rack = self.create_empty_rack_controller()
        subnet = factory.make_Subnet()
        subnet.gateway_ip = None
        subnet.save()
        network = subnet.get_ipnetwork()
        gateway_ip = factory.pick_ip_in_network(network)
        ip = factory.pick_ip_in_network(network, but_not=[gateway_ip])
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [{
                    "mode": "static",
                    "address": "%s/%d" % (str(ip), network.prefixlen),
                    "gateway": str(gateway_ip),
                }],
                "enabled": True,
            },
        }
        rack.update_interfaces(interfaces)
        eth0 = Interface.objects.get(name="eth0", node=rack)
        self.assertThat(
            eth0, MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
                vlan=subnet.vlan,
            ))
        # Check that the gateway IP did get set.
        self.assertThat(
            reload_object(subnet), MatchesStructure.byEquality(
                gateway_ip=gateway_ip,
            ))
        eth0_addresses = list(eth0.ip_addresses.all())
        self.assertThat(eth0_addresses, HasLength(1))
        self.assertThat(
            eth0_addresses[0], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=ip,
                subnet=subnet,
            ))

    def test__new_physical_with_multiple_subnets(self):
        rack = self.create_empty_rack_controller()
        vlan = factory.make_VLAN()
        subnet1 = factory.make_Subnet(vlan=vlan)
        ip1 = factory.pick_ip_in_Subnet(subnet1)
        subnet2 = factory.make_Subnet(vlan=vlan)
        ip2 = factory.pick_ip_in_Subnet(subnet2)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [
                    {
                        "mode": "static",
                        "address": "%s/%d" % (
                            str(ip1), subnet1.get_ipnetwork().prefixlen),
                    },
                    {
                        "mode": "static",
                        "address": "%s/%d" % (
                            str(ip2), subnet2.get_ipnetwork().prefixlen),
                    },
                ],
                "enabled": True,
            },
        }
        rack.update_interfaces(interfaces)
        eth0 = Interface.objects.get(name="eth0", node=rack)
        self.assertThat(
            eth0, MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
                vlan=vlan,
            ))
        eth0_addresses = list(eth0.ip_addresses.order_by('id'))
        self.assertThat(eth0_addresses, HasLength(2))
        self.assertThat(
            eth0_addresses[0], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=ip1,
                subnet=subnet1,
            ))
        self.assertThat(
            eth0_addresses[1], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=ip2,
                subnet=subnet2,
            ))

    def test__existing_physical_with_existing_static_link(self):
        rack = self.create_empty_rack_controller()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip,
            subnet=subnet, interface=interface)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": interface.mac_address,
                "parents": [],
                "links": [{
                    "mode": "static",
                    "address": "%s/%d" % (
                        str(ip), subnet.get_ipnetwork().prefixlen),
                }],
                "enabled": True,
            },
        }
        rack.update_interfaces(interfaces)
        self.assertThat(rack.interface_set.count(), Equals(1))
        self.assertThat(
            reload_object(interface), MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interface.mac_address,
                enabled=True,
                vlan=vlan,
            ))
        addresses = list(interface.ip_addresses.all())
        self.assertThat(addresses, HasLength(1))
        self.assertThat(
            addresses[0], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=ip,
                subnet=subnet,
            ))

    def test__existing_physical_with_existing_auto_link(self):
        rack = self.create_empty_rack_controller()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip=ip,
            subnet=subnet, interface=interface)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": interface.mac_address,
                "parents": [],
                "links": [{
                    "mode": "static",
                    "address": "%s/%d" % (
                        str(ip), subnet.get_ipnetwork().prefixlen),
                }],
                "enabled": True,
            },
        }
        rack.update_interfaces(interfaces)
        self.assertThat(rack.interface_set.count(), Equals(1))
        self.assertThat(
            reload_object(interface), MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interface.mac_address,
                enabled=True,
                vlan=vlan,
            ))
        addresses = list(interface.ip_addresses.all())
        self.assertThat(addresses, HasLength(1))
        self.assertThat(
            addresses[0], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=ip,
                subnet=subnet,
            ))

    def test__existing_physical_removes_old_links(self):
        rack = self.create_empty_rack_controller()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip=ip,
            subnet=subnet, interface=interface)
        extra_ips = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.AUTO, subnet=subnet,
                interface=interface)
            for _ in range(3)
        ]
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": interface.mac_address,
                "parents": [],
                "links": [{
                    "mode": "static",
                    "address": "%s/%d" % (
                        str(ip), subnet.get_ipnetwork().prefixlen),
                }],
                "enabled": True,
            },
        }
        rack.update_interfaces(interfaces)
        self.assertThat(rack.interface_set.count(), Equals(1))
        self.assertThat(
            reload_object(interface), MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interface.mac_address,
                enabled=True,
                vlan=vlan,
            ))
        addresses = list(interface.ip_addresses.all())
        self.assertThat(addresses, HasLength(1))
        self.assertThat(
            addresses[0], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=ip,
                subnet=subnet,
            ))
        for extra_ip in extra_ips:
            self.expectThat(reload_object(extra_ip), Is(None))

    def test__existing_physical_with_links_new_vlan_no_links(self):
        rack = self.create_empty_rack_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip=ip,
            subnet=subnet, interface=interface)
        vid_on_fabric = random.randint(1, 4095)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": interface.mac_address,
                "parents": [],
                "links": [{
                    "mode": "static",
                    "address": "%s/%d" % (
                        str(ip), subnet.get_ipnetwork().prefixlen),
                }],
                "enabled": True,
            },
        }
        interfaces["eth0.%d" % vid_on_fabric] = {
            "type": "vlan",
            "parents": ["eth0"],
            "links": [],
            "enabled": True,
            "vid": vid_on_fabric,
        }
        rack.update_interfaces(interfaces)
        self.assertThat(rack.interface_set.count(), Equals(2))
        self.assertThat(
            reload_object(interface), MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interface.mac_address,
                enabled=True,
                vlan=vlan,
            ))
        addresses = list(interface.ip_addresses.all())
        self.assertThat(addresses, HasLength(1))
        self.assertThat(
            addresses[0], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=ip,
                subnet=subnet,
            ))
        created_vlan = VLAN.objects.get(fabric=fabric, vid=vid_on_fabric)
        vlan_interface = VLANInterface.objects.get(
            node=rack, vlan=created_vlan)
        self.assertThat(
            vlan_interface, MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="eth0.%d" % vid_on_fabric,
                enabled=True,
                vlan=created_vlan,
            ))

    def test__existing_physical_with_links_new_vlan_new_links(self):
        rack = self.create_empty_rack_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip=ip,
            subnet=subnet, interface=interface)
        vid_on_fabric = random.randint(1, 4095)
        vlan_network = factory.make_ip4_or_6_network()
        vlan_ip = factory.pick_ip_in_network(vlan_network)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": interface.mac_address,
                "parents": [],
                "links": [{
                    "mode": "static",
                    "address": "%s/%d" % (
                        str(ip), subnet.get_ipnetwork().prefixlen),
                }],
                "enabled": True,
            },
        }
        interfaces["eth0.%d" % vid_on_fabric] = {
            "type": "vlan",
            "parents": ["eth0"],
            "links": [{
                "mode": "static",
                "address": "%s/%d" % (
                    str(vlan_ip), vlan_network.prefixlen),
            }],
            "enabled": True,
            "vid": vid_on_fabric,
        }
        rack.update_interfaces(interfaces)
        self.assertThat(rack.interface_set.count(), Equals(2))
        self.assertThat(
            reload_object(interface), MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interface.mac_address,
                enabled=True,
                vlan=vlan,
            ))
        parent_addresses = list(interface.ip_addresses.all())
        self.assertThat(parent_addresses, HasLength(1))
        self.assertThat(
            parent_addresses[0], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=ip,
                subnet=subnet,
            ))
        created_vlan = VLAN.objects.get(fabric=fabric, vid=vid_on_fabric)
        vlan_interface = VLANInterface.objects.get(
            node=rack, vlan=created_vlan)
        self.assertThat(
            vlan_interface, MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="eth0.%d" % vid_on_fabric,
                enabled=True,
                vlan=created_vlan,
            ))
        vlan_subnet = Subnet.objects.get(cidr=str(vlan_network.cidr))
        self.assertThat(
            vlan_subnet, MatchesStructure.byEquality(
                name=str(vlan_network.cidr),
                cidr=str(vlan_network.cidr),
                vlan=created_vlan,
                space=Space.objects.get_default_space(),
            ))
        vlan_addresses = list(vlan_interface.ip_addresses.all())
        self.assertThat(vlan_addresses, HasLength(1))
        self.assertThat(
            vlan_addresses[0], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=vlan_ip,
                subnet=vlan_subnet,
            ))

    def test__existing_physical_with_links_new_vlan_wrong_subnet_vid(self):
        rack = self.create_empty_rack_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip=ip,
            subnet=subnet, interface=interface)
        vid_on_fabric = random.randint(1, 4095)
        wrong_subnet = factory.make_Subnet()
        vlan_ip = factory.pick_ip_in_Subnet(wrong_subnet)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": interface.mac_address,
                "parents": [],
                "links": [{
                    "mode": "static",
                    "address": "%s/%d" % (
                        str(ip), subnet.get_ipnetwork().prefixlen),
                }],
                "enabled": True,
            },
        }
        interfaces["eth0.%d" % vid_on_fabric] = {
            "type": "vlan",
            "parents": ["eth0"],
            "links": [{
                "mode": "static",
                "address": "%s/%d" % (
                    str(vlan_ip), wrong_subnet.get_ipnetwork().prefixlen),
            }],
            "enabled": True,
            "vid": vid_on_fabric,
        }
        maaslog = self.patch(node_module, "maaslog")
        rack.update_interfaces(interfaces)
        self.assertThat(rack.interface_set.count(), Equals(2))
        self.assertThat(
            reload_object(interface), MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interface.mac_address,
                enabled=True,
                vlan=vlan,
            ))
        parent_addresses = list(interface.ip_addresses.all())
        self.assertThat(parent_addresses, HasLength(1))
        self.assertThat(
            parent_addresses[0], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=ip,
                subnet=subnet,
            ))
        created_vlan = VLAN.objects.get(fabric=fabric, vid=vid_on_fabric)
        vlan_interface = VLANInterface.objects.get(
            node=rack, vlan=created_vlan)
        self.assertThat(
            vlan_interface, MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="eth0.%d" % vid_on_fabric,
                enabled=True,
                vlan=created_vlan,
            ))
        vlan_addresses = list(vlan_interface.ip_addresses.all())
        self.assertThat(vlan_addresses, HasLength(0))
        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "Unable to update IP address '%s' assigned to "
                "interface '%s' on rack controller '%s'. Subnet '%s' "
                "for IP address is not on VLAN '%s.%d'." % (
                    vlan_ip, "eth0.%d" % vid_on_fabric, rack.hostname,
                    wrong_subnet.name, wrong_subnet.vlan.fabric.name,
                    wrong_subnet.vlan.vid)))

    def test__existing_physical_with_no_links_new_vlan_no_links(self):
        rack = self.create_empty_rack_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        vid_on_fabric = random.randint(1, 4095)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": interface.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
        }
        interfaces["eth0.%d" % vid_on_fabric] = {
            "type": "vlan",
            "parents": ["eth0"],
            "links": [],
            "enabled": True,
            "vid": vid_on_fabric,
        }
        rack.update_interfaces(interfaces)
        self.assertThat(rack.interface_set.count(), Equals(2))
        self.assertThat(
            reload_object(interface), MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interface.mac_address,
                enabled=True,
                vlan=vlan,
            ))
        created_vlan = VLAN.objects.get(fabric=fabric, vid=vid_on_fabric)
        vlan_interface = VLANInterface.objects.get(
            node=rack, vlan=created_vlan)
        self.assertThat(
            vlan_interface, MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="eth0.%d" % vid_on_fabric,
                enabled=True,
                vlan=created_vlan,
            ))

    def test__existing_physical_with_no_links_new_vlan_with_links(self):
        rack = self.create_empty_rack_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        other_fabric = factory.make_Fabric()
        new_vlan = factory.make_VLAN(fabric=other_fabric)
        subnet = factory.make_Subnet(vlan=new_vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": interface.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
        }
        interfaces["eth0.%d" % new_vlan.vid] = {
            "type": "vlan",
            "parents": ["eth0"],
            "links": [{
                "mode": "static",
                "address": "%s/%d" % (
                    str(ip), subnet.get_ipnetwork().prefixlen)
            }],
            "enabled": True,
            "vid": new_vlan.vid,
        }
        rack.update_interfaces(interfaces)
        self.assertThat(rack.interface_set.count(), Equals(2))
        self.assertThat(
            reload_object(interface), MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interface.mac_address,
                enabled=True,
                vlan=other_fabric.get_default_vlan(),
            ))
        vlan_interface = VLANInterface.objects.get(
            node=rack, vlan=new_vlan)
        self.assertThat(
            vlan_interface, MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="eth0.%d" % new_vlan.vid,
                enabled=True,
                vlan=new_vlan,
            ))
        vlan_addresses = list(vlan_interface.ip_addresses.all())
        self.assertThat(vlan_addresses, HasLength(1))
        self.assertThat(
            vlan_addresses[0], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=ip,
                subnet=subnet,
            ))

    def test__existing_physical_with_no_links_vlan_with_wrong_subnet(self):
        rack = self.create_empty_rack_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        new_vlan = factory.make_VLAN(fabric=fabric)
        vlan_interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, vlan=new_vlan, parents=[interface])
        wrong_subnet = factory.make_Subnet()
        ip = factory.pick_ip_in_Subnet(wrong_subnet)
        links_to_remove = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.STICKY, interface=vlan_interface)
            for _ in range(3)
        ]
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": interface.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
        }
        interfaces["eth0.%d" % new_vlan.vid] = {
            "type": "vlan",
            "parents": ["eth0"],
            "links": [{
                "mode": "static",
                "address": "%s/%d" % (
                    str(ip), wrong_subnet.get_ipnetwork().prefixlen)
            }],
            "enabled": True,
            "vid": new_vlan.vid,
        }
        maaslog = self.patch(node_module, "maaslog")
        rack.update_interfaces(interfaces)
        self.assertThat(rack.interface_set.count(), Equals(2))
        self.assertThat(
            reload_object(interface), MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interface.mac_address,
                enabled=True,
                vlan=vlan,
            ))
        self.assertThat(
            reload_object(vlan_interface), MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="eth0.%d" % new_vlan.vid,
                enabled=True,
                vlan=new_vlan,
            ))
        vlan_addresses = list(vlan_interface.ip_addresses.all())
        self.assertThat(vlan_addresses, HasLength(1))
        self.assertThat(
            vlan_addresses[0], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=None,
                subnet=None,
            ))
        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "Unable to correctly identify VLAN for interface '%s' "
                "on rack controller '%s'. Placing interface on "
                "VLAN '%s.%d' without address assignments." % (
                    "eth0.%d" % new_vlan.vid, rack.hostname,
                    new_vlan.fabric.name, new_vlan.vid)))
        for link in links_to_remove:
            self.expectThat(reload_object(link), Is(None))

    def test__bond_with_existing_parents(self):
        rack = self.create_empty_rack_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth1": {
                "type": "physical",
                "mac_address": eth1.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "bond0": {
                "type": "bond",
                "mac_address": factory.make_mac_address(),
                "parents": ["eth0", "eth1"],
                "links": [],
                "enabled": True,
            },
        }
        rack.update_interfaces(interfaces)
        self.assertThat(rack.interface_set.count(), Equals(3))
        bond_interface = BondInterface.objects.get(
            node=rack, mac_address=interfaces["bond0"]["mac_address"])
        self.assertThat(
            bond_interface, MatchesStructure.byEquality(
                type=INTERFACE_TYPE.BOND,
                name="bond0",
                mac_address=interfaces["bond0"]["mac_address"],
                enabled=True,
                vlan=vlan,
            ))
        self.assertThat(
            [parent.name for parent in bond_interface.parents.all()],
            MatchesSetwise(Equals("eth0"), Equals("eth1")))

    def test__bond_updates_existing_bond(self):
        rack = self.create_empty_rack_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND, vlan=vlan, parents=[eth0, eth1], node=rack,
            name="bond0", mac_address=factory.make_mac_address())
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth1": {
                "type": "physical",
                "mac_address": eth1.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "bond0": {
                "type": "bond",
                "mac_address": factory.make_mac_address(),
                "parents": ["eth0"],
                "links": [],
                "enabled": True,
            },
        }
        rack.update_interfaces(interfaces)
        self.assertThat(rack.interface_set.count(), Equals(3))
        self.assertThat(
            reload_object(bond0), MatchesStructure.byEquality(
                type=INTERFACE_TYPE.BOND,
                name="bond0",
                mac_address=interfaces["bond0"]["mac_address"],
                enabled=True,
                vlan=vlan,
            ))
        self.assertThat(
            [parent.name for parent in bond0.parents.all()],
            Equals(["eth0"]))

    def test__bond_moves_bond_with_mac_address(self):
        rack = self.create_empty_rack_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        other_node = factory.make_Node()
        other_nic = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=other_node)
        bond_mac_address = factory.make_mac_address()
        bond_to_move = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[other_nic], node=other_node,
            mac_address=bond_mac_address)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth1": {
                "type": "physical",
                "mac_address": eth1.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "bond0": {
                "type": "bond",
                "mac_address": bond_mac_address,
                "parents": ["eth0", "eth1"],
                "links": [],
                "enabled": True,
            },
        }
        rack.update_interfaces(interfaces)
        self.assertThat(rack.interface_set.count(), Equals(3))
        self.assertThat(
            reload_object(bond_to_move), MatchesStructure.byEquality(
                type=INTERFACE_TYPE.BOND,
                name="bond0",
                mac_address=bond_mac_address,
                enabled=True,
                node=rack,
                vlan=vlan,
            ))
        self.assertThat(
            [parent.name for parent in bond_to_move.parents.all()],
            MatchesSetwise(Equals("eth0"), Equals("eth1")))

    def test__bond_creates_link_updates_parent_vlan(self):
        rack = self.create_empty_rack_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[eth0, eth1], vlan=vlan)
        other_fabric = factory.make_Fabric()
        bond0_vlan = other_fabric.get_default_vlan()
        subnet = factory.make_Subnet(vlan=bond0_vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth1": {
                "type": "physical",
                "mac_address": eth1.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "bond0": {
                "type": "bond",
                "mac_address": bond0.mac_address,
                "parents": ["eth0", "eth1"],
                "links": [{
                    "mode": "static",
                    "address": "%s/%d" % (
                        str(ip), subnet.get_ipnetwork().prefixlen),
                }],
                "enabled": True,
            },
        }
        rack.update_interfaces(interfaces)
        self.assertThat(rack.interface_set.count(), Equals(3))
        self.assertThat(
            reload_object(eth0), MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=eth0.mac_address,
                enabled=True,
                vlan=bond0_vlan,
            ))
        self.assertThat(
            reload_object(eth1), MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth1",
                mac_address=eth1.mac_address,
                enabled=True,
                vlan=bond0_vlan,
            ))
        self.assertThat(
            reload_object(bond0), MatchesStructure.byEquality(
                type=INTERFACE_TYPE.BOND,
                name="bond0",
                mac_address=bond0.mac_address,
                enabled=True,
                node=rack,
                vlan=bond0_vlan,
            ))
        self.assertThat(
            [parent.name for parent in bond0.parents.all()],
            MatchesSetwise(Equals("eth0"), Equals("eth1")))

    def test__removes_missing_interfaces(self):
        rack = self.create_empty_rack_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[eth0, eth1], vlan=vlan)
        rack.update_interfaces({})
        self.assertThat(reload_object(eth0), Is(None))
        self.assertThat(reload_object(eth1), Is(None))
        self.assertThat(reload_object(bond0), Is(None))

    def test__removes_one_bond_parent(self):
        rack = self.create_empty_rack_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[eth0, eth1], vlan=vlan)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "bond0": {
                "type": "bond",
                "mac_address": bond0.mac_address,
                "parents": ["eth0"],
                "links": [],
                "enabled": True,
            },
        }
        rack.update_interfaces(interfaces)
        self.assertThat(reload_object(eth0), Not(Is(None)))
        self.assertThat(reload_object(eth1), Is(None))
        self.assertThat(reload_object(bond0), Not(Is(None)))

    def test__removes_one_bond_and_one_parent(self):
        rack = self.create_empty_rack_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan)
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[eth0, eth1], vlan=vlan)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": eth0.mac_address,
                "parents": [],
                "links": [],
                "enabled": True,
            },
        }
        rack.update_interfaces(interfaces)
        self.assertThat(reload_object(eth0), Not(Is(None)))
        self.assertThat(reload_object(eth1), Is(None))
        self.assertThat(reload_object(bond0), Is(None))

    def test__all_new_complex_interfaces(self):
        rack = self.create_empty_rack_controller()
        bond0_fabric = factory.make_Fabric()
        bond0_untagged = bond0_fabric.get_default_vlan()
        bond0_subnet = factory.make_Subnet(vlan=bond0_untagged)
        bond0_ip = factory.pick_ip_in_Subnet(bond0_subnet)
        bond0_vlan = factory.make_VLAN(fabric=bond0_fabric)
        bond0_vlan_subnet = factory.make_Subnet(vlan=bond0_vlan)
        bond0_vlan_ip = factory.pick_ip_in_Subnet(bond0_vlan_subnet)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "eth1": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            },
            "bond0": {
                "type": "bond",
                "mac_address": factory.make_mac_address(),
                "parents": ["eth0", "eth1"],
                "links": [{
                    "mode": "static",
                    "address": "%s/%d" % (
                        str(bond0_ip), bond0_subnet.get_ipnetwork().prefixlen),
                }],
                "enabled": True,
            },
        }
        interfaces["bond0.%d" % bond0_vlan.vid] = {
            "type": "vlan",
            "parents": ["bond0"],
            "links": [{
                "mode": "static",
                "address": "%s/%d" % (
                    str(bond0_vlan_ip),
                    bond0_vlan_subnet.get_ipnetwork().prefixlen),
            }],
            "vid": bond0_vlan.vid,
            "enabled": True,
        }
        rack.update_interfaces(interfaces)
        eth0 = PhysicalInterface.objects.get(
            node=rack, mac_address=interfaces["eth0"]["mac_address"])
        self.assertThat(
            eth0, MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth0",
                mac_address=interfaces["eth0"]["mac_address"],
                enabled=True,
                vlan=bond0_untagged,
            ))
        eth1 = PhysicalInterface.objects.get(
            node=rack, mac_address=interfaces["eth1"]["mac_address"])
        self.assertThat(
            eth1, MatchesStructure.byEquality(
                type=INTERFACE_TYPE.PHYSICAL,
                name="eth1",
                mac_address=interfaces["eth1"]["mac_address"],
                enabled=True,
                vlan=bond0_untagged,
            ))
        bond0 = BondInterface.objects.get(
            node=rack, mac_address=interfaces["bond0"]["mac_address"])
        self.assertThat(
            bond0, MatchesStructure.byEquality(
                type=INTERFACE_TYPE.BOND,
                name="bond0",
                mac_address=interfaces["bond0"]["mac_address"],
                enabled=True,
                vlan=bond0_untagged,
            ))
        self.assertThat(
            [parent.name for parent in bond0.parents.all()],
            MatchesSetwise(Equals("eth0"), Equals("eth1")))
        bond0_addresses = list(bond0.ip_addresses.all())
        self.assertThat(bond0_addresses, HasLength(1))
        self.assertThat(
            bond0_addresses[0], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=bond0_ip,
                subnet=bond0_subnet,
            ))
        bond0_vlan_nic = VLANInterface.objects.get(
            node=rack, vlan=bond0_vlan)
        self.assertThat(
            bond0_vlan_nic, MatchesStructure.byEquality(
                type=INTERFACE_TYPE.VLAN,
                name="bond0.%d" % bond0_vlan.vid,
                enabled=True,
                vlan=bond0_vlan,
            ))
        self.assertThat(
            [parent.name for parent in bond0_vlan_nic.parents.all()],
            Equals(["bond0"]))
        bond0_vlan_nic_addresses = list(bond0_vlan_nic.ip_addresses.all())
        self.assertThat(bond0_vlan_nic_addresses, HasLength(1))
        self.assertThat(
            bond0_vlan_nic_addresses[0], MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=bond0_vlan_ip,
                subnet=bond0_vlan_subnet,
            ))


class TestRackController(MAASServerTestCase):

    def test_refresh_issues_rpc_call(self):
        rackcontroller = factory.make_RackController()

        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(
            rackcontroller, RefreshRackControllerInfo)
        protocol.RefreshRackControllerInfo.return_value = defer.succeed({
            'architecture': rackcontroller.architecture,
            'osystem': '',
            'distro_series': '',
            'swap_size': 0,
            'interfaces': {},
        })

        rackcontroller.refresh()
        token = NodeKey.objects.get_token_for_node(rackcontroller)

        self.expectThat(
            protocol.RefreshRackControllerInfo,
            MockCalledOnceWith(
                ANY, system_id=rackcontroller.system_id,
                consumer_key=token.consumer.key, token_key=token.key,
                token_secret=token.secret))

    def test_refresh_logs_user_request(self):
        rackcontroller = factory.make_RackController(
            interface=True, status=NODE_STATUS.NEW, power_type='manual')
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(
            rackcontroller, RefreshRackControllerInfo)
        protocol.RefreshRackControllerInfo.return_value = defer.succeed({
            'architecture': rackcontroller.architecture,
            'osystem': '',
            'distro_series': '',
            'swap_size': 0,
            'interfaces': {},
        })

        register_event = self.patch(rackcontroller, '_register_request_event')
        rackcontroller.refresh()
        post_commit_hooks.reset()  # Ignore these for now.
        rackcontroller = reload_object(rackcontroller)
        self.assertThat(register_event, MockCalledOnceWith(
            rackcontroller.owner,
            EVENT_TYPES.REQUEST_RACK_CONTROLLER_REFRESH,
            action='starting refresh'))

    def test_refresh_sets_extra_values(self):
        rackcontroller = factory.make_RackController(status=NODE_STATUS.NEW)
        osystem = factory.make_name('osystem')
        distro_series = factory.make_name('distro_series')
        swap_size = random.randint(1, 1000)
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            }
        }

        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(
            rackcontroller, RefreshRackControllerInfo)
        protocol.RefreshRackControllerInfo.return_value = defer.succeed({
            'architecture': rackcontroller.architecture,
            'osystem': osystem,
            'distro_series': distro_series,
            'swap_size': swap_size,
            'interfaces': interfaces
        })

        rackcontroller.refresh()
        rackcontroller = reload_object(rackcontroller)
        self.assertEquals(osystem, rackcontroller.osystem)
        self.assertEquals(distro_series, rackcontroller.distro_series)
        self.assertEquals(swap_size, rackcontroller.swap_size)
        self.assertIsNotNone(
            Interface.objects.filter(
                node=rackcontroller,
                mac_address=interfaces["eth0"]["mac_address"]).first())

    def test_add_chassis_issues_rpc_call(self):
        rackcontroller = factory.make_RackController()

        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(rackcontroller, AddChassis)
        protocol.AddChassis.return_value = defer.succeed({})

        user = factory.make_name('user')
        chassis_type = factory.make_name('chassis_type')
        hostname = factory.make_url()
        username = factory.make_name('username')
        password = factory.make_name('password')
        accept_all = factory.pick_bool()
        domain = factory.make_name('domain')
        prefix_filter = factory.make_name('prefix_filter')
        power_control = factory.make_name('power_control')
        port = random.randint(0, 65535)
        given_protocol = factory.make_name('protocol')

        rackcontroller.add_chassis(
            user, chassis_type, hostname, username, password, accept_all,
            domain, prefix_filter, power_control, port, given_protocol)

        self.expectThat(
            protocol.AddChassis,
            MockCalledOnceWith(
                ANY, user=user, chassis_type=chassis_type, hostname=hostname,
                username=username, password=password, accept_all=accept_all,
                domain=domain, prefix_filter=prefix_filter,
                power_control=power_control, port=port,
                protocol=given_protocol))

    def test_add_chassis_logs_user_request(self):
        rackcontroller = factory.make_RackController()

        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(rackcontroller, AddChassis)
        protocol.AddChassis.return_value = defer.succeed({})

        user = factory.make_name('user')
        chassis_type = factory.make_name('chassis_type')
        hostname = factory.make_url()
        username = factory.make_name('username')
        password = factory.make_name('password')
        accept_all = factory.pick_bool()
        domain = factory.make_name('domain')
        prefix_filter = factory.make_name('prefix_filter')
        power_control = factory.make_name('power_control')
        port = random.randint(0, 65535)
        given_protocol = factory.make_name('protocol')

        register_event = self.patch(rackcontroller, '_register_request_event')
        rackcontroller.add_chassis(
            user, chassis_type, hostname, username, password, accept_all,
            domain, prefix_filter, power_control, port, given_protocol)
        post_commit_hooks.reset()  # Ignore these for now.
        self.assertThat(register_event, MockCalledOnceWith(
            rackcontroller.owner,
            EVENT_TYPES.REQUEST_RACK_CONTROLLER_ADD_CHASSIS,
            action="Adding chassis %s" % hostname))

    def test_allows_delete_when_not_connected(self):
        rackcontroller = factory.make_RackController()
        rackcontroller.delete()
        self.assertIsNone(reload_object(rackcontroller))

    def test_prevents_delete_when_connected(self):
        rackcontroller = factory.make_RackController()
        mock_filter = self.patch(RegionRackRPCConnection.objects, 'filter')
        mock_filter.return_value = [rackcontroller]
        self.assertRaises(ValidationError, rackcontroller.delete)

    def test_delete_converts_region_and_rack_to_region(self):
        region_and_rack = factory.make_Node(
            node_type=NODE_TYPE.REGION_AND_RACK_CONTROLLER)
        system_id = region_and_rack.system_id
        typecast_node(region_and_rack, RackController).delete()
        self.assertEquals(
            NODE_TYPE.REGION_CONTROLLER,
            Node.objects.get(system_id=system_id).node_type)
