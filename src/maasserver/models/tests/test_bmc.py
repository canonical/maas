# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver models."""

__all__ = []

from maasserver.models.bmc import BMC
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
