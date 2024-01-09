# Copyright 2016-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import http.client

from django.urls import reverse
from django.utils.http import urlencode

from maasserver.api import rackcontrollers
from maasserver.models.bmc import Pod
from maasserver.testing.api import (
    APITestCase,
    APITransactionTestCase,
    explain_unexpected_response,
)
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object


class TestRackControllerAPI(APITransactionTestCase.ForUser):
    """Tests for /api/2.0/rackcontrollers/<rack>/."""

    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/rackcontrollers/rack-name/",
            reverse("rackcontroller_handler", args=["rack-name"]),
        )

    @staticmethod
    def get_rack_uri(rack):
        """Get the API URI for `rack`."""
        return reverse("rackcontroller_handler", args=[rack.system_id])

    def test_PUT_updates_rack_controller(self):
        self.become_admin()
        rack = factory.make_RackController(owner=self.user)
        zone = factory.make_zone()
        new_description = factory.make_name("description")
        response = self.client.put(
            self.get_rack_uri(rack),
            {"description": new_description, "zone": zone.name},
        )
        self.assertEqual(http.client.OK, response.status_code)
        rack = reload_object(rack)
        self.assertEqual(zone.name, rack.zone.name)
        self.assertEqual(new_description, rack.description)

    def test_PUT_requires_admin(self):
        rack = factory.make_RackController(owner=self.user)
        response = self.client.put(self.get_rack_uri(rack), {})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_POST_import_boot_images_import_to_rack_controllers(self):
        self.become_admin()
        rack = factory.make_RackController(owner=factory.make_User())
        response = self.client.post(
            self.get_rack_uri(rack), {"op": "import_boot_images"}
        )
        self.assertEqual(
            http.client.ACCEPTED,
            response.status_code,
            explain_unexpected_response(http.client.ACCEPTED, response),
        )

    def test_POST_import_boot_images_denied_if_not_admin(self):
        rack = factory.make_RackController(owner=factory.make_User())
        response = self.client.post(
            self.get_rack_uri(rack), {"op": "import_boot_images"}
        )
        self.assertEqual(
            http.client.FORBIDDEN,
            response.status_code,
            explain_unexpected_response(http.client.FORBIDDEN, response),
        )

    def test_GET_list_boot_images(self):
        factory.make_RegionController()
        rack = factory.make_RackController(owner=factory.make_User())
        resource = factory.make_usable_boot_resource(
            architecture="amd64/hwe-16.04",
            extra={"subarches": "hwe-p,hwe-t,hwe-16.04,hwe-16.10"},
        )
        self.become_admin()
        response = self.client.get(
            self.get_rack_uri(rack), {"op": "list_boot_images"}
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            explain_unexpected_response(http.client.OK, response),
        )
        ret = json_load_bytes(response.content)
        self.assertEqual({"connected", "images", "status"}, ret.keys())
        image = ret["images"][0]
        self.assertCountEqual(image["name"], resource.name)
        self.assertCountEqual(
            image["subarches"], ["hwe-p", "hwe-t", "hwe-16.04", "hwe-16.10"]
        )

    def test_GET_list_boot_images_denied_if_not_admin(self):
        rack = factory.make_RackController(owner=factory.make_User())
        response = self.client.get(
            self.get_rack_uri(rack), {"op": "list_boot_images"}
        )
        self.assertEqual(
            http.client.FORBIDDEN,
            response.status_code,
            explain_unexpected_response(http.client.FORBIDDEN, response),
        )

    def test_DELETE_cannot_delete_if_primary_rack(self):
        self.become_admin()
        vlan = factory.make_VLAN()
        rack = factory.make_RackController(vlan=vlan)
        vlan.dhcp_on = True
        vlan.primary_rack = rack
        vlan.save()
        response = self.client.delete(self.get_rack_uri(rack))
        self.assertEqual(
            http.client.BAD_REQUEST,
            response.status_code,
            explain_unexpected_response(http.client.BAD_REQUEST, response),
        )

    def test_DELETE_delete_with_force(self):
        self.become_admin()
        vlan = factory.make_VLAN()
        factory.make_Subnet(vlan=vlan)
        rack = factory.make_RackController(vlan=vlan)
        ip = factory.make_StaticIPAddress(
            interface=rack.current_config.interface_set.first()
        )
        factory.make_Pod(ip_address=ip)
        vlan.dhcp_on = True
        vlan.primary_rack = rack
        vlan.save()
        mock_async_delete = self.patch(Pod, "async_delete")
        response = self.client.delete(
            self.get_rack_uri(rack),
            QUERY_STRING=urlencode({"force": "true"}, doseq=True),
        )
        self.assertEqual(
            http.client.NO_CONTENT,
            response.status_code,
            explain_unexpected_response(http.client.NO_CONTENT, response),
        )
        mock_async_delete.assert_called_once_with()

    def test_pod_DELETE_delete_without_force(self):
        self.become_admin()
        vlan = factory.make_VLAN()
        factory.make_Subnet(vlan=vlan)
        rack = factory.make_RackController(vlan=vlan)
        ip = factory.make_StaticIPAddress(
            interface=rack.current_config.interface_set.first()
        )
        factory.make_Pod(ip_address=ip)
        vlan.dhcp_on = True
        vlan.primary_rack = rack
        vlan.save()
        mock_async_delete = self.patch(Pod, "async_delete")
        response = self.client.delete(self.get_rack_uri(rack))
        self.assertEqual(
            http.client.BAD_REQUEST,
            response.status_code,
            explain_unexpected_response(http.client.BAD_REQUEST, response),
        )
        mock_async_delete.assert_not_called()

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
            self.get_rack_uri(rack),
            QUERY_STRING=urlencode({"force": "true"}, doseq=True),
        )
        self.assertEqual(
            http.client.NO_CONTENT,
            response.status_code,
            explain_unexpected_response(http.client.NO_CONTENT, response),
        )
        mock_async_delete.assert_not_called()


