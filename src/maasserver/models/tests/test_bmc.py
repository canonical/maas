# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver models."""

__all__ = []

from maasserver.enum import IPADDRESS_TYPE
from maasserver.models.bmc import BMC
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestBMC(MAASServerTestCase):

    def test_delete_bmc_deletes_related_ip_address(self):
        ip = factory.make_StaticIPAddress()
        bmc = factory.make_BMC(ip_address=ip)
        bmc.delete()
        self.assertIsNone(reload_object(ip))

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

    def test_get_usable_rack_controllers_returns_empty_when_no_ip(self):
        bmc = factory.make_BMC()
        self.assertEquals(set(), bmc.get_usable_rack_controllers())

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
