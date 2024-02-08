# Copyright 2016-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import random
from statistics import mean
from unittest.mock import call, Mock, sentinel

from django.core.exceptions import (
    ObjectDoesNotExist,
    PermissionDenied,
    ValidationError,
)
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from django.http import Http404
import petname
from twisted.internet.defer import DeferredList, fail, inlineCallbacks, succeed

from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODE_TYPE,
)
from maasserver.exceptions import PodProblem
from maasserver.models import bmc as bmc_module
from maasserver.models.blockdevice import BlockDevice
from maasserver.models.bmc import (
    BMC,
    BMCRoutableRackControllerRelationship,
    get_requested_ips,
    Pod,
)
from maasserver.models.fabric import Fabric
from maasserver.models.filesystem import Filesystem
from maasserver.models.node import Controller, Machine, Node
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.podhints import PodHints
from maasserver.models.podstoragepool import PodStoragePool
from maasserver.models.resourcepool import ResourcePool
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.virtualmachine import (
    VirtualMachine,
    VirtualMachineDisk,
    VirtualMachineInterface,
)
from maasserver.models.vmcluster import VMCluster
from maasserver.permissions import PodPermission
from maasserver.secrets import SecretManager
from maasserver.testing.factory import factory
from maasserver.testing.fixtures import RBACEnabled
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import reload_object
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for
from provisioningserver.drivers.pod import (
    DiscoveredMachine,
    DiscoveredMachineBlockDevice,
    DiscoveredMachineInterface,
    DiscoveredPod,
    DiscoveredPodHints,
    DiscoveredPodStoragePool,
    InterfaceAttachType,
    RequestedMachine,
    RequestedMachineInterface,
)
from provisioningserver.enum import POWER_STATE
from provisioningserver.rpc.cluster import DecomposeMachine
from provisioningserver.utils.constraints import LabeledConstraintMap

wait_for_reactor = wait_for()
UNDEFINED = object()


class TestBMC(MAASServerTestCase):
    def get_machine_ip_address(self, machine):
        return machine.current_config.interface_set.all()[
            0
        ].ip_addresses.all()[0]

    def make_machine_and_bmc_with_shared_ip(self):
        machine = factory.make_Node(interface=False)
        machine.current_config.interface_set.clear()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=machine
        )
        machine_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=subnet,
            interface=interface,
        )
        self.assertEqual(1, machine.current_config.interface_set.count())

        bmc = factory.make_BMC(
            power_type="virsh",
            power_parameters={
                "power_address": "protocol://%s:8080/path/to/thing#tag"
                % (factory.ip_to_url_format(machine_ip.ip))
            },
        )
        # Make sure they're sharing an IP.
        machine = reload_object(machine)
        machine_ip_addr = self.get_machine_ip_address(machine)
        self.assertEqual(machine_ip_addr.id, bmc.ip_address.id)
        return machine, bmc, machine_ip

    def make_machine_and_bmc_differing_ips(self):
        machine = factory.make_Node(interface=False)
        machine.current_config.interface_set.clear()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=machine
        )
        machine_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=subnet,
            interface=interface,
        )
        self.assertEqual(1, machine.current_config.interface_set.count())

        ip_address = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet
        )
        bmc_ip = ip_address.ip
        ip_address.delete()
        bmc = factory.make_BMC(
            power_type="virsh",
            power_parameters={
                "power_address": "protocol://%s:8080/path/to/thing#tag"
                % (factory.ip_to_url_format(bmc_ip))
            },
        )
        # Make sure they're not sharing an IP.
        machine = reload_object(machine)
        machine_ip_addr = self.get_machine_ip_address(machine)
        self.assertNotEqual(machine_ip_addr.id, bmc.ip_address.id)
        return machine, bmc, machine_ip

    def test_make_machine_and_bmc_discovered_ip(self):
        # Regression test for LP:1816651
        subnet = factory.make_Subnet()
        discovered_ip = factory.make_StaticIPAddress(
            subnet=subnet, alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        sticky_ip = factory.make_StaticIPAddress(
            ip=discovered_ip.ip,
            subnet=subnet,
            alloc_type=IPADDRESS_TYPE.STICKY,
        )
        bmc = factory.make_BMC(
            power_type="virsh",
            power_parameters={
                "power_address": "protocol://%s:8080/path/to/thing#tag"
                % (factory.ip_to_url_format(discovered_ip.ip))
            },
        )
        self.assertCountEqual(
            [discovered_ip, sticky_ip],
            StaticIPAddress.objects.filter(ip=discovered_ip.ip),
        )
        self.assertEqual(sticky_ip, bmc.ip_address)

    def test_bmc_save_extracts_ip_address(self):
        subnet = factory.make_Subnet()
        sticky_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet
        )
        power_parameters = {
            "power_address": "protocol://%s:8080/path/to/thing#tag"
            % (factory.ip_to_url_format(sticky_ip.ip))
        }
        bmc = factory.make_BMC(
            power_type="virsh", power_parameters=power_parameters
        )
        self.assertEqual(sticky_ip.ip, bmc.ip_address.ip)
        self.assertEqual(subnet, bmc.ip_address.subnet)

    def test_bmc_save_accepts_naked_ipv6_address(self):
        subnet = factory.make_Subnet(cidr=factory.make_ipv6_network())
        sticky_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet
        )
        power_parameters = {"power_address": "%s" % sticky_ip.ip}
        bmc = factory.make_BMC(
            power_type="ipmi", power_parameters=power_parameters
        )
        self.assertEqual(sticky_ip.ip, bmc.ip_address.ip)
        self.assertEqual(subnet, bmc.ip_address.subnet)

    def test_bmc_save_accepts_bracketed_ipv6_address(self):
        subnet = factory.make_Subnet(cidr=factory.make_ipv6_network())
        sticky_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet
        )
        power_parameters = {"power_address": "[%s]" % sticky_ip.ip}
        bmc = factory.make_BMC(
            power_type="ipmi", power_parameters=power_parameters
        )
        self.assertEqual(sticky_ip.ip, bmc.ip_address.ip)
        self.assertEqual(subnet, bmc.ip_address.subnet)

    def test_bmc_changing_power_parameters_changes_ip(self):
        ip = factory.make_ipv4_address()
        power_parameters = {
            "power_address": "protocol://%s:8080/path#tag"
            % factory.ip_to_url_format(ip)
        }
        bmc = factory.make_BMC(
            power_type="virsh", power_parameters=power_parameters
        )
        self.assertEqual(ip, bmc.ip_address.ip)
        self.assertIsNone(bmc.ip_address.subnet)

        subnet = factory.make_Subnet()
        sticky_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet
        )
        bmc.set_power_parameters(
            {
                "power_address": "protocol://%s:8080/path/to/thing#tag"
                % (factory.ip_to_url_format(sticky_ip.ip))
            }
        )
        bmc.save()
        self.assertEqual(sticky_ip.ip, bmc.ip_address.ip)
        self.assertEqual(subnet, bmc.ip_address.subnet)

    def test_bmc_changing_power_parameters_ipmi_errors_if_invalid(self):
        ip = factory.make_ipv4_address()
        power_parameters = {
            "power_address": "protocol://%s" % factory.ip_to_url_format(ip)
        }
        with self.assertRaisesRegex(
            ValueError, "does not support netmasks or subnet prefixes!"
        ):
            factory.make_BMC(
                power_type="ipmi", power_parameters=power_parameters
            )

    def test_deleting_machine_ip_when_shared_with_bmc(self):
        machine, bmc, machine_ip = self.make_machine_and_bmc_with_shared_ip()

        # Now delete the machine.
        old_ip = machine_ip.ip
        machine.delete()

        # Check BMC still has old IP.
        bmc = reload_object(bmc)
        self.assertIsNotNone(bmc.ip_address)
        self.assertEqual(old_ip, bmc.ip_address.ip)

        # Make sure DB ID's of StaticIPAddress instances differ.
        self.assertNotEqual(machine_ip.id, bmc.ip_address.id)

    def test_removing_bmc_ip_when_shared_with_bmc(self):
        machine, bmc, machine_ip = self.make_machine_and_bmc_with_shared_ip()

        # Clear the BMC IP.
        old_ip = bmc.ip_address.ip
        bmc.power_type = "manual"
        bmc.save()
        self.assertIsNone(bmc.ip_address)

        # Check Machine still has same IP address.
        machine = reload_object(machine)
        machine_ip_addr = self.get_machine_ip_address(machine)
        self.assertEqual(old_ip, machine_ip_addr.ip)
        self.assertEqual(machine_ip.id, machine_ip_addr.id)

    def test_changing_machine_ip_when_shared_with_bmc_keeps_both(self):
        machine, bmc, machine_ip = self.make_machine_and_bmc_with_shared_ip()

        # Now change the Machine's IP to a new address on same subnet.
        old_ip = machine_ip.ip
        new_ip_address = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=machine_ip.subnet
        )
        new_ip = new_ip_address.ip
        # Remove IP so we can set machine_ip to its address.
        new_ip_address.delete()
        self.assertNotEqual(new_ip, old_ip)
        machine_ip.ip = new_ip
        machine_ip.save()

        # Check Machine has new IP address but kept same instance: machine_ip.
        machine = reload_object(machine)
        machine_ip_addr = self.get_machine_ip_address(machine)
        self.assertEqual(new_ip, machine_ip_addr.ip)
        self.assertEqual(machine_ip.id, machine_ip_addr.id)

        # Check BMC still has old IP.
        bmc = reload_object(bmc)
        self.assertEqual(old_ip, bmc.ip_address.ip)

        # Make sure DB ID's of StaticIPAddress instances differ.
        self.assertNotEqual(machine_ip_addr.id, bmc.ip_address.id)

    def test_changing_bmc_ip_when_shared_with_machine_keeps_both(self):
        machine, bmc, machine_ip = self.make_machine_and_bmc_with_shared_ip()

        # Now change the BMC's IP to a new address on same subnet.
        old_ip = machine_ip.ip
        new_ip_address = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=machine_ip.subnet
        )
        new_ip = new_ip_address.ip
        # Remove IP so we can set machine_ip to its address.
        new_ip_address.delete()
        self.assertNotEqual(new_ip, old_ip)

        bmc.set_power_parameters(
            {
                "power_address": "protocol://%s:8080/path/to/thing#tag"
                % (factory.ip_to_url_format(new_ip))
            }
        )
        bmc.save()

        # Check Machine has old IP address and kept same instance: machine_ip.
        machine = reload_object(machine)
        machine_ip_addr = self.get_machine_ip_address(machine)
        self.assertEqual(old_ip, machine_ip_addr.ip)
        self.assertEqual(machine_ip.id, machine_ip_addr.id)

        # Check BMC has new IP.
        bmc = reload_object(bmc)
        self.assertEqual(new_ip, bmc.ip_address.ip)

        # Make sure DB ID's of StaticIPAddress instances differ.
        self.assertNotEqual(machine_ip_addr.id, bmc.ip_address.id)

    def test_bmc_existing_ip_links_to_it(self):
        ip = factory.make_StaticIPAddress(ip="10.10.10.10")
        bmc = factory.make_BMC(
            power_type="virsh",
            power_parameters={
                "power_address": f"virsh://{ip.ip}/path/to/thing#tag"
            },
        )
        self.assertEqual(bmc.ip_address.id, ip.id)

    def test_merging_bmc_into_machine_ip(self):
        machine, bmc, machine_ip = self.make_machine_and_bmc_differing_ips()

        # Now change the BMC's address to match machine's.
        bmc.set_power_parameters(
            {
                "power_address": "protocol://%s:8080/path/to/thing#tag"
                % (factory.ip_to_url_format(machine_ip.ip))
            }
        )
        bmc.save()

        # Make sure BMC and Machine are using same StaticIPAddress instance.
        machine = reload_object(machine)
        machine_ip_addr = self.get_machine_ip_address(machine)
        self.assertEqual(machine_ip_addr.id, bmc.ip_address.id)

    def test_delete_bmc_deletes_orphaned_ip_address(self):
        bmc = factory.make_BMC(
            power_type="virsh",
            power_parameters={
                "power_address": "protocol://%s:8080/path/to/thing#tag"
                % (factory.make_ipv4_address())
            },
        )
        ip = bmc.ip_address
        bmc.delete()
        self.assertEqual(0, StaticIPAddress.objects.filter(id=ip.id).count())

    def test_delete_deletes_bmc_secrets(self):
        bmc = factory.make_BMC()
        secret_manager = SecretManager()
        secret_manager.set_composite_secret(
            "power-parameters", {"foo": "bar"}, obj=bmc
        )

        bmc.delete()
        self.assertIsNone(
            secret_manager.get_simple_secret(
                "power-parameters", obj=bmc, default=None
            )
        )

    def test_delete_bmc_spares_non_orphaned_ip_address(self):
        machine, bmc, machine_ip = self.make_machine_and_bmc_with_shared_ip()
        bmc.delete()
        self.assertEqual(
            1, StaticIPAddress.objects.filter(id=machine_ip.id).count()
        )

    def test_scope_power_parameters(self):
        bmc_parameters = dict(
            power_address=factory.make_string(),
            power_pass=factory.make_string(),
        )
        node_parameters = dict(
            power_vm_name=factory.make_string(),
            power_uuid=factory.make_string(),
        )
        parameters = {**bmc_parameters, **node_parameters}
        result = BMC.scope_power_parameters("vmware", parameters)
        self.assertTrue(result[0])
        self.assertEqual(bmc_parameters, result[1])
        self.assertEqual(node_parameters, result[2])

    def test_scope_power_parameters_unknown_parameter(self):
        bmc_parameters = dict(power_address=factory.make_string())
        node_parameters = dict(server_name=factory.make_string())
        # This random parameter should be stored on the node instance.
        node_parameters[factory.make_string()] = factory.make_string()
        parameters = {**bmc_parameters, **node_parameters}
        result = BMC.scope_power_parameters("hmc", parameters)
        self.assertTrue(result[0])
        self.assertEqual(bmc_parameters, result[1])
        self.assertEqual(node_parameters, result[2])

    def test_bmc_extract_ip_address_whole_value(self):
        power_parameters = {"power_address": "192.168.1.1"}
        self.assertEqual(
            "192.168.1.1", BMC.extract_ip_address("hmc", power_parameters)
        )

    def test_bmc_extract_ip_address_empty_power_type_gives_none(self):
        power_parameters = {"power_address": "192.168.1.1"}
        self.assertIsNone(BMC.extract_ip_address("", power_parameters))
        self.assertIsNone(BMC.extract_ip_address(None, power_parameters))

    def test_bmc_extract_ip_address_blank_gives_none(self):
        self.assertIsNone(BMC.extract_ip_address("hmc", None))
        self.assertIsNone(BMC.extract_ip_address("hmc", {}))

        power_parameters = {"power_address": ""}
        self.assertIsNone(BMC.extract_ip_address("hmc", power_parameters))

        power_parameters = {"power_address": None}
        self.assertIsNone(BMC.extract_ip_address("hmc", power_parameters))

    def test_bmc_extract_ip_address_from_url_blank_gives_none(self):
        self.assertIsNone(BMC.extract_ip_address("virsh", None))
        self.assertIsNone(BMC.extract_ip_address("virsh", {}))

        power_parameters = {"power_address": ""}
        self.assertEqual(
            None, BMC.extract_ip_address("virsh", power_parameters)
        )

        power_parameters = {"power_address": None}
        self.assertEqual(
            None, BMC.extract_ip_address("virsh", power_parameters)
        )

    def test_bmc_extract_ip_address_from_url_empty_host(self):
        power_parameters = {"power_address": "http://:8080/foo/#baz"}
        self.assertEqual("", BMC.extract_ip_address("virsh", power_parameters))

    def test_bmc_extract_ip_address_with_fqdn_returns_none(self):
        self.assertIsNone(
            BMC.extract_ip_address(
                "webhook", {"power_address": factory.make_url()}
            )
        )

    def test_get_usable_rack_controllers_returns_empty_when_none(self):
        bmc = factory.make_BMC()
        self.assertEqual(bmc.get_usable_rack_controllers(), [])

    def test_get_usable_rack_controllers_returns_routable_racks(self):
        bmc = factory.make_BMC()
        routable_racks = [factory.make_RackController() for _ in range(3)]
        not_routable_racks = [factory.make_RackController() for _ in range(3)]
        for rack in routable_racks:
            BMCRoutableRackControllerRelationship(
                bmc=bmc, rack_controller=rack, routable=True
            ).save()
        for rack in not_routable_racks:
            BMCRoutableRackControllerRelationship(
                bmc=bmc, rack_controller=rack, routable=False
            ).save()
        self.assertCountEqual(
            routable_racks,
            bmc.get_usable_rack_controllers(with_connection=False),
        )

    def test_get_usable_rack_controllers_returns_routable_racks_conn(self):
        bmc = factory.make_BMC()
        routable_racks = [factory.make_RackController() for _ in range(3)]
        not_routable_racks = [factory.make_RackController() for _ in range(3)]
        for rack in routable_racks:
            BMCRoutableRackControllerRelationship(
                bmc=bmc, rack_controller=rack, routable=True
            ).save()
        for rack in not_routable_racks:
            BMCRoutableRackControllerRelationship(
                bmc=bmc, rack_controller=rack, routable=False
            ).save()
        connected_rack = random.choice(routable_racks)
        client = Mock()
        client.ident = connected_rack.system_id
        self.patch(bmc_module, "getAllClients").return_value = [client]
        self.assertEqual(
            [connected_rack],
            bmc.get_usable_rack_controllers(with_connection=True),
        )

    def test_get_usable_rack_controllers_updates_subnet_on_sip(self):
        network = factory.make_ipv4_network()
        subnet = factory.make_Subnet(cidr=str(network.cidr))
        ip = factory.pick_ip_in_Subnet(subnet)
        sip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet
        )
        sip.subnet = None
        sip.save()
        bmc = factory.make_BMC(
            power_type="virsh",
            power_parameters={
                "power_address": "qemu+ssh://user@%s/system" % ip
            },
            ip_address=sip,
        )
        bmc.get_usable_rack_controllers()
        self.assertEqual(subnet, reload_object(sip).subnet)

    def test_get_usable_rack_controllers_updates_handles_unknown_subnet(self):
        network = factory.make_ipv4_network()
        ip = factory.pick_ip_in_network(network)
        sip = StaticIPAddress.objects.create(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip
        )
        bmc = factory.make_BMC(
            power_type="virsh",
            power_parameters={
                "power_address": "qemu+ssh://user@%s/system" % ip
            },
            ip_address=sip,
        )
        bmc.get_usable_rack_controllers()
        self.assertIsNone(reload_object(sip).subnet)

    def test_get_usable_rack_controllers_returns_rack_controllers(self):
        rack_controller = factory.make_RackController()
        machine = factory.make_Node(bmc_connected_to=rack_controller)
        self.assertEqual(
            [rack_controller],
            machine.bmc.get_usable_rack_controllers(with_connection=False),
        )

    def test_get_client_identifiers_returns_rack_controller_system_ids(self):
        rack_controllers = [factory.make_RackController() for _ in range(3)]
        bmc = factory.make_BMC()
        self.patch(
            bmc, "get_usable_rack_controllers"
        ).return_value = rack_controllers
        expected_system_ids = [rack.system_id for rack in rack_controllers]
        self.assertEqual(expected_system_ids, bmc.get_client_identifiers())

    def test_is_accessible_calls_get_usable_rack_controllers(self):
        bmc = factory.make_BMC()
        mock_get_usable_rack_controllers = self.patch(
            bmc, "get_usable_rack_controllers"
        )
        bmc.is_accessible()
        mock_get_usable_rack_controllers.assert_called_once_with(
            with_connection=True
        )

    def test_is_accessible_returns_true(self):
        bmc = factory.make_BMC()
        mock_get_usable_rack_controllers = self.patch(
            bmc, "get_usable_rack_controllers"
        )
        mock_get_usable_rack_controllers.return_value = [
            factory.make_RackController()
        ]
        self.assertTrue(bmc.is_accessible())

    def test_is_accessible_returns_false(self):
        bmc = factory.make_BMC()
        mock_get_usable_rack_controllers = self.patch(
            bmc, "get_usable_rack_controllers"
        )
        mock_get_usable_rack_controllers.return_value = []
        self.assertFalse(bmc.is_accessible())

    def test_update_routable_racks_updates_rack_relationship(self):
        node = factory.make_Node(power_type="virsh")

        # Create old relationships that should be removed.
        old_relationship_ids = [
            BMCRoutableRackControllerRelationship.objects.create(
                bmc=node.bmc,
                rack_controller=factory.make_RackController(),
                routable=True,
            ).id
            for _ in range(3)
        ]

        routable_racks = [factory.make_RackController() for _ in range(3)]
        non_routable_racks = [factory.make_RackController() for _ in range(3)]

        node.bmc.update_routable_racks(
            [rack.system_id for rack in routable_racks],
            [rack.system_id for rack in non_routable_racks],
        )

        self.assertFalse(
            BMCRoutableRackControllerRelationship.objects.filter(
                id__in=old_relationship_ids
            ).exists()
        )
        self.assertEqual(
            BMCRoutableRackControllerRelationship.objects.filter(
                rack_controller__in=routable_racks, routable=True
            ).count(),
            len(routable_racks),
        )
        self.assertEqual(
            BMCRoutableRackControllerRelationship.objects.filter(
                rack_controller__in=non_routable_racks, routable=False
            ).count(),
            len(non_routable_racks),
        )

    def test_get_power_params(self):
        bmc = factory.make_BMC()
        secret_manager = SecretManager()
        secret_manager.set_composite_secret(
            "power-parameters", {"foo": "bar"}, obj=bmc
        )

        self.assertEqual({"foo": "bar"}, bmc.get_power_parameters())