class TestRackControllersAPI(APITestCase.ForUser):
    """Tests for /api/2.0/rackcontrollers/."""

    @staticmethod
    def get_rack_uri():
        """Get the API URI for `rack`."""
        return reverse("rackcontrollers_handler")

    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/rackcontrollers/",
            reverse("rackcontrollers_handler"),
        )

    def test_read_returns_limited_fields(self):
        self.become_admin()
        factory.make_RackController(owner=self.user)
        response = self.client.get(reverse("rackcontrollers_handler"))
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
                "service_set",
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

    def test_POST_import_boot_images_import_to_rack_controllers(self):
        self.become_admin()
        factory.make_RackController(owner=factory.make_User())
        response = self.client.post(
            self.get_rack_uri(), {"op": "import_boot_images"}
        )
        self.assertEqual(
            http.client.ACCEPTED,
            response.status_code,
            explain_unexpected_response(http.client.ACCEPTED, response),
        )

    def test_POST_import_boot_images_denied_if_not_admin(self):
        factory.make_RackController(owner=factory.make_User())
        response = self.client.post(
            self.get_rack_uri(), {"op": "import_boot_images"}
        )
        self.assertEqual(
            http.client.FORBIDDEN,
            response.status_code,
            explain_unexpected_response(http.client.FORBIDDEN, response),
        )

    def test_GET_describe_power_types(self):
        get_all_power_types = self.patch(
            rackcontrollers, "get_all_power_types"
        )
        self.become_admin()
        response = self.client.get(
            self.get_rack_uri(), {"op": "describe_power_types"}
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            explain_unexpected_response(http.client.OK, response),
        )
        get_all_power_types.assert_called_once_with()

    def test_GET_describe_power_types_denied_if_not_admin(self):
        get_all_power_types = self.patch(
            rackcontrollers, "get_all_power_types"
        )
        response = self.client.get(
            self.get_rack_uri(), {"op": "describe_power_types"}
        )
        self.assertEqual(
            http.client.FORBIDDEN,
            response.status_code,
            explain_unexpected_response(http.client.FORBIDDEN, response),
        )
        get_all_power_types.assert_not_called()
