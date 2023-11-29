# Copyright 2016-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import http.client

from django.urls import reverse
from django.utils.http import urlencode

from maasserver.enum import NODE_TYPE
from maasserver.models.bmc import Pod
from maasserver.testing.api import APITestCase, explain_unexpected_response
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object


class TestRegionControllerAPI(APITestCase.ForUser):
    """Tests for /api/2.0/regioncontrollers/<region>/."""

    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/regioncontrollers/region-name/",
            reverse("regioncontroller_handler", args=["region-name"]),
        )

    @staticmethod
    def get_region_uri(region):
        """Get the API URI for `region`."""
        return reverse("regioncontroller_handler", args=[region.system_id])

    def test_PUT_updates_region_controller(self):
        self.become_admin()
        region = factory.make_RegionController()
        zone = factory.make_zone()
        new_description = factory.make_name("description")
        response = self.client.put(
            self.get_region_uri(region),
            {"description": new_description, "zone": zone.name},
        )
        self.assertEqual(http.client.OK, response.status_code)
        region = reload_object(region)
        self.assertEqual(zone.name, region.zone.name)
        self.assertEqual(new_description, region.description)

    def test_PUT_requires_admin(self):
        region = factory.make_RegionController()
        response = self.client.put(self.get_region_uri(region), {})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_DELETE_delete_with_force(self):
        self.become_admin()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        region = factory.make_Node_with_Interface_on_Subnet(
            node_type=NODE_TYPE.REGION_CONTROLLER, subnet=subnet, vlan=vlan
        )
        ip = factory.make_StaticIPAddress(
            interface=region.current_config.interface_set.first()
        )
        factory.make_Pod(ip_address=ip)
        mock_async_delete = self.patch(Pod, "async_delete")
        response = self.client.delete(
            self.get_region_uri(region),
            QUERY_STRING=urlencode({"force": "true"}, doseq=True),
        )
        self.assertEqual(
            http.client.NO_CONTENT,
            response.status_code,
            explain_unexpected_response(http.client.NO_CONTENT, response),
        )
        mock_async_delete.assert_called_once_with()

    def test_DELETE_force_not_required_for_pod_region_rack(self):
        self.become_admin()
        vlan = factory.make_VLAN()
        factory.make_Subnet(vlan=vlan)
        rack = factory.make_RegionRackController(vlan=vlan)
        ip = factory.make_StaticIPAddress(
            interface=rack.current_config.interface_set.first()
        )
        factory.make_Pod(ip_address=ip)
        mock_async_delete = self.patch(Pod, "async_delete")
        response = self.client.delete(
            self.get_region_uri(rack),
            QUERY_STRING=urlencode({"force": "true"}, doseq=True),
        )
        self.assertEqual(
            http.client.NO_CONTENT,
            response.status_code,
            explain_unexpected_response(http.client.NO_CONTENT, response),
        )
        mock_async_delete.assert_not_called()

    def test_pod_DELETE_delete_without_force(self):
        self.become_admin()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        region = factory.make_Node_with_Interface_on_Subnet(
            node_type=NODE_TYPE.REGION_CONTROLLER, subnet=subnet, vlan=vlan
        )
        ip = factory.make_StaticIPAddress(
            interface=region.current_config.interface_set.first()
        )
        factory.make_Pod(ip_address=ip)
        mock_async_delete = self.patch(Pod, "async_delete")
        response = self.client.delete(self.get_region_uri(region))
        self.assertEqual(
            http.client.BAD_REQUEST,
            response.status_code,
            explain_unexpected_response(http.client.BAD_REQUEST, response),
        )
        mock_async_delete.assert_not_called()


class TestRegionControllersAPI(APITestCase.ForUser):
    """Tests for /api/2.0/regioncontrollers/."""

    @staticmethod
    def get_region_uri():
        """Get the API URI for `region`."""
        return reverse("regioncontrollers_handler")

    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/regioncontrollers/",
            reverse("regioncontrollers_handler"),
        )

    def test_read_returns_limited_fields(self):
        self.become_admin()
        factory.make_RegionController()
        response = self.client.get(reverse("regioncontrollers_handler"))
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            {
                "system_id",
                "hostname",
                "description",
                "hardware_uuid",
                "domain",
                "fqdn",
                "architecture",
                "cpu_count",
                "cpu_speed",
                "memory",
                "swap_size",
                "osystem",
                "power_state",
                "power_type",
                "resource_uri",
                "distro_series",
                "interface_set",
                "ip_addresses",
                "zone",
                "status_action",
                "node_type",
                "node_type_name",
                "current_commissioning_result_id",
                "current_testing_result_id",
                "current_installation_result_id",
                "version",
                "commissioning_status",
                "commissioning_status_name",
                "testing_status",
                "testing_status_name",
                "cpu_test_status",
                "cpu_test_status_name",
                "memory_test_status",
                "memory_test_status_name",
                "network_test_status",
                "network_test_status_name",
                "storage_test_status",
                "storage_test_status_name",
                "other_test_status",
                "other_test_status_name",
                "hardware_info",
                "tag_names",
                "interface_test_status",
                "interface_test_status_name",
            },
            parsed_result[0].keys(),
        )