class TestPodManager(MAASServerTestCase):
    def enable_rbac(self):
        rbac = self.useFixture(RBACEnabled())
        self.store = rbac.store

    def test_get_pods_no_rbac_always_all(self):
        pods = [factory.make_Pod() for _ in range(3)]
        for perm in PodPermission:
            self.assertCountEqual(
                pods, Pod.objects.get_pods(factory.make_User(), perm)
            )

    def test_get_pods_view_rbac_returns_view_rights(self):
        self.enable_rbac()
        user = factory.make_User()
        view_pool = factory.make_ResourcePool()
        view = factory.make_Pod(pool=view_pool)
        self.store.add_pool(view_pool)
        self.store.allow(user.username, view_pool, "view")
        view_all_pool = factory.make_ResourcePool()
        view_all = factory.make_Pod(pool=view_all_pool)
        self.store.add_pool(view_all_pool)
        self.store.allow(user.username, view_all_pool, "view-all")

        # others not shown
        for _ in range(3):
            factory.make_Pod()

        self.assertCountEqual(
            [view, view_all], Pod.objects.get_pods(user, PodPermission.view)
        )

    def test_get_pods_edit_compose_rbac_returns_admin_rights(self):
        self.enable_rbac()
        user = factory.make_User()
        view_pool = factory.make_ResourcePool()
        factory.make_Pod(pool=view_pool)
        self.store.add_pool(view_pool)
        self.store.allow(user.username, view_pool, "view")
        deploy_pool = factory.make_ResourcePool()
        factory.make_Pod(pool=deploy_pool)
        self.store.add_pool(deploy_pool)
        self.store.allow(user.username, deploy_pool, "deploy-machines")
        admin_pool = factory.make_ResourcePool()
        admin_pod = factory.make_Pod(pool=admin_pool)
        self.store.add_pool(admin_pool)
        self.store.allow(user.username, admin_pool, "admin-machines")

        # others not shown
        for _ in range(3):
            factory.make_Pod()

        self.assertCountEqual(
            [admin_pod], Pod.objects.get_pods(user, PodPermission.edit)
        )
        self.assertCountEqual(
            [admin_pod], Pod.objects.get_pods(user, PodPermission.compose)
        )

    def test_get_pods_dynamic_compose_rbac_returns_deploy_admin_rights(self):
        self.enable_rbac()
        user = factory.make_User()
        view_pool = factory.make_ResourcePool()
        factory.make_Pod(pool=view_pool)
        self.store.add_pool(view_pool)
        self.store.allow(user.username, view_pool, "view")
        deploy_pool = factory.make_ResourcePool()
        deploy_pod = factory.make_Pod(pool=deploy_pool)
        self.store.add_pool(deploy_pool)
        self.store.allow(user.username, deploy_pool, "deploy-machines")
        admin_pool = factory.make_ResourcePool()
        admin_pod = factory.make_Pod(pool=admin_pool)
        self.store.add_pool(admin_pool)
        self.store.allow(user.username, admin_pool, "admin-machines")

        # others not shown
        for _ in range(3):
            factory.make_Pod()

        self.assertCountEqual(
            [deploy_pod, admin_pod],
            Pod.objects.get_pods(user, PodPermission.dynamic_compose),
        )

    def test_get_pod_or_404_raises_404(self):
        user = factory.make_User()
        self.patch(user, "has_perm").return_value = False
        self.assertRaises(
            Http404,
            Pod.objects.get_pod_or_404,
            random.randint(10, 20),
            user,
            PodPermission.view,
        )

    def test_get_pod_or_404_checks_permissions(self):
        pod = factory.make_Pod()
        user = factory.make_User()
        self.patch(user, "has_perm").return_value = False
        self.assertRaises(
            PermissionDenied,
            Pod.objects.get_pod_or_404,
            pod.id,
            user,
            PodPermission.view,
        )

    def test_get_pod_or_404_returns_pod(self):
        pod = factory.make_Pod()
        user = factory.make_User()
        self.patch(user, "has_perm").return_value = True
        self.assertEqual(
            pod, Pod.objects.get_pod_or_404(pod.id, user, PodPermission.view)
        )


class PodTestMixin:
    def make_discovered_block_device(
        self,
        model=None,
        serial=None,
        id_path=None,
        storage_pools=None,
    ):
        if id_path is None:
            if model is None:
                model = factory.make_name("model")
            if serial is None:
                serial = factory.make_name("serial")
        else:
            model = None
            serial = None
        storage_pool = None
        if storage_pools is not None:
            storage_pool = random.choice(storage_pools).id
        return DiscoveredMachineBlockDevice(
            model=model,
            serial=serial,
            size=random.randint(1024**3, 1024**4),
            block_size=random.choice([512, 4096]),
            tags=[factory.make_name("tag") for _ in range(3)],
            id_path=id_path,
            storage_pool=storage_pool,
        )

    def make_discovered_interface(
        self,
        mac_address=UNDEFINED,
        attach_name=None,
        attach_type=InterfaceAttachType.MACVLAN,
        vid=0,
    ):
        if mac_address is UNDEFINED:
            mac_address = factory.make_mac_address()
        if mac_address is not None:
            mac_address = str(mac_address)
        return DiscoveredMachineInterface(
            mac_address=mac_address,
            attach_name=attach_name,
            attach_type=attach_type,
            vid=vid,
            tags=[factory.make_name("tag") for _ in range(3)],
        )

    def make_discovered_machine(
        self,
        hostname=None,
        project=None,
        block_devices=None,
        interfaces=None,
        storage_pools=None,
        memory=None,
        location=None,
    ):
        if block_devices is None:
            block_devices = [
                self.make_discovered_block_device(
                    storage_pools=storage_pools,
                )
                for _ in range(3)
            ]
        if interfaces is None:
            interfaces = [self.make_discovered_interface() for i in range(3)]
            interfaces[0].boot = True
        if hostname is None:
            hostname = factory.make_name("hostname")
        if memory is None:
            memory = random.randint(8192, 8192 * 8)
        power_parameters = {"instance_name": hostname}
        if project:
            power_parameters["project"] = project
        return DiscoveredMachine(
            hostname=hostname,
            architecture="amd64/generic",
            cores=random.randint(8, 120),
            cpu_speed=random.randint(2000, 4000),
            memory=memory,
            interfaces=interfaces,
            block_devices=block_devices,
            power_state=random.choice([POWER_STATE.ON, POWER_STATE.OFF]),
            power_parameters=power_parameters,
            tags=[factory.make_name("tag") for _ in range(3)],
            location=location,
        )

    def make_discovered_storage_pool(self):
        name = factory.make_name("name")
        return DiscoveredPodStoragePool(
            id=factory.make_name("id"),
            name=name,
            storage=random.randint(10 * 1024**3, 100 * 1024**3),
            type=factory.make_name("type"),
            path="/var/lib/%s" % name,
        )

    def make_discovered_pod(
        self,
        name=None,
        machines=None,
        storage_pools=None,
        mac_addresses=None,
    ):
        if name is None:
            name = petname.Generate(2, "-")
        if machines is None:
            machines = [
                self.make_discovered_machine(storage_pools=storage_pools)
                for _ in range(3)
            ]
        if storage_pools is None:
            storage_pools = [
                self.make_discovered_storage_pool() for _ in range(3)
            ]
        if mac_addresses is None:
            mac_addresses = []
        return DiscoveredPod(
            architectures=["amd64/generic"],
            name=name,
            version=factory.make_name("version"),
            cores=random.randint(8, 120),
            cpu_speed=random.randint(2000, 4000),
            memory=random.randint(8192, 8192 * 8),
            local_storage=random.randint(20000, 40000),
            hints=DiscoveredPodHints(
                cores=random.randint(8, 16),
                cpu_speed=random.randint(2000, 4000),
                memory=random.randint(8192, 8192 * 2),
                local_storage=random.randint(10000, 20000),
            ),
            storage_pools=storage_pools,
            machines=machines,
            mac_addresses=mac_addresses,
        )


