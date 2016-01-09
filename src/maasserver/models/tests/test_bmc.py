# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver models."""

__all__ = []

from maasserver.models.bmc import BMC
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase


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
