# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import http.client
import random

from django.urls import reverse

from maasserver.api import auth
from maasserver.enum import NODE_STATUS, NODE_TYPE
from maasserver.models import Device, Domain
from maasserver.models import node as node_module
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.fixtures import RBACEnabled
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object


class TestDeviceOwnerData(APITestCase.ForUser):
    def test_GET_returns_owner_data(self):
        owner_data = {factory.make_name("key"): factory.make_name("value")}
        factory.make_Device(owner=self.user, owner_data=owner_data)
        response = self.client.get(reverse("devices_handler"))
        self.assertEqual(
            http.client.OK.value, response.status_code, response.content
        )
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            [owner_data],
            [device.get("owner_data") for device in parsed_result],
        )


class TestDevicesAPI(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual("/MAAS/api/2.0/devices/", reverse("devices_handler"))

    def test_POST_creates_device(self):
        hostname = factory.make_name("host")
        macs = {
            factory.make_mac_address() for _ in range(random.randint(1, 2))
        }
        response = self.client.post(
            reverse("devices_handler"),
            {"hostname": hostname, "mac_addresses": macs},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        system_id = json_load_bytes(response.content)["system_id"]
        device = Device.objects.get(system_id=system_id)
        self.assertEqual(hostname, device.hostname)
        self.assertIsNone(device.parent)
        self.assertEqual(device.node_type, NODE_TYPE.DEVICE)
        self.assertEqual(self.user, device.owner)
        self.assertEqual(
            macs,
            {
                nic.mac_address
                for nic in device.current_config.interface_set.all()
            },
        )

    def test_POST_creates_device_with_parent(self):
        parent = factory.make_Node()
        hostname = factory.make_name("host")
        macs = {
            factory.make_mac_address() for _ in range(random.randint(1, 2))
        }
        response = self.client.post(
            reverse("devices_handler"),
            {
                "hostname": hostname,
                "mac_addresses": macs,
                "parent": parent.system_id,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        system_id = json_load_bytes(response.content)["system_id"]
        device = Device.objects.get(system_id=system_id)
        self.assertEqual(hostname, device.hostname)
        self.assertEqual(parent, device.parent)
        self.assertEqual(device.node_type, NODE_TYPE.DEVICE)

    def test_POST_creates_device_with_default_domain(self):
        hostname = factory.make_name("host")
        macs = {
            factory.make_mac_address() for _ in range(random.randint(1, 2))
        }
        response = self.client.post(
            reverse("devices_handler"),
            {"hostname": hostname, "mac_addresses": macs},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        system_id = json_load_bytes(response.content)["system_id"]
        device = Device.objects.get(system_id=system_id)
        self.assertEqual(hostname, device.hostname)
        self.assertEqual(Domain.objects.get_default_domain(), device.domain)
        self.assertEqual(device.node_type, NODE_TYPE.DEVICE)

    def test_POST_creates_device_with_domain(self):
        hostname = factory.make_name("host")
        domain = factory.make_Domain()
        macs = {
            factory.make_mac_address() for _ in range(random.randint(1, 2))
        }
        response = self.client.post(
            reverse("devices_handler"),
            {
                "hostname": hostname,
                "mac_addresses": macs,
                "domain": domain.name,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        system_id = json_load_bytes(response.content)["system_id"]
        device = Device.objects.get(system_id=system_id)
        self.assertEqual(hostname, device.hostname)
        self.assertEqual(domain, device.domain)
        self.assertEqual(device.node_type, NODE_TYPE.DEVICE)

    def test_POST_without_macs_raises_appropriate_error(self):
        hostname = factory.make_name("host")
        domain = factory.make_Domain()
        response = self.client.post(
            reverse("devices_handler"),
            {"hostname": hostname, "domain": domain.name},
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_empty_POST_raises_appropriate_error(self):
        response = self.client.post(reverse("devices_handler"), {})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_POST_returns_limited_fields(self):
        response = self.client.post(
            reverse("devices_handler"),
            {
                "hostname": factory.make_string(),
                "mac_addresses": ["aa:bb:cc:dd:ee:ff"],
            },
        )
        parsed_result = json_load_bytes(response.content)
        self.assertCountEqual(
            {
                "address_ttl",
                "hostname",
                "description",
                "domain",
                "fqdn",
                "owner",
                "owner_data",
                "system_id",
                "node_type",
                "node_type_name",
                "parent",
                "tag_names",
                "ip_addresses",
                "interface_set",
                "resource_uri",
                "workload_annotations",
                "zone",
            },
            parsed_result.keys(),
        )

    def create_devices(self, owner, nb=3):
        return [
            factory.make_Node(
                interface=True, node_type=NODE_TYPE.DEVICE, owner=owner
            )
            for _ in range(nb)
        ]

    def test_read_lists_devices(self):
        # The api allows for fetching the list of devices.
        devices = self.create_devices(owner=self.user)
        factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        response = self.client.get(reverse("devices_handler"))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertCountEqual(
            [device.system_id for device in devices],
            [device.get("system_id") for device in parsed_result],
        )

    def test_read_ignores_nodes(self):
        factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        response = self.client.get(reverse("devices_handler"))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            [], [device.get("system_id") for device in parsed_result]
        )

    def test_read_with_id_returns_matching_devices(self):
        # The "list" operation takes optional "id" parameters.  Only
        # devices with matching ids will be returned.
        devices = self.create_devices(owner=self.user)
        ids = [device.system_id for device in devices]
        matching_id = ids[0]
        response = self.client.get(
            reverse("devices_handler"), {"id": [matching_id]}
        )
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            [matching_id],
            [device.get("system_id") for device in parsed_result],
        )

    def test_read_with_macaddress_returns_matching_devices(self):
        # The "list" operation takes optional "mac_address" parameters.  Only
        # devices with matching MAC addresses will be returned.
        devices = self.create_devices(owner=self.user)
        matching_device = devices[0]
        matching_mac = matching_device.get_boot_interface().mac_address
        response = self.client.get(
            reverse("devices_handler"), {"mac_address": [matching_mac]}
        )
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            [matching_device.system_id],
            [device.get("system_id") for device in parsed_result],
        )

    def test_read_returns_limited_fields(self):
        self.create_devices(owner=self.user)
        response = self.client.get(reverse("devices_handler"))
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            {
                "address_ttl",
                "hostname",
                "description",
                "domain",
                "fqdn",
                "owner",
                "owner_data",
                "system_id",
                "node_type",
                "node_type_name",
                "parent",
                "tag_names",
                "ip_addresses",
                "interface_set",
                "resource_uri",
                "workload_annotations",
                "zone",
            },
            parsed_result[0].keys(),
        )

    def test_create_no_permission(self):
        self.patch(auth, "validate_user_external_auth").return_value = True
        self.useFixture(RBACEnabled())
        self.become_non_local()
        response = self.client.post(
            reverse("devices_handler"),
            {"mac_addresses": ["aa:bb:cc:dd:ee:ff"]},
        )
        self.assertEqual(response.status_code, http.client.FORBIDDEN)


def get_device_uri(device):
    """Return a device's URI on the API."""
    return reverse("device_handler", args=[device.system_id])


class TestDeviceAPI(APITestCase.ForUser):
    def test_handler_path(self):
        system_id = factory.make_name("system-id")
        self.assertEqual(
            "/MAAS/api/2.0/devices/%s/" % system_id,
            reverse("device_handler", args=[system_id]),
        )

    def test_POST_method_without_op_not_allowed(self):
        device = factory.make_Node(node_type=NODE_TYPE.DEVICE, owner=self.user)

        response = self.client.post(get_device_uri(device))
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_GET_reads_device(self):
        device = factory.make_Node(node_type=NODE_TYPE.DEVICE, owner=self.user)

        response = self.client.get(get_device_uri(device))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertEqual(device.system_id, parsed_device["system_id"])

    def test_PUT_updates_device_hostname_description(self):
        device = factory.make_Node(node_type=NODE_TYPE.DEVICE, owner=self.user)
        new_hostname = factory.make_name("hostname")
        new_description = factory.make_name("description")

        response = self.client.put(
            get_device_uri(device),
            {"hostname": new_hostname, "description": new_description},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        device = reload_object(device)
        self.assertEqual(new_hostname, device.hostname)
        self.assertEqual(new_description, device.description)

    def test_PUT_updates_device_parent(self):
        parent = factory.make_Node()
        device = factory.make_Node(
            node_type=NODE_TYPE.DEVICE, owner=self.user, parent=parent
        )
        new_parent = factory.make_Node()

        response = self.client.put(
            get_device_uri(device), {"parent": new_parent.system_id}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        device = reload_object(device)
        self.assertEqual(new_parent, device.parent)

    def test_PUT_rejects_edit_if_not_permitted(self):
        device = factory.make_Node(
            node_type=NODE_TYPE.DEVICE, owner=factory.make_User()
        )
        old_hostname = device.hostname

        response = self.client.put(
            get_device_uri(device), {"hostname": factory.make_name("hostname")}
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertEqual(old_hostname, reload_object(device).hostname)

    def test_PUT_updates_with_rbac(self):
        self.patch(auth, "validate_user_external_auth").return_value = True
        self.useFixture(RBACEnabled())
        self.become_non_local()

        device = factory.make_Node(node_type=NODE_TYPE.DEVICE, owner=self.user)
        new_hostname = factory.make_name("hostname")

        response = self.client.put(
            get_device_uri(device), {"hostname": new_hostname}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        device = reload_object(device)
        self.assertEqual(new_hostname, device.hostname)

    def test_DELETE_removes_device(self):
        device = factory.make_Node(node_type=NODE_TYPE.DEVICE, owner=self.user)
        response = self.client.delete(get_device_uri(device))
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(device))

    def test_DELETE_rejects_deletion_if_not_permitted(self):
        device = factory.make_Node(
            node_type=NODE_TYPE.DEVICE, owner=factory.make_User()
        )
        response = self.client.delete(get_device_uri(device))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertEqual(device, reload_object(device))

    def test_restore_networking_configuration(self):
        self.become_admin()
        device = factory.make_Device()
        mock_set_initial_networking_config = self.patch(
            node_module.Device, "set_initial_networking_configuration"
        )
        response = self.client.post(
            get_device_uri(device), {"op": "restore_networking_configuration"}
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            device.system_id, json_load_bytes(response.content)["system_id"]
        )
        mock_set_initial_networking_config.assert_called_once()

    def test_restore_networking_configuration_requires_admin(self):
        device = factory.make_Device()
        response = self.client.post(
            get_device_uri(device), {"op": "restore_networking_configuration"}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_restore_default_configuration(self):
        self.become_admin()
        device = factory.make_Device()
        mock_set_initial_networking_config = self.patch(
            node_module.Device, "set_initial_networking_configuration"
        )
        response = self.client.post(
            get_device_uri(device), {"op": "restore_default_configuration"}
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            device.system_id, json_load_bytes(response.content)["system_id"]
        )
        mock_set_initial_networking_config.assert_called_once()

    def test_restore_default_configuration_requires_admin(self):
        device = factory.make_Device()
        response = self.client.post(
            get_device_uri(device), {"op": "restore_default_configuration"}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )
