# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver models."""

__all__ = []

import random
from unittest.mock import Mock

from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
)
from maasserver.models import bmc as bmc_module
from maasserver.models.bmc import (
    BMC,
    BMCRoutableRackControllerRelationship,
)
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maastesting.matchers import MockCalledOnceWith
from testtools.matchers import HasLength


class TestBMC(MAASServerTestCase):

    @staticmethod
    def get_machine_ip_address(machine):
        return machine.interface_set.all()[0].ip_addresses.all()[0]

    def make_machine_and_bmc_with_shared_ip(self):
        machine = factory.make_Node(interface=False)
        machine.interface_set = []
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=machine)
        machine_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet,
            interface=interface)
        self.assertEqual(1, machine.interface_set.count())

        bmc = factory.make_BMC(
            power_type="virsh",
            power_parameters={
                'power_address':
                "protocol://%s:8080/path/to/thing#tag" % (
                    factory.ip_to_url_format(machine_ip.ip))})
        # Make sure they're sharing an IP.
        machine = reload_object(machine)
        machine_ip_addr = TestBMC.get_machine_ip_address(machine)
        self.assertEqual(machine_ip_addr.id, bmc.ip_address.id)
        return machine, bmc, machine_ip

    def make_machine_and_bmc_differing_ips(self):
        machine = factory.make_Node(interface=False)
        machine.interface_set = []
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=machine)
        machine_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet,
            interface=interface)
        self.assertEqual(1, machine.interface_set.count())

        ip_address = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet)
        bmc_ip = ip_address.ip
        ip_address.delete()
        bmc = factory.make_BMC(
            power_type="virsh",
            power_parameters={
                'power_address':
                "protocol://%s:8080/path/to/thing#tag" % (
                    factory.ip_to_url_format(bmc_ip))})
        # Make sure they're not sharing an IP.
        machine = reload_object(machine)
        machine_ip_addr = TestBMC.get_machine_ip_address(machine)
        self.assertNotEqual(machine_ip_addr.id, bmc.ip_address.id)
        return machine, bmc, machine_ip

    def test_bmc_save_extracts_ip_address(self):
        subnet = factory.make_Subnet()
        sticky_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet)
        power_parameters = {
            'power_address':
            "protocol://%s:8080/path/to/thing#tag" % (
                factory.ip_to_url_format(sticky_ip.ip)),
        }
        bmc = factory.make_BMC(
            power_type="virsh", power_parameters=power_parameters)
        self.assertEqual(sticky_ip.ip, bmc.ip_address.ip)
        self.assertEqual(subnet, bmc.ip_address.subnet)

    def test_bmc_changing_power_parameters_changes_ip(self):
        ip = factory.make_ipv4_address()
        power_parameters = {
            'power_address':
            "protocol://%s:8080/path#tag" % factory.ip_to_url_format(ip),
        }
        bmc = factory.make_BMC(
            power_type="virsh", power_parameters=power_parameters)
        self.assertEqual(ip, bmc.ip_address.ip)
        self.assertIsNone(bmc.ip_address.subnet)

        subnet = factory.make_Subnet()
        sticky_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet)
        bmc.power_parameters = {
            'power_address':
            "protocol://%s:8080/path/to/thing#tag" % (
                factory.ip_to_url_format(sticky_ip.ip)),
        }
        bmc.save()
        self.assertEqual(sticky_ip.ip, bmc.ip_address.ip)
        self.assertEqual(subnet, bmc.ip_address.subnet)

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
        machine_ip_addr = TestBMC.get_machine_ip_address(machine)
        self.assertEqual(old_ip, machine_ip_addr.ip)
        self.assertEqual(machine_ip.id, machine_ip_addr.id)

    def test_changing_machine_ip_when_shared_with_bmc_keeps_both(self):
        machine, bmc, machine_ip = self.make_machine_and_bmc_with_shared_ip()

        # Now change the Machine's IP to a new address on same subnet.
        old_ip = machine_ip.ip
        new_ip_address = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=machine_ip.subnet)
        new_ip = new_ip_address.ip
        # Remove IP so we can set machine_ip to its address.
        new_ip_address.delete()
        self.assertNotEqual(new_ip, old_ip)
        machine_ip.ip = new_ip
        machine_ip.save()

        # Check Machine has new IP address but kept same instance: machine_ip.
        machine = reload_object(machine)
        machine_ip_addr = TestBMC.get_machine_ip_address(machine)
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
            alloc_type=IPADDRESS_TYPE.STICKY, subnet=machine_ip.subnet)
        new_ip = new_ip_address.ip
        # Remove IP so we can set machine_ip to its address.
        new_ip_address.delete()
        self.assertNotEqual(new_ip, old_ip)

        bmc.power_parameters = {
            'power_address':
            "protocol://%s:8080/path/to/thing#tag" % (
                factory.ip_to_url_format(new_ip))}
        bmc.save()

        # Check Machine has old IP address and kept same instance: machine_ip.
        machine = reload_object(machine)
        machine_ip_addr = TestBMC.get_machine_ip_address(machine)
        self.assertEqual(old_ip, machine_ip_addr.ip)
        self.assertEqual(machine_ip.id, machine_ip_addr.id)

        # Check BMC has new IP.
        bmc = reload_object(bmc)
        self.assertEqual(new_ip, bmc.ip_address.ip)

        # Make sure DB ID's of StaticIPAddress instances differ.
        self.assertNotEqual(machine_ip_addr.id, bmc.ip_address.id)

    def test_merging_machine_into_bmc_ip(self):
        machine, bmc, _ = self.make_machine_and_bmc_differing_ips()

        # Now change the machine's address to match bmc's.
        machine_ip_addr = TestBMC.get_machine_ip_address(machine)
        machine_ip_addr.ip = bmc.ip_address.ip
        machine_ip_addr.save()

        # Make sure BMC and Machine now using same StaticIPAddress instance.
        machine = reload_object(machine)
        machine_ip_addr = TestBMC.get_machine_ip_address(machine)
        self.assertEqual(machine_ip_addr.id, reload_object(bmc).ip_address.id)

    def test_merging_bmc_into_machine_ip(self):
        machine, bmc, machine_ip = self.make_machine_and_bmc_differing_ips()

        # Now change the BMC's address to match machine's.
        bmc.power_parameters = {
            'power_address':
            "protocol://%s:8080/path/to/thing#tag" % (
                factory.ip_to_url_format(machine_ip.ip))}
        bmc.save()

        # Make sure BMC and Machine are using same StaticIPAddress instance.
        machine = reload_object(machine)
        machine_ip_addr = TestBMC.get_machine_ip_address(machine)
        self.assertEqual(machine_ip_addr.id, bmc.ip_address.id)

    def test_delete_bmc_deletes_orphaned_ip_address(self):
        bmc = factory.make_BMC(
            power_type="virsh",
            power_parameters={
                'power_address':
                "protocol://%s:8080/path/to/thing#tag" % (
                    factory.make_ipv4_address())})
        ip = bmc.ip_address
        bmc.delete()
        self.assertEqual(0, StaticIPAddress.objects.filter(id=ip.id).count())

    def test_delete_bmc_spares_non_orphaned_ip_address(self):
        machine, bmc, machine_ip = self.make_machine_and_bmc_with_shared_ip()
        bmc.delete()
        self.assertEqual(
            1, StaticIPAddress.objects.filter(id=machine_ip.id).count())

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
        result = BMC.scope_power_parameters('vmware', parameters)
        self.assertEqual(bmc_parameters, result[0])
        self.assertEqual(node_parameters, result[1])

    def test_scope_power_parameters_unknown_parameter(self):
        bmc_parameters = dict(power_address=factory.make_string())
        node_parameters = dict(server_name=factory.make_string())
        # This random parameter should be stored on the node instance.
        node_parameters[factory.make_string()] = factory.make_string()
        parameters = {**bmc_parameters, **node_parameters}
        result = BMC.scope_power_parameters('hmc', parameters)
        self.assertEqual(bmc_parameters, result[0])
        self.assertEqual(node_parameters, result[1])

    def test_bmc_extract_ip_address_whole_value(self):
        power_parameters = {'power_address': "192.168.1.1"}
        self.assertEqual(
            "192.168.1.1", BMC.extract_ip_address("hmc", power_parameters))

    def test_bmc_extract_ip_address_empty_power_type_gives_none(self):
        power_parameters = {'power_address': "192.168.1.1"}
        self.assertEqual(
            None, BMC.extract_ip_address("", power_parameters))
        self.assertEqual(
            None, BMC.extract_ip_address(None, power_parameters))

    def test_bmc_extract_ip_address_blank_gives_none(self):
        self.assertEqual(None, BMC.extract_ip_address("hmc", None))
        self.assertEqual(None, BMC.extract_ip_address("hmc", {}))

        power_parameters = {'power_address': ""}
        self.assertEqual(None, BMC.extract_ip_address("hmc", power_parameters))

        power_parameters = {'power_address': None}
        self.assertEqual(None, BMC.extract_ip_address("hmc", power_parameters))

    def test_bmc_extract_ip_address_from_url(self):
        power_parameters = {
            'power_address': "protocol://somehost:8080/path/to/thing#tag",
        }
        self.assertEqual(
            "somehost", BMC.extract_ip_address("virsh", power_parameters))

    def test_bmc_extract_ip_address_from_url_blank_gives_none(self):
        self.assertEqual(None, BMC.extract_ip_address("virsh", None))
        self.assertEqual(None, BMC.extract_ip_address("virsh", {}))

        power_parameters = {'power_address': ""}
        self.assertEqual(
            None, BMC.extract_ip_address("virsh", power_parameters))

        power_parameters = {'power_address': None}
        self.assertEqual(
            None, BMC.extract_ip_address("virsh", power_parameters))

    def test_bmc_extract_ip_address_from_url_empty_host(self):
        power_parameters = {
            'power_address': "http://:8080/foo/#baz",
        }
        self.assertEqual(
            "", BMC.extract_ip_address("virsh", power_parameters))

    def test_get_usable_rack_controllers_returns_empty_when_none(self):
        bmc = factory.make_BMC()
        self.assertThat(bmc.get_usable_rack_controllers(), HasLength(0))

    def test_get_usable_rack_controllers_returns_routable_racks(self):
        bmc = factory.make_BMC()
        routable_racks = [
            factory.make_RackController()
            for _ in range(3)
        ]
        not_routable_racks = [
            factory.make_RackController()
            for _ in range(3)
        ]
        for rack in routable_racks:
            BMCRoutableRackControllerRelationship(
                bmc=bmc, rack_controller=rack, routable=True).save()
        for rack in not_routable_racks:
            BMCRoutableRackControllerRelationship(
                bmc=bmc, rack_controller=rack, routable=False).save()
        self.assertItemsEqual(
            routable_racks,
            bmc.get_usable_rack_controllers(with_connection=False))

    def test_get_usable_rack_controllers_returns_routable_racks_conn(self):
        bmc = factory.make_BMC()
        routable_racks = [
            factory.make_RackController()
            for _ in range(3)
        ]
        not_routable_racks = [
            factory.make_RackController()
            for _ in range(3)
        ]
        for rack in routable_racks:
            BMCRoutableRackControllerRelationship(
                bmc=bmc, rack_controller=rack, routable=True).save()
        for rack in not_routable_racks:
            BMCRoutableRackControllerRelationship(
                bmc=bmc, rack_controller=rack, routable=False).save()
        connected_rack = random.choice(routable_racks)
        client = Mock()
        client.ident = connected_rack.system_id
        self.patch(bmc_module, "getAllClients").return_value = [client]
        self.assertItemsEqual(
            [connected_rack],
            bmc.get_usable_rack_controllers(with_connection=True))

    def test_get_usable_rack_controllers_updates_subnet_on_sip(self):
        network = factory.make_ipv4_network()
        subnet = factory.make_Subnet(cidr=str(network.cidr))
        ip = factory.pick_ip_in_Subnet(subnet)
        sip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet)
        sip.subnet = None
        sip.save()
        bmc = factory.make_BMC(
            power_type="virsh",
            power_parameters={
                "power_address": "qemu+ssh://user@%s/system" % ip,
            }, ip_address=sip)
        bmc.get_usable_rack_controllers()
        self.assertEqual(subnet, reload_object(sip).subnet)

    def test_get_usable_rack_controllers_updates_handles_unknown_subnet(self):
        network = factory.make_ipv4_network()
        ip = factory.pick_ip_in_network(network)
        sip = StaticIPAddress.objects.create(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip)
        bmc = factory.make_BMC(
            power_type="virsh",
            power_parameters={
                "power_address": "qemu+ssh://user@%s/system" % ip,
            }, ip_address=sip)
        bmc.get_usable_rack_controllers()
        self.assertIsNone(reload_object(sip).subnet)

    def test_get_usable_rack_controllers_returns_rack_controllers(self):
        rack_controller = factory.make_RackController()
        machine = factory.make_Node(bmc_connected_to=rack_controller)
        self.assertItemsEqual(
            [rack_controller], machine.bmc.get_usable_rack_controllers(
                with_connection=False))

    def test_get_client_identifiers_returns_rack_controller_system_ids(self):
        rack_controllers = [
            factory.make_RackController()
            for _ in range(3)
        ]
        bmc = factory.make_BMC()
        self.patch(
            bmc, "get_usable_rack_controllers").return_value = rack_controllers
        expected_system_ids = [
            rack.system_id
            for rack in rack_controllers
        ]
        self.assertItemsEqual(
            expected_system_ids, bmc.get_client_identifiers())

    def test_is_accessible_calls_get_usable_rack_controllers(self):
        bmc = factory.make_BMC()
        mock_get_usable_rack_controllers = self.patch(
            bmc, "get_usable_rack_controllers")
        bmc.is_accessible()
        self.assertThat(
            mock_get_usable_rack_controllers,
            MockCalledOnceWith(with_connection=False))

    def test_is_accessible_returns_true(self):
        bmc = factory.make_BMC()
        mock_get_usable_rack_controllers = self.patch(
            bmc, "get_usable_rack_controllers")
        mock_get_usable_rack_controllers.return_value = [
            factory.make_RackController()]
        self.assertTrue(bmc.is_accessible())

    def test_is_accessible_returns_false(self):
        bmc = factory.make_BMC()
        mock_get_usable_rack_controllers = self.patch(
            bmc, "get_usable_rack_controllers")
        mock_get_usable_rack_controllers.return_value = []
        self.assertFalse(bmc.is_accessible())

    def test_update_routable_racks_updates_rack_relationship(self):
        node = factory.make_Node(power_type="virsh")

        # Create old relationships that should be removed.
        old_relationship_ids = [
            BMCRoutableRackControllerRelationship.objects.create(
                bmc=node.bmc, rack_controller=factory.make_RackController(),
                routable=True).id
            for _ in range(3)
        ]

        routable_racks = [
            factory.make_RackController()
            for _ in range(3)
        ]
        non_routable_racks = [
            factory.make_RackController()
            for _ in range(3)
        ]

        node.bmc.update_routable_racks([
            rack.system_id
            for rack in routable_racks
        ], [
            rack.system_id
            for rack in non_routable_racks
        ])

        self.assertThat(
            BMCRoutableRackControllerRelationship.objects.filter(
                id__in=old_relationship_ids), HasLength(0))
        self.assertThat(
            BMCRoutableRackControllerRelationship.objects.filter(
                rack_controller__in=routable_racks, routable=True),
            HasLength(len(routable_racks)))
        self.assertThat(
            BMCRoutableRackControllerRelationship.objects.filter(
                rack_controller__in=non_routable_racks, routable=False),
            HasLength(len(non_routable_racks)))
