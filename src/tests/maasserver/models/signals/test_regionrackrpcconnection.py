# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the behaviour of RegionRackRPCConnection signals."""

from maasserver.models import DNSPublication
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestPostSaveRegionRackRPCConnectionSignal(MAASServerTestCase):
    def test_save_region_rack_rpc_connection_creates_dnspublication(self):
        factory.make_RegionRackRPCConnection()
        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertIn("connected", dnspublication.source)

    def test_save_region_rack_rpc_connection_does_not_create_dnspublication_after_first_connection(
        self,
    ):
        rack_controller = factory.make_RackController()
        endpoint = factory.make_RegionControllerProcessEndpoint()
        endpoint2 = factory.make_RegionControllerProcessEndpoint()
        factory.make_RegionRackRPCConnection(
            rack_controller=rack_controller, endpoint=endpoint
        )
        dnspublication = DNSPublication.objects.get_most_recent()
        factory.make_RegionRackRPCConnection(
            rack_controller=rack_controller, endpoint=endpoint2
        )
        self.assertEqual(
            dnspublication, DNSPublication.objects.get_most_recent()
        )


class TestPostRegionRackRPCConnectionSubnetSignal(MAASServerTestCase):
    def test_delete_rack_rpc_connection_creates_dnspublication(self):
        connection = factory.make_RegionRackRPCConnection()
        connection.delete()
        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertIn("disconnected", dnspublication.source)

    def test_delete_rack_rpc_connection_does_not_create_dnspublication_when_still_connected(
        self,
    ):
        rack_controller = factory.make_RackController()
        factory.make_RegionRackRPCConnection(rack_controller=rack_controller)
        connection = factory.make_RegionRackRPCConnection(
            rack_controller=rack_controller
        )
        connection.delete()
        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertNotIn("disconnected", dnspublication.source)