class TestPod(MAASServerTestCase, PodTestMixin):
    def test_name_project_cluster_uniqueness(self):
        user = factory.make_User()
        cluster = factory.make_VMCluster(pods=0)
        discovered_pod = self.make_discovered_pod()
        pod1 = Pod(
            power_type="lxd",
            power_parameters={"project": factory.make_name("project")},
        )
        pod1.sync(discovered_pod, user)
        pod1.hints.cluster = cluster
        pod1.save()
        pod2 = Pod(
            power_type="lxd",
            name=pod1.name,
            power_parameters={"project": pod1.power_parameters["project"]},
        )
        self.assertRaises(IntegrityError, pod2.sync, discovered_pod, user)

    def test_name_always_unique_with_no_cluster(self):
        pod1 = Pod(power_type="virsh", power_parameters={})
        pod1.save()
        pod2 = Pod(power_type="virsh", power_parameters={}, name=pod1.name)
        self.assertRaises(IntegrityError, pod2.save)

    def test_allows_same_name_in_cluster_different_project(self):
        cluster = factory.make_VMCluster(pods=0)
        discovered = self.make_discovered_pod()
        pod1 = Pod(
            power_type="lxd",
            power_parameters={"project": factory.make_name("project")},
        )
        pod1.save()
        pod1.sync_hints(discovered.hints, cluster=cluster)
        pod2 = Pod(
            power_type="lxd",
            name=pod1.name,
            power_parameters={"project": factory.make_name("project")},
        )
        pod2.save()
        pod2.sync_hints(discovered.hints, cluster=cluster)
        self.assertEqual(pod1.name, pod2.name)
        self.assertEqual(pod1.hints.cluster_id, pod2.hints.cluster_id)

    def test_create_with_pool(self):
        pool = ResourcePool.objects.get_default_resource_pool()
        pod = Pod(power_type="virsh", power_parameters={}, pool=pool)
        pod.save()
        self.assertEqual(pool, pod.pool)

    def test_create_with_no_pool(self):
        pod = Pod(power_type="virsh", power_parameters={})
        pod.save()
        self.assertEqual(
            ResourcePool.objects.get_default_resource_pool(), pod.pool
        )

    def test_save_with_no_pool(self):
        pod = Pod(power_type="virsh", power_parameters={})
        pod.pool = None
        self.assertRaises(ValidationError, pod.save)

    def test_no_delete_pod_pool(self):
        pool = factory.make_ResourcePool()
        pod = Pod(power_type="virsh", power_parameters={}, pool=pool)
        pod.save()
        self.assertRaises(ProtectedError, pool.delete)

    def test_create_with_over_commit_ratios(self):
        cpu_over_commit_ratio = random.uniform(0.1, 2.0)
        memory_over_commit_ratio = random.uniform(0.1, 2.0)
        pod = Pod(
            power_type="virsh",
            power_parameters={},
            cpu_over_commit_ratio=cpu_over_commit_ratio,
            memory_over_commit_ratio=memory_over_commit_ratio,
        )
        pod.save()
        self.assertEqual(cpu_over_commit_ratio, pod.cpu_over_commit_ratio)
        self.assertEqual(
            memory_over_commit_ratio, pod.memory_over_commit_ratio
        )

    def test_create_with_no_over_commit_ratios(self):
        pod = Pod(power_type="virsh", power_parameters={})
        pod.save()
        self.assertEqual(1, pod.cpu_over_commit_ratio)
        self.assertEqual(1, pod.memory_over_commit_ratio)

    def test_sync_pod_properties_and_hints(self):
        discovered = self.make_discovered_pod()
        discovered.tags = [factory.make_name("tag") for _ in range(3)]
        # Create a subset of the discovered pod's tags
        # to make sure no duplicates are added on sync.
        pod = Pod(
            power_type="lxd",
            power_parameters={
                "power_address": "https://10.0.0.1:8443",
                "project": "prj",
            },
            tags=[discovered.tags[0]],
        )
        self.patch(pod, "sync_machines")
        pod.sync(discovered, factory.make_User())
        self.assertEqual(pod.architectures, discovered.architectures)
        self.assertEqual(pod.name, discovered.name)
        self.assertEqual(pod.version, discovered.version)
        self.assertEqual(pod.cores, discovered.cores)
        self.assertEqual(pod.cpu_speed, discovered.cpu_speed)
        self.assertEqual(pod.memory, discovered.memory)
        self.assertEqual(pod.local_storage, discovered.local_storage)
        self.assertEqual(pod.capabilities, discovered.capabilities)
        self.assertCountEqual(pod.tags, discovered.tags)

        hints = pod.hints
        self.assertEqual(hints.cores, discovered.hints.cores)
        self.assertEqual(hints.cpu_speed, discovered.hints.cpu_speed)
        self.assertEqual(hints.memory, discovered.hints.memory)
        self.assertEqual(hints.local_storage, discovered.hints.local_storage)

        storage_pools = pod.storage_pools
        self.assertEqual(
            pod.default_storage_pool.pool_id, discovered.storage_pools[0].id
        )
        self.assertCountEqual(
            storage_pools.values_list(
                "name", "pool_id", "pool_type", "path", "storage"
            ),
            [
                (sp.name, sp.id, sp.type, sp.path, sp.storage)
                for sp in discovered.storage_pools
            ],
        )

    def test_sync_lxd_host_removes_trust_password(self):
        discovered = self.make_discovered_pod()
        pod = Pod(
            power_type="lxd",
            power_parameters={
                "power_address": "https://10.0.0.1:8443",
                "password": "sekret",
            },
        )
        self.patch(pod, "sync_machines")
        pod.sync(discovered, factory.make_User())
        self.assertNotIn("password", pod.get_power_parameters())

    def test_sync_pod_creates_new_machines_connected_to_default_vlan(self):
        discovered = self.make_discovered_pod()
        # Set one of the discovered machine's hostnames to something illegal.
        machine = discovered.machines[0]
        machine.hostname = "This is not legal #$%*^@!"
        mock_set_default_storage_layout = self.patch(
            Machine, "set_default_storage_layout"
        )
        mock_set_initial_networking_configuration = self.patch(
            Machine, "set_initial_networking_configuration"
        )
        mock_start_commissioning = self.patch(Machine, "start_commissioning")
        pod = factory.make_Pod()
        pod.sync(discovered, factory.make_User())
        machine_macs = [
            machine.interfaces[0].mac_address
            for machine in discovered.machines
        ]
        created_machines = Machine.objects.filter(
            current_config__interface__mac_address__in=machine_macs
        ).distinct()
        default_vlan = Fabric.objects.get_default_fabric().get_default_vlan()
        for created_machine, discovered_machine in zip(
            created_machines, discovered.machines
        ):
            self.assertEqual(
                created_machine.architecture, discovered_machine.architecture
            )
            self.assertEqual(created_machine.bmc, pod)
            self.assertEqual(
                created_machine.cpu_count, discovered_machine.cores
            )
            self.assertEqual(
                created_machine.cpu_speed, discovered_machine.cpu_speed
            )
            self.assertEqual(created_machine.memory, discovered_machine.memory)
            self.assertEqual(
                created_machine.power_state, discovered_machine.power_state
            )
            self.assertEqual(
                created_machine.get_instance_power_parameters(),
                discovered_machine.power_parameters,
            )
            self.assertFalse(created_machine.dynamic)
            self.assertCountEqual(
                [tag.name for tag in created_machine.tags.all()],
                discovered_machine.tags,
            )
            self.assertIsNotNone(created_machine.boot_interface)
            for created_device, (idx, discovered_device) in zip(
                created_machine.physicalblockdevice_set,
                enumerate(discovered_machine.block_devices),
            ):
                self.assertEqual(
                    created_device.name,
                    BlockDevice._get_block_name_from_idx(idx),
                )
                self.assertEqual(
                    created_device.id_path, discovered_device.id_path
                )
                self.assertEqual(created_device.model, discovered_device.model)
                self.assertEqual(
                    created_device.serial, discovered_device.serial
                )
                self.assertEqual(created_device.size, discovered_device.size)
                self.assertEqual(
                    created_device.block_size, discovered_device.block_size
                )
                self.assertCountEqual(
                    created_device.tags, discovered_device.tags
                )
            for created_if, (idx, discovered_if) in zip(
                created_machine.current_config.interface_set.all(),
                enumerate(discovered_machine.interfaces),
            ):
                self.assertEqual(created_if.name, f"eth{idx}")
                self.assertEqual(
                    created_if.mac_address, discovered_if.mac_address
                )
                self.assertEqual(
                    created_if.vlan,
                    default_vlan if discovered_if.boot else None,
                )
                self.assertEqual(created_if.tags, discovered_if.tags)
        mock_set_default_storage_layout.assert_not_called()
        mock_set_initial_networking_configuration.assert_not_called()
        self.assertEqual(
            mock_start_commissioning.call_count,
            len(discovered.machines),
        )

    def test_sync_creates_vms_all_projects(self):
        project1 = factory.make_string()
        project2 = factory.make_string()
        discovered_machines = [
            self.make_discovered_machine(project=project1),
            self.make_discovered_machine(project=project2),
        ]
        discovered_pod = self.make_discovered_pod(machines=discovered_machines)
        pod = factory.make_Pod(
            pod_type="lxd", parameters={"project": project1}
        )
        self.patch(Machine, "start_commissioning")
        pod.sync(discovered_pod, factory.make_User())
        discovered_vms = {
            discovered_vm.power_parameters["instance_name"]: discovered_vm
            for discovered_vm in discovered_machines
        }
        vms = VirtualMachine.objects.all()
        for vm in vms:
            discovered_vm = discovered_vms.pop(vm.identifier)
            self.assertEqual(
                vm.project, discovered_vm.power_parameters["project"]
            )
            self.assertEqual(vm.memory, discovered_vm.memory)
            self.assertEqual(
                vm.hugepages_backed, discovered_vm.hugepages_backed
            )
            self.assertEqual(vm.pinned_cores, discovered_vm.pinned_cores)
            self.assertEqual(vm.unpinned_cores, discovered_vm.cores)
        self.assertEqual(discovered_vms, {}, "Found extra vms not discovered")
        # a machine is created only for the VM in the tracked project
        [machine] = Machine.objects.all()
        self.assertEqual(machine.virtualmachine.project, project1)

    def test_sync_deletes_vms_all_projects(self):
        project1 = factory.make_string()
        project2 = factory.make_string()
        discovered_pod = self.make_discovered_pod(machines=[])
        pod = factory.make_Pod(
            pod_type="lxd", parameters={"project": project1}
        )
        factory.make_VirtualMachine(project=project1, bmc=pod)
        factory.make_VirtualMachine(project=project2, bmc=pod)
        self.patch(Machine, "start_commissioning")
        pod.sync(discovered_pod, factory.make_User())
        self.assertFalse(VirtualMachine.objects.exists())

    def test_sync_deletes_vms_no_project(self):
        discovered_pod = self.make_discovered_pod(machines=[])
        pod = factory.make_Pod(pod_type="virsh")
        factory.make_VirtualMachine(bmc=pod)
        factory.make_VirtualMachine(bmc=pod)
        self.patch(Machine, "start_commissioning")
        pod.sync(discovered_pod, factory.make_User())
        self.assertFalse(VirtualMachine.objects.exists())

    def test_sync_pod_links_existing_vm(self):
        project = factory.make_string()
        discovered_machine = self.make_discovered_machine(project=project)
        discovered_pod = self.make_discovered_pod(
            machines=[discovered_machine]
        )
        instance_name = discovered_machine.power_parameters["instance_name"]
        pod = factory.make_Pod(pod_type="lxd", parameters={"project": project})
        virtual_machine = factory.make_VirtualMachine(
            identifier=instance_name,
            bmc=pod,
            project=project,
        )
        self.patch(Machine, "start_commissioning")
        pod.sync(discovered_pod, factory.make_User())
        machine = Machine.objects.get(hostname=instance_name)
        self.assertEqual(machine.virtualmachine, virtual_machine)

    def test_sync_pod_links_different_vm_different_project(self):
        project = factory.make_string()
        discovered_machine = self.make_discovered_machine(project=project)
        discovered_pod = self.make_discovered_pod(
            machines=[discovered_machine]
        )
        instance_name = discovered_machine.power_parameters["instance_name"]
        pod = factory.make_Pod(pod_type="lxd", parameters={"project": project})
        other_vm = factory.make_VirtualMachine(
            identifier=instance_name,
            bmc=pod,
            project=factory.make_string(),
        )
        self.patch(Machine, "start_commissioning")
        pod.sync(discovered_pod, factory.make_User())
        machine = Machine.objects.get(hostname=instance_name)
        self.assertNotEqual(machine.virtualmachine, other_vm)

    def test_sync_pod_removes_unknown_vms(self):
        project = factory.make_string()
        discovered_machine = self.make_discovered_machine(project=project)
        instance_name = discovered_machine.power_parameters["instance_name"]
        discovered_pod = self.make_discovered_pod(
            machines=[discovered_machine]
        )
        pod = factory.make_Pod(pod_type="lxd", parameters={"project": project})
        machine1 = factory.make_Machine(bmc=pod)
        # a VM linked to a machine that's been removed on the VM host
        factory.make_VirtualMachine(
            identifier=machine1.hostname,
            bmc=pod,
            machine=machine1,
            project=project,
        )
        # a VM not linked to a machine that's been removed on the VM host
        factory.make_VirtualMachine(bmc=pod, project=project)
        self.patch(Machine, "start_commissioning")
        pod.sync(discovered_pod, factory.make_User())
        self.assertNotIn(machine1, Machine.objects.all())
        # only one VM exists, for the new discovered machine
        [new_vm] = VirtualMachine.objects.all()
        self.assertEqual(new_vm.identifier, instance_name)

    def test_sync_pod_upgrades_default_storage_pool(self):
        discovered = self.make_discovered_pod(machines=[])
        discovered_default = discovered.storage_pools[2]
        pod = factory.make_Pod(
            parameters={"default_storage_pool": discovered_default.name}
        )
        pod.sync(discovered, factory.make_User())
        self.assertEqual(
            discovered_default.name, pod.default_storage_pool.name
        )
        self.assertEqual({}, pod.get_power_parameters())

    def test_sync_pod_sets_default_numanode(self):
        discovered_bdev = self.make_discovered_block_device()
        discovered_iface = self.make_discovered_interface()
        discovered_machine = self.make_discovered_machine(
            block_devices=[discovered_bdev], interfaces=[discovered_iface]
        )
        discovered_pod = self.make_discovered_pod(
            machines=[discovered_machine]
        )
        self.patch(Machine, "start_commissioning")
        pod = factory.make_Pod()
        pod.sync(discovered_pod, factory.make_User())
        [machine] = Machine.objects.all()
        self.assertIsNotNone(machine.default_numanode)
        [bdev] = machine.physicalblockdevice_set.all()
        [iface] = machine.current_config.interface_set.all()
        self.assertEqual(bdev.numa_node, machine.default_numanode)
        self.assertEqual(iface.numa_node, machine.default_numanode)

    def test_sync_pod_ignores_unknown_values(self):
        pod = factory.make_Pod()
        # Fill Pod with data, factory doesn't do this.
        discovered_pod = self.make_discovered_pod(
            machines=[], storage_pools=[]
        )
        user = factory.make_User()
        pod.sync(discovered_pod, user)
        # Simulate sending unknown data. LXD does this as data
        # is sent in the form of a commissioning script.
        pod.sync(
            DiscoveredPod(architectures=discovered_pod.architectures), user
        )
        self.assertNotEqual(-1, pod.cores)
        self.assertNotEqual(-1, pod.cpu_speed)
        self.assertNotEqual(-1, pod.memory)
        self.assertNotEqual(-1, pod.local_storage)
        self.assertNotEqual(-1, pod.hints.cores)
        self.assertNotEqual(-1, pod.hints.cpu_speed)
        self.assertNotEqual(-1, pod.hints.memory)
        self.assertNotEqual(-1, pod.hints.local_storage)

    def test_sync_pod_with_cluster_saves_cluster_hint(self):
        pod = factory.make_Pod()
        cluster = factory.make_VMCluster(pods=0)

        discovered_pod = self.make_discovered_pod(
            machines=[], storage_pools=[]
        )
        user = factory.make_User()
        pod.sync(discovered_pod, user, cluster=cluster)

        self.assertIsNotNone(pod.hints.cluster)
        self.assertEqual(pod.hints.cluster.name, cluster.name)
        self.assertEqual(pod.hints.cluster.project, cluster.project)

    def test_create_machine_ensures_unique_hostname(self):
        existing_machine = factory.make_Node()
        discovered_machine = self.make_discovered_machine()
        discovered_machine.hostname = existing_machine.hostname
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        fabric = factory.make_Fabric()
        factory.make_VLAN(
            fabric=fabric,
            dhcp_on=True,
            primary_rack=factory.make_RackController(),
        )
        pod = factory.make_Pod()
        # Doesn't raise an exception ensures that the hostname is unique as
        # that will cause a database exception.
        pod.create_machine(discovered_machine, factory.make_User())

    def test_create_machine_creates_virtualmachine(self):
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        project = factory.make_string()
        pod = factory.make_Pod(pod_type="lxd", parameters={"project": project})
        discovered_machine = self.make_discovered_machine()
        instance_name = discovered_machine.power_parameters["instance_name"]
        machine = pod.create_machine(discovered_machine, factory.make_User())
        vm = machine.virtualmachine
        self.assertEqual(vm.identifier, instance_name)
        self.assertEqual(vm.bmc, pod)
        self.assertEqual(vm.project, project)
        self.assertEqual(vm.machine, machine)
        self.assertEqual(vm.memory, machine.memory)
        self.assertEqual(vm.unpinned_cores, machine.cpu_count)
        self.assertFalse(vm.hugepages_backed)

    def test_create_machine_creates_virtualmachine_no_project(self):
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        pod = factory.make_Pod(pod_type="virsh")
        discovered_machine = self.make_discovered_machine()
        instance_name = factory.make_string()
        discovered_machine.power_parameters = {"power_id": instance_name}
        machine = pod.create_machine(discovered_machine, factory.make_User())
        vm = machine.virtualmachine
        self.assertEqual(vm.identifier, instance_name)
        self.assertEqual(vm.project, "")

    def test_create_machine_creates_virtualmachine_with_hugepages(
        self,
    ):
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        project = factory.make_string()
        pod = factory.make_Pod(
            pod_type="lxd",
            parameters={"project": project},
        )
        discovered_machine = self.make_discovered_machine(project=project)
        discovered_machine.hugepages_backed = True
        machine = pod.create_machine(discovered_machine, factory.make_User())
        self.assertTrue(machine.virtualmachine.hugepages_backed)

    def test_create_machine_creates_virtualmachine_pinned_cores(self):
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        pod = factory.make_Pod(
            pod_type="lxd", parameters={"project": factory.make_string()}
        )
        discovered_machine = self.make_discovered_machine()
        instance_name = factory.make_string()
        discovered_machine.power_parameters["instance_name"] = instance_name
        discovered_machine.pinned_cores = [0, 1, 2]
        machine = pod.create_machine(discovered_machine, factory.make_User())
        self.assertEqual(machine.virtualmachine.unpinned_cores, 0)
        self.assertEqual(machine.virtualmachine.pinned_cores, [0, 1, 2])

    def test_create_machine_invalid_hostname(self):
        discovered_machine = self.make_discovered_machine()
        discovered_machine.hostname = "invalid_name"
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        fabric = factory.make_Fabric()
        factory.make_VLAN(
            fabric=fabric,
            dhcp_on=True,
            primary_rack=factory.make_RackController(),
        )
        pod = factory.make_Pod()
        # Doesn't raise an exception ensures that the hostname is unique as
        # that will cause a database exception.
        machine = pod.create_machine(discovered_machine, factory.make_User())
        self.assertNotEqual(machine.hostname, "invalid_name")

    def test_create_machine_pod_pool(self):
        discovered_machine = self.make_discovered_machine()
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        fabric = factory.make_Fabric()
        factory.make_VLAN(
            fabric=fabric,
            dhcp_on=True,
            primary_rack=factory.make_RackController(),
        )
        pool = factory.make_ResourcePool()
        pod = factory.make_Pod(pool=pool)
        machine = pod.create_machine(discovered_machine, factory.make_User())
        self.assertEqual(pool, machine.pool)

    def test_create_machine_default_bios_boot_method(self):
        discovered_machine = self.make_discovered_machine()
        discovered_machine.bios_boot_method = None
        fabric = factory.make_Fabric()
        factory.make_VLAN(
            fabric=fabric,
            dhcp_on=True,
            primary_rack=factory.make_RackController(),
        )
        pool = factory.make_ResourcePool()
        pod = factory.make_Pod(pool=pool)
        machine = pod.create_machine(
            discovered_machine, factory.make_User(), skip_commissioning=True
        )
        self.assertIsNone(machine.bios_boot_method)
        mount_points = [
            fs.mount_point
            for fs in Filesystem.objects.filter(
                partition__partition_table__block_device__node_config=machine.current_config
            ).all()
        ]
        self.assertEqual(["/"], mount_points)

    def test_create_machine_uefi_bios_boot_method(self):
        discovered_machine = self.make_discovered_machine()
        discovered_machine.bios_boot_method = "uefi"
        self.patch(Machine, "start_commissioning")
        fabric = factory.make_Fabric()
        factory.make_VLAN(
            fabric=fabric,
            dhcp_on=True,
            primary_rack=factory.make_RackController(),
        )
        pool = factory.make_ResourcePool()
        pod = factory.make_Pod(pool=pool)
        machine = pod.create_machine(
            discovered_machine, factory.make_User(), skip_commissioning=True
        )
        self.assertEqual("uefi", machine.bios_boot_method)
        mount_points = [
            fs.mount_point
            for fs in Filesystem.objects.filter(
                partition__partition_table__block_device__node_config=machine.current_config
            ).all()
        ]
        self.assertCountEqual(["/", "/boot/efi"], mount_points)

    def test_create_machine_sets_zone(self):
        discovered_machine = self.make_discovered_machine()
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        fabric = factory.make_Fabric()
        factory.make_VLAN(
            fabric=fabric,
            dhcp_on=True,
            primary_rack=factory.make_RackController(),
        )
        zone = factory.make_Zone()
        pod = factory.make_Pod(zone=zone)
        machine = pod.create_machine(discovered_machine, factory.make_User())
        self.assertEqual(zone, machine.zone)

    def test_create_machine_sets_pod_tags_on_machine(self):
        discovered_machine = self.make_discovered_machine()
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        fabric = factory.make_Fabric()
        factory.make_VLAN(
            fabric=fabric,
            dhcp_on=True,
            primary_rack=factory.make_RackController(),
        )
        pod = factory.make_Pod()
        tag = factory.make_Tag()
        pod.add_tag(tag.name)
        machine = pod.create_machine(discovered_machine, factory.make_User())
        self.assertIn(tag, machine.tags.all())

    def test_create_machine_sets_interface_names_using_constraint_labels(self):
        discovered_machine = self.make_discovered_machine()
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(
            fabric=fabric,
            dhcp_on=True,
            primary_rack=factory.make_RackController(),
        )
        vlan2 = factory.make_VLAN(
            fabric=fabric,
            dhcp_on=False,
            primary_rack=factory.make_RackController(),
        )
        vlan3 = factory.make_VLAN(
            fabric=fabric,
            dhcp_on=False,
            primary_rack=factory.make_RackController(),
        )
        pod = factory.make_Pod()
        machine = pod.create_machine(
            discovered_machine,
            factory.make_User(),
            interfaces=LabeledConstraintMap(
                "maas0:vlan=id:%d;maas1:vlan=id:%d;maas2:vlan=id:%d"
                % (vlan.id, vlan2.id, vlan3.id)
            ),
        )
        # Check that the interface names match the labels provided in the
        # constraints string.
        self.assertEqual(
            ["maas0", "maas1", "maas2"],
            list(
                machine.current_config.interface_set.order_by(
                    "id"
                ).values_list("name", flat=True)
            ),
        )

    def test_create_machine_allocates_requested_ip_addresses(self):
        discovered_machine = self.make_discovered_machine()
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(
            fabric=fabric,
            dhcp_on=True,
            primary_rack=factory.make_RackController(),
        )
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        vlan2 = factory.make_VLAN(
            fabric=fabric,
            dhcp_on=False,
            primary_rack=factory.make_RackController(),
        )
        subnet2 = factory.make_Subnet(vlan=vlan2)
        ip2 = factory.pick_ip_in_Subnet(subnet2)
        vlan3 = factory.make_VLAN(
            fabric=fabric,
            dhcp_on=False,
            primary_rack=factory.make_RackController(),
        )
        subnet3 = factory.make_Subnet(vlan=vlan3)
        ip3 = factory.pick_ip_in_Subnet(subnet3)
        pod = factory.make_Pod()
        rmi = RequestedMachineInterface(ifname="maas0", requested_ips=[ip])
        rmi2 = RequestedMachineInterface(ifname="maas1", requested_ips=[ip2])
        rmi3 = RequestedMachineInterface(ifname="maas2", requested_ips=[ip3])
        requested_machine = RequestedMachine(
            hostname="foo",
            architecture="amd64",
            cores=1,
            memory=1024,
            block_devices=[],
            interfaces=[rmi, rmi2, rmi3],
        )
        machine = pod.create_machine(
            discovered_machine,
            factory.make_User(),
            interfaces=LabeledConstraintMap(
                "maas0:vlan=id:%d;maas1:vlan=id:%d;maas2:ip=%s"
                % (vlan.id, vlan2.id, ip3)
            ),
            requested_machine=requested_machine,
        )
        sip = StaticIPAddress.objects.filter(ip=ip).first()
        self.assertEqual(sip.get_interface().node_config.node, machine)
        sip2 = StaticIPAddress.objects.filter(ip=ip2).first()
        self.assertEqual(sip2.get_interface().node_config.node, machine)
        sip3 = StaticIPAddress.objects.filter(ip=ip3).first()
        self.assertEqual(sip3.get_interface().node_config.node, machine)

    def test_create_machine_unconfigures_ips_upon_request(self):
        discovered_machine = self.make_discovered_machine()
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(
            fabric=fabric,
            dhcp_on=True,
            primary_rack=factory.make_RackController(),
        )
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        vlan2 = factory.make_VLAN(
            fabric=fabric,
            dhcp_on=False,
            primary_rack=factory.make_RackController(),
        )
        subnet2 = factory.make_Subnet(vlan=vlan2)
        ip2 = factory.pick_ip_in_Subnet(subnet2)
        vlan3 = factory.make_VLAN(
            fabric=fabric,
            dhcp_on=False,
            primary_rack=factory.make_RackController(),
        )
        subnet3 = factory.make_Subnet(vlan=vlan3)
        ip3 = factory.pick_ip_in_Subnet(subnet3)
        pod = factory.make_Pod()
        rmi = RequestedMachineInterface(
            ifname="maas0", requested_ips=[ip], ip_mode="unconfigured"
        )
        rmi2 = RequestedMachineInterface(
            ifname="maas1", requested_ips=[ip2], ip_mode="unconfigured"
        )
        rmi3 = RequestedMachineInterface(
            ifname="maas2", requested_ips=[ip3], ip_mode="unconfigured"
        )
        requested_machine = RequestedMachine(
            hostname="foo",
            architecture="amd64",
            cores=1,
            memory=1024,
            block_devices=[],
            interfaces=[rmi, rmi2, rmi3],
        )
        machine = pod.create_machine(
            discovered_machine,
            factory.make_User(),
            interfaces=LabeledConstraintMap(
                "maas0:vlan=id:%d,mode=unconfigured;"
                "maas1:vlan=id:%d,mode=unconfigured;"
                "maas2:ip=%s,mode=unconfigured" % (vlan.id, vlan2.id, ip3)
            ),
            requested_machine=requested_machine,
        )
        sip = StaticIPAddress.objects.filter(
            interface__name=rmi.ifname
        ).first()
        self.assertEqual(sip.get_interface().node_config.node, machine)
        self.assertIsNone(sip.ip)
        sip2 = StaticIPAddress.objects.filter(
            interface__name=rmi2.ifname
        ).first()
        self.assertEqual(sip2.get_interface().node_config.node, machine)
        self.assertIsNone(sip2.ip)
        sip3 = StaticIPAddress.objects.filter(
            interface__name=rmi3.ifname
        ).first()
        self.assertEqual(sip3.get_interface().node_config.node, machine)
        self.assertIsNone(sip3.ip)

    def test_create_machine_sets_up_interface_vlans_correctly(self):
        discovered_machine = self.make_discovered_machine()
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        fabric = factory.make_Fabric()
        controller = factory.make_RackController()
        vlan = factory.make_VLAN(
            fabric=fabric, dhcp_on=True, primary_rack=controller
        )
        vlan2 = factory.make_VLAN(
            fabric=fabric, dhcp_on=False, primary_rack=controller
        )
        vlan3 = factory.make_VLAN(
            fabric=fabric, dhcp_on=False, primary_rack=controller
        )
        # Create subnets, so we can test to ensure they get linked up.
        subnet = factory.make_Subnet(vlan=vlan)
        factory.make_Subnet(vlan=vlan2)
        factory.make_Subnet(vlan=vlan3)
        eth0 = factory.make_Interface(node=controller, vlan=vlan)
        eth1 = factory.make_Interface(node=controller, vlan=vlan2)
        eth2 = factory.make_Interface(node=controller, vlan=vlan3)
        br0 = factory.make_Interface(
            iftype=INTERFACE_TYPE.BRIDGE,
            node=controller,
            vlan=vlan,
            parents=[eth0],
        )
        ip = factory.make_StaticIPAddress(subnet=subnet, interface=br0)
        discovered_machine.interfaces[
            0
        ].attach_type = InterfaceAttachType.BRIDGE
        discovered_machine.interfaces[0].attach_name = br0.name
        discovered_machine.interfaces[
            1
        ].attach_type = InterfaceAttachType.MACVLAN
        discovered_machine.interfaces[1].attach_name = eth1.name
        discovered_machine.interfaces[
            2
        ].attach_type = InterfaceAttachType.MACVLAN
        discovered_machine.interfaces[2].attach_name = eth2.name
        pod = factory.make_Pod(ip_address=ip)
        # Skip commissioning on creation so that we can test that VLANs
        # are properly set based on the interface constraint.
        machine = pod.create_machine(
            discovered_machine,
            factory.make_User(),
            # Use numeric names to mimic what Juju will do.
            interfaces=LabeledConstraintMap(
                "0:vlan=id:%d;1:vlan=id:%d;2:vlan=id:%d"
                % (vlan.id, vlan2.id, vlan3.id)
            ),
        )
        interfaces = {
            interface.name: interface
            for interface in machine.current_config.interface_set.all()
        }
        self.assertEqual(vlan, interfaces["eth0"].vlan)
        self.assertEqual(vlan2, interfaces["eth1"].vlan)
        self.assertEqual(vlan3, interfaces["eth2"].vlan)
        # Make sure all interfaces also have a subnet link.
        self.assertEqual(1, interfaces["eth0"].ip_addresses.count())
        self.assertEqual(1, interfaces["eth1"].ip_addresses.count())
        self.assertEqual(1, interfaces["eth2"].ip_addresses.count())

    def test_create_machine_sriov_vlan(self):
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        fabric = factory.make_Fabric()
        controller = factory.make_RackController()
        vlan1 = factory.make_VLAN(
            fabric=fabric, dhcp_on=True, primary_rack=controller
        )
        vlan2 = factory.make_VLAN(
            fabric=fabric, dhcp_on=False, primary_rack=controller
        )
        factory.make_Subnet(vlan=vlan1)
        subnet1 = factory.make_Subnet(vlan=vlan1)
        subnet2 = factory.make_Subnet(vlan=vlan2)
        eth0 = factory.make_Interface(
            node=controller, vlan=vlan1, sriov_max_vf=10
        )
        factory.make_Interface(
            node=controller,
            vlan=vlan2,
            iftype=INTERFACE_TYPE.VLAN,
            parents=[eth0],
            subnet=subnet2,
        )
        ip = factory.make_StaticIPAddress(subnet=subnet1, interface=eth0)
        discovered_interfaces = [
            # An SR-IOV interface with no VLAN tagging.
            self.make_discovered_interface(
                attach_name=eth0.name, attach_type=InterfaceAttachType.SRIOV
            ),
            # An SR-IOV interface with automatic VLAN tagging.
            self.make_discovered_interface(
                attach_name=eth0.name,
                attach_type=InterfaceAttachType.SRIOV,
                vid=vlan2.vid,
            ),
            # An SR-IOV interface with no corresponding host interface that was
            # created by an lxd profile.
            self.make_discovered_interface(
                attach_name=eth0.name,
                attach_type=InterfaceAttachType.SRIOV,
                vid=vlan1.vid + vlan2.vid,
            ),
        ]
        discovered_machine = self.make_discovered_machine(
            interfaces=discovered_interfaces
        )

        pod = factory.make_Pod(ip_address=ip)
        # Skip commissioning on creation so that we can test that VLANs
        # are properly set based on the interface constraint.
        machine = pod.create_machine(
            discovered_machine,
            factory.make_User(),
            interfaces=LabeledConstraintMap(
                f"1:vlan=id:{vlan1.id};1:vlan=id:{vlan2.id}"
            ),
        )
        interfaces = {
            interface.name: interface
            for interface in machine.current_config.interface_set.all()
        }
        self.assertCountEqual(["eth0", "eth1", "eth2"], interfaces.keys())
        self.assertEqual(vlan1, interfaces["eth0"].vlan)
        self.assertEqual(1, interfaces["eth0"].ip_addresses.count())
        self.assertEqual(vlan2, interfaces["eth1"].vlan)
        self.assertEqual(1, interfaces["eth1"].ip_addresses.count())
        self.assertIsNone(interfaces["eth2"].vlan)
        self.assertEqual(0, interfaces["eth2"].ip_addresses.count())

    def test_create_machine_uses_default_ifnames_if_discovered_mismatch(self):
        """This makes sure that if the discovered machine comes back with
        a different number of interfaces than the constraint string, the
        default (ethX) names are used.
        """
        discovered_machine = self.make_discovered_machine()
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(
            fabric=fabric,
            dhcp_on=True,
            primary_rack=factory.make_RackController(),
        )
        vlan2 = factory.make_VLAN(
            fabric=fabric,
            dhcp_on=False,
            primary_rack=factory.make_RackController(),
        )
        pod = factory.make_Pod()
        # The constraint here as two labels, but the discovered machine will
        # have three interfaces.
        machine = pod.create_machine(
            discovered_machine,
            factory.make_User(),
            interfaces=LabeledConstraintMap(
                "maas0:vlan=id:%d;maas1:vlan=id:%d" % (vlan.id, vlan2.id)
            ),
        )
        # Check that the interface names use the ethX numbering, since the
        # provided constraints won't match the number of interfaces that were
        # returned.
        self.assertEqual(
            ["eth0", "eth1", "eth2"],
            list(
                machine.current_config.interface_set.order_by(
                    "id"
                ).values_list("name", flat=True)
            ),
        )

    def test_create_machine_uses_default_names_if_no_interfaces(self):
        discovered_machine = self.make_discovered_machine()
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        fabric = factory.make_Fabric()
        factory.make_VLAN(
            fabric=fabric,
            dhcp_on=True,
            primary_rack=factory.make_RackController(),
        )
        pod = factory.make_Pod()
        machine = pod.create_machine(discovered_machine, factory.make_User())
        # Check that the interface names match the labels provided in the
        # constraints string.
        self.assertEqual(
            ["eth0", "eth1", "eth2"],
            list(
                machine.current_config.interface_set.order_by(
                    "id"
                ).values_list("name", flat=True)
            ),
        )

    def test_create_machine_with_disks_creates_vmdisk(self):
        d_storage_pool1 = self.make_discovered_storage_pool()
        d_storage_pool2 = self.make_discovered_storage_pool()
        d_block_device1 = self.make_discovered_block_device(
            id_path="/dev/sda",
            storage_pools=[d_storage_pool1],
        )
        d_block_device2 = self.make_discovered_block_device(
            id_path="/dev/sdb",
            storage_pools=[d_storage_pool2],
        )
        discovered_machine = self.make_discovered_machine(
            block_devices=[d_block_device1, d_block_device2],
        )
        discovered_pool = self.make_discovered_pod(
            machines=[], storage_pools=[d_storage_pool1, d_storage_pool2]
        )
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        pod = factory.make_Pod()
        pod.sync(discovered_pool, factory.make_User())

        machine = pod.create_machine(discovered_machine, factory.make_User())
        vm = machine.virtualmachine
        vmdisk1, vmdisk2 = VirtualMachineDisk.objects.filter(vm=vm).order_by(
            "block_device__id_path"
        )
        disk1, disk2 = machine.current_config.blockdevice_set.order_by(
            "id_path"
        )
        pool1 = PodStoragePool.objects.get(pool_id=d_storage_pool1.id)
        pool2 = PodStoragePool.objects.get(pool_id=d_storage_pool2.id)
        self.assertEqual(disk1.vmdisk, vmdisk1)
        self.assertEqual(disk2.vmdisk, vmdisk2)
        self.assertEqual(vmdisk1.backing_pool, pool1)
        self.assertEqual(vmdisk2.backing_pool, pool2)
        self.assertEqual(disk1.size, vmdisk1.size)
        self.assertEqual(disk2.size, vmdisk2.size)

    def test_create_new_machine_skips_commissioning_if_no_mac_is_present(self):
        discovered_machine = self.make_discovered_machine()
        for iface in discovered_machine.interfaces:
            iface.mac_address = None

        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        self.patch(Machine, "_release")
        fabric = factory.make_Fabric()
        factory.make_VLAN(
            fabric=fabric,
            dhcp_on=True,
            primary_rack=factory.make_RackController(),
        )
        pod = factory.make_Pod()
        machine = pod.create_machine(discovered_machine, factory.make_User())
        self.assertEqual(machine.status, NODE_STATUS.BROKEN)
        machine.start_commissioning.assert_not_called()

    def test_create_new_machine_does_not_skip_commissioning_if_mac_is_present(
        self,
    ):
        discovered_machine = self.make_discovered_machine()
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        fabric = factory.make_Fabric()
        factory.make_VLAN(
            fabric=fabric,
            dhcp_on=True,
            primary_rack=factory.make_RackController(),
        )
        pod = factory.make_Pod()
        machine = pod.create_machine(discovered_machine, factory.make_User())
        machine.start_commissioning.assert_called_once()

    def test_sync_pod_creates_new_machines_connected_to_dhcp_vlan(self):
        discovered = self.make_discovered_pod()
        mock_set_default_storage_layout = self.patch(
            Machine, "set_default_storage_layout"
        )
        mock_set_initial_networking_configuration = self.patch(
            Machine, "set_initial_networking_configuration"
        )
        mock_start_commissioning = self.patch(Machine, "start_commissioning")
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(
            fabric=fabric,
            dhcp_on=True,
            primary_rack=factory.make_RackController(),
        )
        pod = factory.make_Pod()
        pod.sync(discovered, factory.make_User())
        machine_macs = [
            machine.interfaces[0].mac_address
            for machine in discovered.machines
        ]
        created_machines = Machine.objects.filter(
            current_config__interface__mac_address__in=machine_macs
        ).distinct()
        for created_machine, discovered_machine in zip(
            created_machines, discovered.machines
        ):
            self.assertEqual(
                created_machine.architecture, discovered_machine.architecture
            )
            self.assertEqual(created_machine.bmc, pod)
            self.assertEqual(
                created_machine.cpu_count, discovered_machine.cores
            )
            self.assertEqual(
                created_machine.cpu_speed, discovered_machine.cpu_speed
            )
            self.assertEqual(created_machine.memory, discovered_machine.memory)
            self.assertEqual(
                created_machine.power_state, discovered_machine.power_state
            )
            self.assertEqual(
                created_machine.get_instance_power_parameters(),
                discovered_machine.power_parameters,
            )
            self.assertFalse(created_machine.dynamic)
            self.assertCountEqual(
                [tag.name for tag in created_machine.tags.all()],
                discovered_machine.tags,
            )
            self.assertIsNotNone(created_machine.boot_interface)
            for created_device, (idx, discovered_device) in zip(
                created_machine.physicalblockdevice_set,
                enumerate(discovered_machine.block_devices),
            ):
                self.assertEqual(
                    created_device.name,
                    BlockDevice._get_block_name_from_idx(idx),
                )
                self.assertEqual(
                    created_device.id_path, discovered_device.id_path
                )
                self.assertEqual(created_device.model, discovered_device.model)
                self.assertEqual(
                    created_device.serial, discovered_device.serial
                )
                self.assertEqual(created_device.size, discovered_device.size)
                self.assertEqual(
                    created_device.block_size, discovered_device.block_size
                )
                self.assertCountEqual(
                    created_device.tags, discovered_device.tags
                )
            for created_if, (idx, discovered_if) in zip(
                created_machine.current_config.interface_set.all(),
                enumerate(discovered_machine.interfaces),
            ):
                self.assertEqual(created_if.name, f"eth{idx}")
                self.assertEqual(
                    created_if.mac_address, discovered_if.mac_address
                )
                self.assertEqual(
                    created_if.vlan,
                    vlan if discovered_if.boot else None,
                )
                self.assertEqual(created_if.tags, discovered_if.tags)
        mock_set_default_storage_layout.assert_not_called()
        mock_set_initial_networking_configuration.assert_not_called()
        self.assertEqual(
            mock_start_commissioning.call_count,
            len(discovered.machines),
        )

    def test_create_machine_with_bad_physical_block_device(self):
        block_device = self.make_discovered_block_device()
        block_device.serial = None
        block_device.id_path = None
        machine = self.make_discovered_machine(block_devices=[block_device])
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        fabric = factory.make_Fabric()
        factory.make_VLAN(
            fabric=fabric,
            dhcp_on=True,
            primary_rack=factory.make_RackController(),
        )
        pod = factory.make_Pod()
        pod.create_machine(machine, factory.make_User())
        created_machine = Machine.objects.get(
            current_config__interface__mac_address=machine.interfaces[
                0
            ].mac_address
        )
        self.assertEqual(created_machine.architecture, machine.architecture)
        self.assertEqual(created_machine.bmc, pod)
        self.assertEqual(created_machine.cpu_count, machine.cores)
        self.assertEqual(created_machine.cpu_speed, machine.cpu_speed)
        self.assertEqual(created_machine.memory, machine.memory)
        self.assertEqual(created_machine.power_state, machine.power_state)
        self.assertEqual(
            created_machine.instance_power_parameters, machine.power_parameters
        )
        self.assertFalse(created_machine.dynamic)
        self.assertCountEqual(
            [tag.name for tag in created_machine.tags.all()], machine.tags
        )
        self.assertCountEqual(
            created_machine.physicalblockdevice_set.all(), []
        )

    def test_create_machine_doesnt_allow_bad_physical_block_device(self):
        block_device = self.make_discovered_block_device()
        block_device.serial = None
        block_device.id_path = None
        machine = self.make_discovered_machine(block_devices=[block_device])
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        fabric = factory.make_Fabric()
        factory.make_VLAN(
            fabric=fabric,
            dhcp_on=True,
            primary_rack=factory.make_RackController(),
        )
        pod = factory.make_Pod()
        self.assertRaises(
            ValidationError,
            pod.create_machine,
            machine,
            factory.make_User(),
            skip_commissioning=True,
        )

    def test_create_machine_creates_machine_with_parent_child_relation(self):
        self.patch(Machine, "set_default_storage_layout")
        self.patch(Machine, "set_initial_networking_configuration")
        self.patch(Machine, "start_commissioning")
        project = factory.make_string()
        host = factory.make_Machine_with_Interface_on_Subnet()
        pod = factory.make_Pod(
            host=host, pod_type="lxd", parameters={"project": project}
        )
        discovered_machine = self.make_discovered_machine()
        machine = pod.create_machine(discovered_machine, factory.make_User())
        self.assertEqual(machine.parent, host)

    def test_sync_pod_deletes_missing_machines(self):
        pod = factory.make_Pod()
        machine = factory.make_Node()
        machine.bmc = pod
        machine.save()
        discovered = self.make_discovered_pod(machines=[])
        pod.sync(discovered, factory.make_User())
        self.assertIsNone(reload_object(machine))

    def test_sync_moves_machine_under_pod(self):
        pod = factory.make_Pod()
        machine = factory.make_Node(interface=True)
        discovered_interface = self.make_discovered_interface(
            mac_address=machine.current_config.interface_set.first().mac_address
        )
        discovered_machine = self.make_discovered_machine(
            interfaces=[discovered_interface]
        )
        discovered_pod = self.make_discovered_pod(
            machines=[discovered_machine]
        )
        pod.sync(discovered_pod, factory.make_User())
        machine = reload_object(machine)
        self.assertEqual(pod.id, machine.bmc.id)

    def test_sync_keeps_rack_controller_pod_nodes(self):
        pod = factory.make_Pod()
        controller = factory.make_RackController(interface=True)
        discovered_interface = self.make_discovered_interface(
            mac_address=controller.current_config.interface_set.first().mac_address
        )
        discovered_machine = self.make_discovered_machine(
            interfaces=[discovered_interface]
        )
        discovered_pod = self.make_discovered_pod(
            machines=[discovered_machine]
        )
        pod.sync(discovered_pod, factory.make_User())
        controller = reload_object(controller)
        self.assertEqual(NODE_TYPE.RACK_CONTROLLER, controller.node_type)

    def test_sync_updates_machine_properties_for_dynamic(self):
        pod = factory.make_Pod()
        machine = factory.make_Node(interface=True, dynamic=True)
        discovered_interface = self.make_discovered_interface(
            mac_address=machine.current_config.interface_set.first().mac_address
        )
        discovered_machine = self.make_discovered_machine(
            interfaces=[discovered_interface]
        )
        discovered_pod = self.make_discovered_pod(
            machines=[discovered_machine]
        )
        pod.sync(discovered_pod, factory.make_User())
        machine = reload_object(machine)
        self.assertEqual(machine.architecture, discovered_machine.architecture)
        self.assertEqual(machine.cpu_count, discovered_machine.cores)
        self.assertEqual(machine.cpu_speed, discovered_machine.cpu_speed)
        self.assertEqual(machine.memory, discovered_machine.memory)
        self.assertEqual(machine.power_state, discovered_machine.power_state)
        self.assertEqual(
            machine.instance_power_parameters,
            discovered_machine.power_parameters,
        )
        self.assertCountEqual(
            [tag.name for tag in machine.tags.all()], discovered_machine.tags
        )

    def test_sync_updates_machine_properties_for_not_dynamic(self):
        pod = factory.make_Pod()
        machine = factory.make_Node(interface=True, dynamic=False)
        discovered_interface = self.make_discovered_interface(
            mac_address=machine.current_config.interface_set.first().mac_address
        )
        discovered_machine = self.make_discovered_machine(
            interfaces=[discovered_interface]
        )
        discovered_pod = self.make_discovered_pod(
            machines=[discovered_machine]
        )
        pod.sync(discovered_pod, factory.make_User())
        machine = reload_object(machine)
        self.assertEqual(machine.cpu_count, discovered_machine.cores)
        self.assertEqual(machine.memory, discovered_machine.memory)
        self.assertEqual(machine.power_state, discovered_machine.power_state)
        self.assertEqual(
            machine.instance_power_parameters,
            discovered_machine.power_parameters,
        )

    def test_sync_creates_machine_vm(self):
        project = factory.make_string()
        pod = factory.make_Pod(pod_type="lxd", parameters={"project": project})
        machine = factory.make_Node(interface=True)
        discovered_interface = self.make_discovered_interface(
            mac_address=machine.current_config.interface_set.first().mac_address,
        )
        discovered_machine = self.make_discovered_machine(
            project=project, interfaces=[discovered_interface]
        )
        discovered_machine.hugepages_backed = True
        discovered_machine.pinned_cores = [0, 1, 2]
        discovered_pod = self.make_discovered_pod(
            machines=[discovered_machine]
        )
        pod.sync(discovered_pod, factory.make_User())
        machine = reload_object(machine)
        vm = machine.virtualmachine
        self.assertTrue(vm.hugepages_backed)
        self.assertEqual(vm.pinned_cores, [0, 1, 2])
        self.assertEqual(vm.project, project)

    def test_sync_creates_machine_vm_no_project(self):
        pod = factory.make_Pod(pod_type="virsh")
        machine = factory.make_Node(interface=True)
        discovered_interface = self.make_discovered_interface(
            mac_address=machine.current_config.interface_set.first().mac_address,
        )
        discovered_machine = self.make_discovered_machine(
            interfaces=[discovered_interface]
        )
        discovered_machine.hugepages_backed = True
        discovered_machine.pinned_cores = [0, 1, 2]
        discovered_pod = self.make_discovered_pod(
            machines=[discovered_machine]
        )
        pod.sync(discovered_pod, factory.make_User())
        machine = reload_object(machine)
        vm = machine.virtualmachine
        self.assertTrue(vm.hugepages_backed)
        self.assertEqual(vm.project, "")

    def test_sync_updates_machine_vm(self):
        project = factory.make_string()
        pod = factory.make_Pod(pod_type="lxd", parameters={"project": project})
        machine = factory.make_Node(interface=True)
        vm = factory.make_VirtualMachine(
            identifier=machine.hostname,
            bmc=pod,
            project=project,
            machine=machine,
            hugepages_backed=False,
        )
        discovered_interface = self.make_discovered_interface(
            mac_address=machine.current_config.interface_set.first().mac_address,
        )
        discovered_machine = self.make_discovered_machine(
            project=project, interfaces=[discovered_interface]
        )
        discovered_machine.hugepages_backed = True
        discovered_machine.pinned_cores = [0, 1, 2]
        discovered_machine.hostname = machine.hostname
        discovered_machine.power_parameters["instance_name"] = machine.hostname
        discovered_pod = self.make_discovered_pod(
            machines=[discovered_machine]
        )
        pod.sync(discovered_pod, factory.make_User())
        vm = reload_object(vm)
        self.assertTrue(vm.hugepages_backed)
        self.assertEqual(vm.pinned_cores, [0, 1, 2])

    def test_sync_updates_machine_bmc_deletes_old_bmc(self):
        pod = factory.make_Pod()
        machine = factory.make_Node(interface=True)
        old_bmc = factory.make_BMC()
        machine.bmc = old_bmc
        machine.save()
        discovered_interface = self.make_discovered_interface(
            mac_address=machine.current_config.interface_set.first().mac_address
        )
        discovered_machine = self.make_discovered_machine(
            interfaces=[discovered_interface]
        )
        discovered_pod = self.make_discovered_pod(
            machines=[discovered_machine]
        )
        pod.sync(discovered_pod, factory.make_User())
        machine = reload_object(machine)
        old_bmc = reload_object(old_bmc)
        self.assertIsNone(old_bmc)
        self.assertEqual(pod, machine.bmc)

    def test_sync_updates_machine_bmc_keeps_old_bmc(self):
        pod = factory.make_Pod()
        rack_controller = factory.make_RackController()
        machine = factory.make_Node(
            interface=True,
            power_type="virsh",
            bmc_connected_to=rack_controller,
        )
        old_bmc = machine.bmc

        # Create another machine sharing the BMC. This should prevent the
        # BMC from being deleted.
        other_machine = factory.make_Node(interface=True)
        other_machine.bmc = machine.bmc
        other_machine.instance_power_parameter = {
            "power_id": factory.make_name("power_id")
        }
        other_machine.save()

        discovered_interface = self.make_discovered_interface(
            mac_address=machine.current_config.interface_set.first().mac_address
        )
        discovered_machine = self.make_discovered_machine(
            interfaces=[discovered_interface]
        )
        discovered_pod = self.make_discovered_pod(
            machines=[discovered_machine]
        )
        pod.sync(discovered_pod, factory.make_User())
        machine = reload_object(machine)
        old_bmc = reload_object(old_bmc)
        self.assertIsNotNone(old_bmc)
        self.assertEqual(pod, machine.bmc.as_self())

    def test_sync_updates_existing_machine_block_devices_for_dynamic(self):
        pod = factory.make_Pod()
        machine = factory.make_Node(with_boot_disk=False, dynamic=True)
        boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=machine
        )
        keep_model_bd = factory.make_PhysicalBlockDevice(node=machine)
        keep_path_bd = factory.make_PhysicalBlockDevice(
            node=machine, id_path=factory.make_name("id_path")
        )
        delete_model_bd = factory.make_PhysicalBlockDevice(node=machine)
        delete_path_bd = factory.make_PhysicalBlockDevice(
            node=machine, id_path=factory.make_name("id_path")
        )
        dkeep_model_bd = self.make_discovered_block_device(
            model=keep_model_bd.model, serial=keep_model_bd.serial
        )
        dkeep_path_bd = self.make_discovered_block_device(
            id_path=keep_path_bd.id_path
        )
        dnew_model_bd = self.make_discovered_block_device()
        dnew_path_bd = self.make_discovered_block_device(
            id_path=factory.make_name("id_path")
        )
        discovered_machine = self.make_discovered_machine(
            block_devices=[
                dkeep_model_bd,
                dkeep_path_bd,
                dnew_model_bd,
                dnew_path_bd,
            ],
            interfaces=[
                self.make_discovered_interface(
                    mac_address=boot_interface.mac_address
                )
            ],
        )
        discovered_machine.power_parameters[
            "instance_name"
        ] = factory.make_string()
        discovered_pod = self.make_discovered_pod(
            machines=[discovered_machine]
        )
        pod.sync(discovered_pod, factory.make_User())
        machine = reload_object(machine)
        keep_model_bd = reload_object(keep_model_bd)
        keep_path_bd = reload_object(keep_path_bd)
        delete_model_bd = reload_object(delete_model_bd)
        delete_path_bd = reload_object(delete_path_bd)
        node_config = machine.current_config
        new_model_bd = PhysicalBlockDevice.objects.filter(
            node_config=node_config,
            model=dnew_model_bd.model,
            serial=dnew_model_bd.serial,
        ).first()
        new_path_bd = PhysicalBlockDevice.objects.filter(
            node_config=node_config, id_path=dnew_path_bd.id_path
        ).first()
        self.assertIsNone(delete_model_bd)
        self.assertIsNone(delete_path_bd)

        self.assertEqual(keep_model_bd.size, dkeep_model_bd.size)
        self.assertEqual(keep_model_bd.block_size, dkeep_model_bd.block_size)
        self.assertCountEqual(keep_model_bd.tags, dkeep_model_bd.tags)
        self.assertEqual(keep_model_bd.vmdisk.size, dkeep_model_bd.size)

        self.assertEqual(keep_path_bd.size, dkeep_path_bd.size)
        self.assertEqual(keep_path_bd.block_size, dkeep_path_bd.block_size)
        self.assertCountEqual(keep_path_bd.tags, dkeep_path_bd.tags)
        self.assertEqual(keep_path_bd.vmdisk.size, dkeep_path_bd.size)

        self.assertEqual(new_model_bd.size, dnew_model_bd.size)
        self.assertEqual(new_model_bd.block_size, dnew_model_bd.block_size)
        self.assertCountEqual(new_model_bd.tags, dnew_model_bd.tags)
        self.assertEqual(new_model_bd.vmdisk.size, dnew_model_bd.size)

        self.assertEqual(new_path_bd.size, dnew_path_bd.size)
        self.assertEqual(new_path_bd.block_size, dnew_path_bd.block_size)
        self.assertCountEqual(new_path_bd.tags, dnew_path_bd.tags)
        self.assertEqual(new_path_bd.vmdisk.size, dnew_path_bd.size)

    def test_sync_updates_existing_machine_cpu_memory(self):
        pod = factory.make_Pod(pod_type="virsh")
        machine = factory.make_Node(interface=True, cpu_count=2, memory=1024)
        discovered_interface = self.make_discovered_interface(
            mac_address=machine.current_config.interface_set.first().mac_address,
        )
        discovered_machine = self.make_discovered_machine(
            interfaces=[discovered_interface]
        )
        discovered_machine.cores = 3
        discovered_machine.memory = 4096
        discovered_pod = self.make_discovered_pod(
            machines=[discovered_machine]
        )
        pod.sync(discovered_pod, factory.make_User())
        machine = reload_object(machine)
        self.assertEqual(machine.cpu_count, 3)
        self.assertEqual(machine.memory, 4096)

    def test_sync_updates_existing_machine_interfaces_for_dynamic(self):
        pod = factory.make_Pod()
        machine = factory.make_Node(dynamic=True)
        other_vlan = factory.make_Fabric().get_default_vlan()
        keep_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=machine, vlan=other_vlan
        )
        delete_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=machine
        )
        dkeep_interface = self.make_discovered_interface(
            mac_address=keep_interface.mac_address
        )
        dnew_interface = self.make_discovered_interface()
        dnew_interface.boot = True
        discovered_machine = self.make_discovered_machine(
            interfaces=[dkeep_interface, dnew_interface]
        )
        discovered_pod = self.make_discovered_pod(
            machines=[discovered_machine]
        )
        pod.sync(discovered_pod, factory.make_User())
        machine = reload_object(machine)
        keep_interface = reload_object(keep_interface)
        delete_interface = reload_object(delete_interface)
        new_interface = machine.current_config.interface_set.filter(
            mac_address=dnew_interface.mac_address
        ).first()
        self.assertIsNone(delete_interface)
        self.assertEqual(keep_interface.vlan, other_vlan)
        self.assertCountEqual(keep_interface.tags, dkeep_interface.tags)

        self.assertEqual(
            new_interface.vlan,
            Fabric.objects.get_default_fabric().get_default_vlan(),
        )
        self.assertCountEqual(new_interface.tags, dnew_interface.tags)
        self.assertEqual(new_interface, machine.boot_interface)

    def test_sync_updates_existing_machine_vmdisks(self):
        pod = factory.make_Pod()
        machine = factory.make_Node(with_boot_disk=False, dynamic=True)
        boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=machine
        )
        disk1 = factory.make_PhysicalBlockDevice(
            node=machine,
            id_path=factory.make_name("id_path"),
        )
        disk2 = factory.make_PhysicalBlockDevice(
            node=machine,
            id_path=factory.make_name("id_path"),
        )
        d_disk1 = self.make_discovered_block_device(id_path=disk1.id_path)
        d_disk2 = self.make_discovered_block_device(id_path=disk2.id_path)
        discovered_machine = self.make_discovered_machine(
            block_devices=[d_disk1, d_disk2],
            interfaces=[
                self.make_discovered_interface(
                    mac_address=boot_interface.mac_address
                )
            ],
        )
        discovered_machine.power_parameters[
            "instance_name"
        ] = factory.make_string()
        discovered_pod = self.make_discovered_pod(
            machines=[discovered_machine]
        )
        pod.sync(discovered_pod, factory.make_User())
        machine = reload_object(machine)
        vmdisk1 = disk1.vmdisk
        vmdisk2 = disk2.vmdisk
        self.assertIsNotNone(vmdisk1)
        self.assertIsNotNone(vmdisk2)
        discovered_machine.block_devices = [d_disk1]
        pod.sync(discovered_pod, factory.make_User())
        # the second disk and its VirtualMachineDisk are removed
        self.assertIsNone(reload_object(disk2))
        self.assertIsNone(reload_object(vmdisk2))

    def test_sync_creates_vmdisk_other_project(self):
        pod = factory.make_Pod(
            pod_type="lxd", parameters={"project": factory.make_string()}
        )
        discovered_pool1 = self.make_discovered_storage_pool()
        discovered_pool2 = self.make_discovered_storage_pool()
        discovered_machine = self.make_discovered_machine(
            block_devices=[
                self.make_discovered_block_device(
                    storage_pools=[discovered_pool1]
                ),
                self.make_discovered_block_device(
                    storage_pools=[discovered_pool2]
                ),
            ],
        )
        instance_name = factory.make_string()
        discovered_machine.power_parameters = {
            "instance_name": instance_name,
            "project": factory.make_string(),
        }
        discovered_pod = self.make_discovered_pod(
            machines=[discovered_machine],
            storage_pools=[discovered_pool1, discovered_pool2],
        )
        pod.sync(discovered_pod, factory.make_User())
        self.assertEqual(Machine.objects.count(), 0)
        vm = VirtualMachine.objects.get(identifier=instance_name)
        vmdisk1, vmdisk2 = VirtualMachineDisk.objects.filter(vm=vm).order_by(
            "backing_pool_id"
        )
        pool1 = PodStoragePool.objects.get(name=discovered_pool1.name)
        pool2 = PodStoragePool.objects.get(name=discovered_pool2.name)
        self.assertEqual(vmdisk1.backing_pool, pool1)
        self.assertEqual(vmdisk2.backing_pool, pool2)

    def test_sync_associates_existing_node(self):
        pod = factory.make_Pod()
        node = factory.make_Node_with_Interface_on_Subnet()
        pod.sync(
            DiscoveredPod(
                architectures=[node.architecture],
                name=node.hostname,
                mac_addresses=[
                    str(iface.mac_address)
                    for iface in node.current_config.interface_set.all()
                ],
            ),
            factory.make_User(),
        )
        node = reload_object(node)
        self.assertCountEqual([node], pod.hints.nodes.all())
        self.assertEqual(NODE_STATUS.DEPLOYED, node.status)
        self.assertIsNotNone(node.current_commissioning_script_set)

    def test_sync_converts_existing_device(self):
        pod = factory.make_Pod()
        device = factory.make_Node_with_Interface_on_Subnet(
            node_type=NODE_TYPE.DEVICE
        )
        pod.sync(
            DiscoveredPod(
                architectures=[device.architecture],
                name=device.hostname,
                mac_addresses=[
                    str(iface.mac_address)
                    for iface in device.current_config.interface_set.all()
                ],
            ),
            factory.make_User(),
        )
        device = reload_object(device)
        self.assertCountEqual([device], pod.hints.nodes.all())
        self.assertEqual(NODE_STATUS.DEPLOYED, device.status)
        self.assertEqual(NODE_TYPE.MACHINE, device.node_type)
        self.assertIsNotNone(device.current_commissioning_script_set)
        self.assertFalse(device.dynamic)

    def test_sync_creates_machine(self):
        factory.make_usable_boot_resource(architecture="amd64/generic")
        pod = factory.make_Pod()
        mac_addresses = [factory.make_mac_address() for _ in range(3)]
        sync_user = factory.make_User()
        pod.sync(
            DiscoveredPod(
                architectures=["amd64/generic"], mac_addresses=mac_addresses
            ),
            sync_user,
        )
        self.assertEqual(1, pod.hints.nodes.count())
        node = pod.hints.nodes.first()
        self.assertEqual(pod.name, node.hostname)
        self.assertEqual(NODE_STATUS.DEPLOYED, node.status)
        self.assertEqual(NODE_TYPE.MACHINE, node.node_type)
        self.assertEqual(sync_user, node.owner)
        self.assertCountEqual(
            mac_addresses,
            [
                str(iface.mac_address)
                for iface in node.current_config.interface_set.all()
            ],
        )
        self.assertIsNotNone(node.current_commissioning_script_set)
        self.assertTrue(node.dynamic)

    def test_sync_hints_from_nodes(self):
        pod = factory.make_Pod()
        nodes = [factory.make_Node() for _ in range(random.randint(1, 3))]
        for node in nodes:
            numa = node.default_numanode
            numa.cores = list(range(2 ** random.randint(0, 4)))
            numa.memory = 1024 * random.randint(1, 256)
            numa.save()
            for _ in range(2 ** random.randint(0, 4) - 1):
                factory.make_NUMANode(node=node)
            pod.hints.nodes.add(node)

        pod.sync_hints_from_nodes()

        cores = 0
        cpu_speeds = []
        memory = 0
        local_storage = 0
        for node in nodes:
            for numa in node.numanode_set.all():
                cores += len(numa.cores)
                memory += numa.memory
            cpu_speeds.append(node.cpu_speed)
            for bd in node.current_config.blockdevice_set.all():
                if bd.type == "physical":
                    local_storage += bd.size

        self.assertEqual(pod.hints.cores, cores)
        self.assertEqual(
            pod.hints.cpu_speed,
            int(mean(cpu_speeds)),
            f"Wrong hint ({pod.hints.cpu_speed}) for CPU speed. CPU speeds of nodes: {cpu_speeds}",
        )
        self.assertEqual(pod.hints.memory, memory)

    def test_sync_machine_memory(self):
        pod = factory.make_Pod(
            pod_type="lxd", parameters={"project": factory.make_string()}
        )
        machine = factory.make_Machine(memory=1234)
        discovered_machine = self.make_discovered_machine(memory=5678)
        VirtualMachine.objects.create(
            identifier=discovered_machine.hostname,
            project=factory.make_string(),
            bmc=pod,
            memory=9123,
            machine=machine,
        )
        pod._sync_machine(discovered_machine, machine)
        self.assertEqual(5678, machine.virtualmachine.memory)

    def test_sync_machine_interface_new(self):
        pod = factory.make_Pod(pod_type="lxd")
        interface = self.make_discovered_interface(
            mac_address="11:22:33:44:55:66",
            attach_type=InterfaceAttachType.BRIDGE,
        )
        machine = factory.make_Machine()
        discovered_machine = self.make_discovered_machine(
            interfaces=[interface],
        )
        VirtualMachine.objects.create(
            identifier=discovered_machine.hostname,
            project=factory.make_string(),
            bmc=pod,
            machine=machine,
        )
        pod._sync_machine(discovered_machine, machine)
        created_interface = VirtualMachineInterface.objects.get(
            vm=machine.virtualmachine
        )
        self.assertEqual("11:22:33:44:55:66", created_interface.mac_address)
        self.assertEqual(
            InterfaceAttachType.BRIDGE, created_interface.attachment_type
        )

    def test_sync_machine_interface_existing(self):
        pod = factory.make_Pod(pod_type="lxd")
        interface = self.make_discovered_interface(
            mac_address="11:22:33:44:55:66",
            attach_type=InterfaceAttachType.BRIDGE,
        )
        machine = factory.make_Machine()
        discovered_machine = self.make_discovered_machine(
            interfaces=[interface],
        )
        vm = VirtualMachine.objects.create(
            project=factory.make_string(),
            identifier=discovered_machine.hostname,
            bmc=pod,
            machine=machine,
        )
        VirtualMachineInterface.objects.create(
            vm=vm,
            mac_address="11:22:33:44:55:66",
            attachment_type=InterfaceAttachType.MACVLAN,
        )
        pod._sync_machine(discovered_machine, machine)
        created_interface = VirtualMachineInterface.objects.get(
            vm=machine.virtualmachine
        )
        self.assertEqual(
            "11:22:33:44:55:66", str(created_interface.mac_address)
        )
        self.assertEqual(
            InterfaceAttachType.BRIDGE, created_interface.attachment_type
        )

    def test_sync_machine_interface_removed(self):
        pod = factory.make_Pod(pod_type="lxd")
        pod2 = factory.make_Pod(pod_type="lxd")
        interface = self.make_discovered_interface(
            mac_address="11:22:33:44:55:66",
            attach_type=InterfaceAttachType.BRIDGE,
        )
        machine = factory.make_Machine()
        machine2 = factory.make_Machine()
        discovered_machine = self.make_discovered_machine(
            interfaces=[interface],
        )
        vm = VirtualMachine.objects.create(
            project=factory.make_string(),
            identifier=discovered_machine.hostname,
            bmc=pod,
            machine=machine,
        )
        vm2 = VirtualMachine.objects.create(
            identifier="vm2",
            project=factory.make_string(),
            bmc=pod2,
            machine=machine2,
        )
        VirtualMachineInterface.objects.create(
            vm=vm,
            mac_address="11:22:33:44:55:66",
            attachment_type=InterfaceAttachType.BRIDGE,
        )
        VirtualMachineInterface.objects.create(
            vm=vm,
            mac_address="22:33:44:55:66:77",
            attachment_type=InterfaceAttachType.MACVLAN,
        )
        # Make sure interfaces for other VMs won't be removed.
        VirtualMachineInterface.objects.create(
            vm=vm2,
            mac_address="33:44:55:66:77:88",
            attachment_type=InterfaceAttachType.MACVLAN,
        )
        pod._sync_machine(discovered_machine, machine)
        vm_interface = VirtualMachineInterface.objects.get(
            vm=machine.virtualmachine
        )
        self.assertEqual("11:22:33:44:55:66", str(vm_interface.mac_address))
        self.assertEqual(
            InterfaceAttachType.BRIDGE, vm_interface.attachment_type
        )
        vm2_interface = VirtualMachineInterface.objects.get(
            vm=machine2.virtualmachine
        )
        self.assertEqual("33:44:55:66:77:88", str(vm2_interface.mac_address))

    def test_sync_machine_interface_no_mac_address(self):
        project = factory.make_string()
        pod = factory.make_Pod(pod_type="lxd", parameters={"project": project})
        interface1 = self.make_discovered_interface(
            mac_address=None,
            attach_type=InterfaceAttachType.SRIOV,
        )
        interface2 = self.make_discovered_interface(
            mac_address=None,
            attach_type=InterfaceAttachType.SRIOV,
        )
        machine = factory.make_Machine()
        discovered_machine = self.make_discovered_machine(
            project=project,
            interfaces=[interface1, interface2],
        )
        pod._sync_machine(discovered_machine, machine)
        vm_interface1, vm_interface2 = VirtualMachineInterface.objects.filter(
            vm=machine.virtualmachine
        ).order_by("id")
        self.assertIsNone(vm_interface1.mac_address)
        self.assertEqual(
            InterfaceAttachType.SRIOV, vm_interface1.attachment_type
        )
        self.assertIsNone(vm_interface2.mac_address)
        self.assertEqual(
            InterfaceAttachType.SRIOV, vm_interface2.attachment_type
        )

    def test_sync_machine_interface_no_pod_host(self):
        project = factory.make_string()
        pod = factory.make_Pod(
            pod_type="lxd", host=None, parameters={"project": project}
        )
        interface = self.make_discovered_interface(
            mac_address="11:22:33:44:55:66",
            attach_type=InterfaceAttachType.BRIDGE,
            attach_name="eth0",
        )
        machine = factory.make_Machine()
        discovered_machine = self.make_discovered_machine(
            project=project,
            interfaces=[interface],
        )
        pod._sync_machine(discovered_machine, machine)
        vm_interface = VirtualMachineInterface.objects.get(
            vm=machine.virtualmachine
        )
        self.assertIsNone(pod.host)
        self.assertIsNone(vm_interface.host_interface)

    def test_sync_machine_interface_no_pod_host_interface(self):
        project = factory.make_string()
        pod_host = factory.make_Machine()
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, name="eth0", node=pod_host
        )
        pod = factory.make_Pod(
            pod_type="lxd",
            parameters={"project": project},
            host=pod_host,
        )
        interface = self.make_discovered_interface(
            mac_address="11:22:33:44:55:66",
            attach_type=InterfaceAttachType.MACVLAN,
            attach_name="nosuchiface",
        )
        machine = factory.make_Machine()
        discovered_machine = self.make_discovered_machine(
            project=project,
            interfaces=[interface],
        )
        pod._sync_machine(discovered_machine, machine)
        vm_interface = VirtualMachineInterface.objects.get(
            vm=machine.virtualmachine
        )
        self.assertIsNone(vm_interface.host_interface)

    def test_sync_machine_interface_with_pod_host_interface(self):
        pod_host = factory.make_Machine()
        host_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, name="eth0", node=pod_host
        )
        project = factory.make_string()
        pod = factory.make_Pod(
            pod_type="lxd",
            parameters={"project": project},
            host=pod_host,
        )
        interface = self.make_discovered_interface(
            mac_address="11:22:33:44:55:66",
            attach_type=InterfaceAttachType.MACVLAN,
            attach_name="eth0",
        )
        machine = factory.make_Machine()
        discovered_machine = self.make_discovered_machine(
            project=project,
            interfaces=[interface],
        )
        pod._sync_machine(discovered_machine, machine)
        vm_interface = VirtualMachineInterface.objects.get(
            vm=machine.virtualmachine
        )
        self.assertEqual(host_interface, vm_interface.host_interface)

    def test_sync_machines_uses_location_to_set_bmc_in_a_cluster(self):
        self.patch(Machine, "start_commissioning").return_value = None
        project = factory.make_string()
        cluster = factory.make_VMCluster(pods=0, project=project)
        vmhosts = [
            factory.make_Pod(
                pod_type="lxd",
                cluster=cluster,
                parameters={
                    "project": project,
                    "power_address": f"https://10.0.0.{i}:8443",
                },
            )
            for i in range(3)
        ]
        admin = factory.make_admin()
        discovered_machines = [
            self.make_discovered_machine(project=project, location=vmhost.name)
            for vmhost in vmhosts
        ]
        for vmhost in vmhosts:
            vmhost.sync_machines(discovered_machines, admin)
        bmc_ids = [vmhost.id for vmhost in vmhosts]
        discovered_machines[0].memory = 1024
        for vmhost in vmhosts:
            vmhost.sync_machines(discovered_machines, admin)
        new_bmc_ids = [vm.bmc_id for vm in cluster.virtual_machines()]
        self.assertCountEqual(bmc_ids, new_bmc_ids)
        vm = VirtualMachine.objects.get(
            identifier=discovered_machines[0].hostname
        )
        self.assertEqual(vm.memory, discovered_machines[0].memory)

    def test_sync_machines_uses_location_to_update_bmc_in_a_cluster(self):
        self.patch(Machine, "start_commissioning").return_value = None
        project = factory.make_string()
        cluster = factory.make_VMCluster(pods=0, project=project)
        vmhosts = [
            factory.make_Pod(
                pod_type="lxd",
                cluster=cluster,
                parameters={
                    "project": project,
                    "power_address": f"https://10.0.0.{i}:8443",
                },
            )
            for i in range(3)
        ]
        admin = factory.make_admin()
        discovered_machines = [
            self.make_discovered_machine(project=project, location=vmhost.name)
            for vmhost in vmhosts
        ]
        for vmhost in vmhosts:
            vmhost.sync_machines(discovered_machines, admin)
        discovered_machines[0].location = vmhosts[2].name
        for vmhost in vmhosts:
            vmhost.sync_machines(discovered_machines, admin)
        new_bmc_ids = [vm.bmc_id for vm in cluster.virtual_machines()]
        self.assertNotIn(vmhosts[0].id, new_bmc_ids)
        vm = VirtualMachine.objects.get(
            identifier=discovered_machines[0].hostname
        )
        intended_bmc = Pod.objects.get(
            name=discovered_machines[0].location,
            power_parameters__project=project,
        )
        self.assertEqual(vm.bmc_id, intended_bmc.id)


