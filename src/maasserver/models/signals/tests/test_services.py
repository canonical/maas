# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for updating services."""


from unittest.mock import call

from maasserver.models import RackController, RegionRackRPCConnection, Service
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith, MockCallsMatch


class TestRegionRackRPCConnection(MAASServerTestCase):
    def test_calls_create_services_for_on_create(self):
        endpoint = factory.make_RegionControllerProcessEndpoint()
        rack_controller = factory.make_RackController()
        mock_create_for = self.patch(Service.objects, "create_services_for")
        RegionRackRPCConnection.objects.create(
            endpoint=endpoint, rack_controller=rack_controller
        )
        self.assertThat(mock_create_for, MockCalledOnceWith(rack_controller))

    def test_calls_update_rackd_status_on_create(self):
        endpoint = factory.make_RegionControllerProcessEndpoint()
        rack_controller = factory.make_RackController()
        mock_update_rackd_status = self.patch(
            rack_controller, "update_rackd_status"
        )
        RegionRackRPCConnection.objects.create(
            endpoint=endpoint, rack_controller=rack_controller
        )
        self.assertThat(mock_update_rackd_status, MockCalledOnceWith())

    def test_calls_create_services_for_on_update(self):
        endpoint = factory.make_RegionControllerProcessEndpoint()
        rack_controller = factory.make_RackController()
        mock_create_for = self.patch(Service.objects, "create_services_for")
        connection = RegionRackRPCConnection.objects.create(
            endpoint=endpoint, rack_controller=rack_controller
        )
        connection.save()
        self.assertThat(mock_create_for, MockCalledOnceWith(rack_controller))

    def test_calls_update_rackd_status_on_update(self):
        endpoint = factory.make_RegionControllerProcessEndpoint()
        rack_controller = factory.make_RackController()
        mock_update_rackd_status = self.patch(
            rack_controller, "update_rackd_status"
        )
        connection = RegionRackRPCConnection.objects.create(
            endpoint=endpoint, rack_controller=rack_controller
        )
        connection.save()
        self.assertThat(mock_update_rackd_status, MockCalledOnceWith())

    def test_calls_create_services_for_on_delete(self):
        endpoint = factory.make_RegionControllerProcessEndpoint()
        rack_controller = factory.make_RackController()
        mock_create_for = self.patch(Service.objects, "create_services_for")
        connection = RegionRackRPCConnection.objects.create(
            endpoint=endpoint, rack_controller=rack_controller
        )
        connection.delete()
        self.assertThat(
            mock_create_for,
            MockCallsMatch(call(rack_controller), call(rack_controller)),
        )

    def test_calls_update_rackd_status_on_delete(self):
        endpoint = factory.make_RegionControllerProcessEndpoint()
        rack_controller = factory.make_RackController()
        mock_update_rackd_status = self.patch(
            rack_controller, "update_rackd_status"
        )
        connection = RegionRackRPCConnection.objects.create(
            endpoint=endpoint, rack_controller=rack_controller
        )
        connection.delete()
        self.assertThat(
            mock_update_rackd_status, MockCallsMatch(call(), call())
        )


class TestRegionControllerProcess(MAASServerTestCase):
    def test_calls_create_services_for_on_all_racks_on_create(self):
        rack_controllers = [factory.make_RackController() for _ in range(3)]
        mock_create_for = self.patch(Service.objects, "create_services_for")
        factory.make_RegionControllerProcess()
        self.assertEquals(
            len(rack_controllers) + 1, mock_create_for.call_count
        )

    def test_calls_update_rackd_status_on_all_racks_on_create(self):
        rack_controllers = [factory.make_RackController() for _ in range(3)]
        mock_update_rackd_status = self.patch(
            RackController, "update_rackd_status"
        )
        factory.make_RegionControllerProcess()
        self.assertEquals(
            len(rack_controllers), mock_update_rackd_status.call_count
        )

    def test_calls_create_services_for_on_all_racks_on_delete(self):
        rack_controllers = [factory.make_RackController() for _ in range(3)]
        process = factory.make_RegionControllerProcess()
        mock_create_for = self.patch(Service.objects, "create_services_for")
        process.delete()
        self.assertEquals(len(rack_controllers), mock_create_for.call_count)

    def test_calls_update_rackd_status_on_all_racks_on_delete(self):
        rack_controllers = [factory.make_RackController() for _ in range(3)]
        process = factory.make_RegionControllerProcess()
        mock_update_rackd_status = self.patch(
            RackController, "update_rackd_status"
        )
        process.delete()
        self.assertEquals(
            len(rack_controllers), mock_update_rackd_status.call_count
        )