class TestPodHints(MAASServerTestCase, PodTestMixin):
    def test_sync_hints_doesnt_save_empty_hints(self):
        cluster = factory.make_VMCluster(pods=0)
        discovered = self.make_discovered_pod()
        pod1 = Pod(
            power_type="lxd",
            power_parameters={"project": factory.make_name("project")},
        )
        pod1.save()
        mock_hint_save = self.patch(PodHints, "save")
        pod1.sync_hints(discovered.hints, cluster=cluster)
        mock_hint_save.assert_called()
        mock_hint_save.reset_mock()
        blank = DiscoveredPodHints()
        pod1.sync_hints(blank)
        mock_hint_save.assert_not_called()

    def test_sync_hints_doesnt_save_same_hints(self):
        cluster = factory.make_VMCluster(pods=0)
        discovered = self.make_discovered_pod()
        pod1 = Pod(
            power_type="lxd",
            power_parameters={"project": factory.make_name("project")},
        )
        pod1.save()
        mock_hint_save = self.patch(PodHints, "save")
        pod1.sync_hints(discovered.hints, cluster=cluster)
        mock_hint_save.assert_called()
        mock_hint_save.reset_mock()
        pod1.sync_hints(discovered.hints)
        mock_hint_save.assert_not_called()


class TestPodDelete(MAASTransactionServerTestCase, PodTestMixin):
    def test_delete_is_not_allowed(self):
        pod = factory.make_Pod()
        self.assertRaises(AttributeError, pod.delete)

    @wait_for_reactor
    @inlineCallbacks
    def test_delete_async_simply_deletes_empty_pod(self):
        pod = yield deferToDatabase(factory.make_Pod)
        yield pod.async_delete()
        pod = yield deferToDatabase(reload_object, pod)
        self.assertIsNone(pod)

    @wait_for_reactor
    @inlineCallbacks
    def test_delete_async_deletes_empty_pod_with_shared_bmc_on_rack(self):
        pod = yield deferToDatabase(factory.make_Pod)
        bmc = pod.as_bmc()
        rack = yield deferToDatabase(factory.make_RackController, bmc=bmc)
        self.assertIsNotNone(rack)
        yield pod.async_delete()
        pod = yield deferToDatabase(reload_object, pod)
        rack = yield deferToDatabase(reload_object, rack)
        self.assertIsNone(pod)
        self.assertIsNotNone(rack)

    @wait_for_reactor
    @inlineCallbacks
    def test_deletes_machines_and_pod_no_decompose(self):
        pod = yield deferToDatabase(factory.make_Pod)
        machine = yield deferToDatabase(factory.make_Machine, bmc=pod)
        client = Mock()
        self.patch(
            bmc_module, "getClientFromIdentifiers"
        ).return_value = client
        yield pod.async_delete()
        client.assert_not_called()
        machine = yield deferToDatabase(reload_object, machine)
        pod = yield deferToDatabase(reload_object, pod)
        self.assertIsNone(machine)
        self.assertIsNone(pod)

    @wait_for_reactor
    @inlineCallbacks
    def test_decomposes_and_deletes_machines_and_pod(self):
        pod = yield deferToDatabase(factory.make_Pod)
        machine1 = yield deferToDatabase(factory.make_Machine, bmc=pod)
        machine2 = yield deferToDatabase(factory.make_Machine, bmc=pod)
        client = Mock()
        client.side_effect = lambda *args, **kwargs: succeed({"hints": None})
        self.patch(
            bmc_module, "getClientFromIdentifiers"
        ).return_value = client
        yield pod.async_delete(decompose=True)

        power_parameters = yield deferToDatabase(pod.get_power_parameters)
        client.assert_has_calls(
            [
                call(
                    DecomposeMachine,
                    type=pod.power_type,
                    context=power_parameters,
                    pod_id=pod.id,
                    name=pod.name,
                ),
                call(
                    DecomposeMachine,
                    type=pod.power_type,
                    context=power_parameters,
                    pod_id=pod.id,
                    name=pod.name,
                ),
            ]
        )
        machine1 = yield deferToDatabase(reload_object, machine1)
        machine2 = yield deferToDatabase(reload_object, machine2)
        pod = yield deferToDatabase(reload_object, pod)
        self.assertIsNone(machine1)
        self.assertIsNone(machine2)
        self.assertIsNone(pod)

    @wait_for_reactor
    async def test_deletes_dynamically_created_machine(self):
        discovered = self.make_discovered_pod(
            mac_addresses=[factory.make_mac_address()]
        )
        # Create a subset of the discovered pod's tags
        # to make sure no duplicates are added on sync.
        pod = await deferToDatabase(factory.make_Pod)
        admin = await deferToDatabase(factory.make_admin)
        self.patch(pod, "sync_machines")
        await deferToDatabase(pod.sync, discovered, admin)
        dynamically_created_system_id = await deferToDatabase(
            lambda: pod.hints.nodes.first().system_id
        )
        await pod.async_delete(decompose=True)
        pod_node_count = await deferToDatabase(
            lambda: Node.objects.filter(
                system_id=dynamically_created_system_id
            ).count()
        )
        self.assertEqual(0, pod_node_count)

    @wait_for_reactor
    async def test_doesnt_delete_dynamically_created_machine_if_modified(self):
        discovered = self.make_discovered_pod(
            mac_addresses=[factory.make_mac_address()]
        )
        # Create a subset of the discovered pod's tags
        # to make sure no duplicates are added on sync.
        pod = await deferToDatabase(factory.make_Pod)
        admin = await deferToDatabase(factory.make_admin)
        self.patch(pod, "sync_machines")
        await deferToDatabase(pod.sync, discovered, admin)
        dynamically_created_system_id = await deferToDatabase(
            lambda: pod.hints.nodes.first().system_id
        )
        await deferToDatabase(
            lambda: Node.objects.filter(
                system_id=dynamically_created_system_id
            ).update(bmc=factory.make_BMC())
        )
        await pod.async_delete(decompose=True)
        pod_node_count = await deferToDatabase(
            lambda: Node.objects.filter(
                system_id=dynamically_created_system_id
            ).count()
        )
        self.assertEqual(1, pod_node_count)

    @wait_for_reactor
    async def test_doesnt_delete_non_dynamically_created_machine(self):
        machine = await deferToDatabase(
            lambda: factory.make_Machine_with_Interface_on_Subnet()
        )
        machine_mac = await deferToDatabase(
            lambda: str(
                machine.current_config.interface_set.first().mac_address
            )
        )
        discovered = self.make_discovered_pod(mac_addresses=[machine_mac])
        # Create a subset of the discovered pod's tags
        # to make sure no duplicates are added on sync.
        pod = await deferToDatabase(factory.make_Pod)
        admin = await deferToDatabase(factory.make_admin)
        self.patch(pod, "sync_machines")
        await deferToDatabase(pod.sync, discovered, admin)
        await pod.async_delete(decompose=True)
        pod_node_count = await deferToDatabase(
            lambda: Node.objects.filter(
                system_id=machine.system_id,
            ).count()
        )
        self.assertEqual(1, pod_node_count)

    @wait_for_reactor
    async def test_dont_deletes_dynamically_created_controllers(self):
        controller = await deferToDatabase(lambda: factory.make_Controller())
        controller_mac = await deferToDatabase(
            lambda: str(
                controller.current_config.interface_set.first().mac_address
            )
        )
        self.assertTrue(controller.should_be_dynamically_deleted())
        discovered = self.make_discovered_pod(mac_addresses=[controller_mac])
        pod = await deferToDatabase(factory.make_Pod)
        admin = await deferToDatabase(factory.make_admin)
        self.patch(pod, "sync_machines")
        await deferToDatabase(pod.sync, discovered, admin)
        await pod.async_delete(decompose=True)
        controller_count = await deferToDatabase(
            lambda: Controller.objects.filter(
                system_id=controller.system_id
            ).count()
        )
        self.assertEqual(1, controller_count)

    @wait_for_reactor
    @inlineCallbacks
    def test_decomposes_handles_failure_after_one_successful(self):
        pod = yield deferToDatabase(
            factory.make_Pod,
            pod_type="lxd",
            parameters={"project": factory.make_string()},
        )
        decomposable_machine_one = yield deferToDatabase(
            factory.make_Machine,
            bmc=pod,
        )
        decomposable_machine_two = yield deferToDatabase(
            factory.make_Machine,
            bmc=pod,
        )
        delete_machine = yield deferToDatabase(factory.make_Machine, bmc=pod)
        client = Mock()
        client.side_effect = [
            succeed({"hints": sentinel.hints}),
            fail(PodProblem()),
        ]
        self.patch(
            bmc_module, "getClientFromIdentifiers"
        ).return_value = client
        yield pod.async_delete(decompose=True)
        # All the machines should have been deleted.
        decomposable_machine_one = yield deferToDatabase(
            reload_object, decomposable_machine_one
        )
        decomposable_machine_two = yield deferToDatabase(
            reload_object, decomposable_machine_two
        )
        delete_machine = yield deferToDatabase(reload_object, delete_machine)
        pod = yield deferToDatabase(reload_object, pod)
        self.assertIsNone(decomposable_machine_one)
        self.assertIsNone(decomposable_machine_two)
        self.assertIsNone(delete_machine)
        self.assertIsNone(pod)

    @wait_for_reactor
    @inlineCallbacks
    def test_delete_and_wait_with_decompose(self):
        pod = yield deferToDatabase(factory.make_Pod)
        yield deferToDatabase(factory.make_Machine, bmc=pod)
        yield deferToDatabase(factory.make_Machine, bmc=pod)
        mock_result = Mock()
        mock_async_delete = self.patch(pod, "async_delete")
        mock_async_delete.return_value = mock_result
        yield deferToDatabase(pod.delete_and_wait, decompose=True)
        mock_async_delete.assert_called_with(decompose=True)
        mock_result.wait.assert_called_with(180)

    @wait_for_reactor
    @inlineCallbacks
    def test_delete_and_wait_no_decompose(self):
        pod = yield deferToDatabase(factory.make_Pod)
        yield deferToDatabase(factory.make_Machine, bmc=pod)
        yield deferToDatabase(factory.make_Machine, bmc=pod)
        mock_result = Mock()
        mock_async_delete = self.patch(pod, "async_delete")
        mock_async_delete.return_value = mock_result
        yield deferToDatabase(pod.delete_and_wait)
        mock_async_delete.assert_called_with(decompose=False)
        mock_result.wait.assert_called_with(60)

    @wait_for_reactor
    @inlineCallbacks
    def test_delete_clustered_pod_deletes_cluster(self):
        cluster = yield deferToDatabase(factory.make_VMCluster, pods=0)
        pod_defers = yield DeferredList(
            [
                deferToDatabase(factory.make_Pod, cluster=cluster)
                for _ in range(3)
            ]
        )
        pods = [pod[1] for pod in pod_defers]
        yield pods[0].async_delete()
        try:
            yield deferToDatabase(VMCluster.objects.get, id=cluster.id)
        except Exception as e:
            self.assertIsInstance(e, ObjectDoesNotExist)

    @wait_for_reactor
    @inlineCallbacks
    def test_delete_clustered_pod_deletes_peers(self):
        cluster = yield deferToDatabase(factory.make_VMCluster, pods=0)
        pod_defers = yield DeferredList(
            [
                deferToDatabase(factory.make_Pod, cluster=cluster)
                for _ in range(3)
            ]
        )
        pods = [pod[1] for pod in pod_defers]
        pod_ids = [pod.id for pod in pods]
        yield pods[0].async_delete()
        not_found_pods = yield deferToDatabase(
            Pod.objects.filter, id__in=pod_ids
        )
        list_not_found_pods = yield deferToDatabase(list, not_found_pods)
        self.assertEqual(list_not_found_pods, [])

    @wait_for_reactor
    @inlineCallbacks
    def test_delete_deletes_pod_secrets(self):
        pod = yield deferToDatabase(factory.make_Pod)
        secret_manager = SecretManager()
        yield deferToDatabase(
            secret_manager.set_composite_secret,
            "power-parameters",
            {"foo": "bar"},
            pod.as_bmc(),
        )
        yield pod.async_delete()

        secret = yield deferToDatabase(
            secret_manager.get_composite_secret,
            "power-parameters",
            pod.as_bmc(),
            None,
        )

        self.assertIsNone(secret)


class TestPodDefaultMACVlanMode(MAASServerTestCase):
    def test_allows_default_macvlan_mode(self):
        pod = factory.make_Pod()
        default_macvlan_mode = random.choice(
            ["bridge", "private", "vepa", "passthru"]
        )
        pod.default_macvlan_mode = default_macvlan_mode
        pod.save()
        self.assertEqual(default_macvlan_mode, pod.default_macvlan_mode)

    def test_default_default_macvlan_mode_is_None(self):
        pod = factory.make_Pod()
        self.assertIsNone(pod.default_macvlan_mode)


class TestGetRequestedIPs(MAASServerTestCase):
    def test_returns_empty_dict_if_no_requested_machine(self):
        self.assertEqual({}, get_requested_ips(None))

    def test_returns_empty_dict_if_no_interfaces_are_named(self):
        interface = RequestedMachineInterface()
        interface2 = RequestedMachineInterface()
        interfaces = [interface, interface2]
        requested_machine = RequestedMachine(
            factory.make_hostname(), "amd64", 1, 1024, [], interfaces
        )
        self.assertEqual({}, get_requested_ips(requested_machine))

    def test_returns_ifname_to_ip_list_dict_if_specified(self):
        interface = RequestedMachineInterface(
            ifname="eth0", requested_ips=["10.0.0.1", "2001:db8::1"]
        )
        interface2 = RequestedMachineInterface(
            ifname="eth1", requested_ips=["10.0.0.2", "2001:db8::2"]
        )
        interfaces = [interface, interface2]
        requested_machine = RequestedMachine(
            factory.make_hostname(), "amd64", 1, 1024, [], interfaces
        )
        self.assertEqual(
            get_requested_ips(requested_machine),
            {
                "eth0": ["10.0.0.1", "2001:db8::1"],
                "eth1": ["10.0.0.2", "2001:db8::2"],
            },
        )

    def test_leaves_out_keys_with_no_assigned_ips(self):
        interface = RequestedMachineInterface(
            ifname="eth0", requested_ips=["10.0.0.1", "2001:db8::1"]
        )
        interface2 = RequestedMachineInterface(ifname="eth1", requested_ips=[])
        interfaces = [interface, interface2]
        requested_machine = RequestedMachine(
            factory.make_hostname(), "amd64", 1, 1024, [], interfaces
        )
        self.assertEqual(
            {"eth0": ["10.0.0.1", "2001:db8::1"]},
            get_requested_ips(requested_machine),
        )
