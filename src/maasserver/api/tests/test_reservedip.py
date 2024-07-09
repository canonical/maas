# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ReserveIPs API."""

import http.client

from django.urls import reverse

from maasserver.models import ReservedIP
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes


class TestReservedIPsAPI(APITestCase.ForUserAndAdmin):
    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/reservedips/", reverse("reservedips_handler")
        )

    def test_read(self):
        uri = reverse("reservedips_handler")
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        vlan = subnet.vlan
        factory.make_ReservedIP("10.0.0.121", subnet, vlan)
        factory.make_ReservedIP("10.0.0.105", subnet, vlan)
        factory.make_ReservedIP("10.0.0.15", subnet, vlan)

        response = self.client.get(uri)

        expected_ids = [
            reserved_ip.id for reserved_ip in ReservedIP.objects.all()
        ]
        ids = [
            reserved_ip["id"]
            for reserved_ip in json_load_bytes(response.content)
        ]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ids.sort(), expected_ids.sort())

    def test_read_with_no_reserved_ips(self):
        uri = reverse("reservedips_handler")
        response = self.client.get(uri)

        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(json_load_bytes(response.content), [])

    def test_create_reserved_ip(self):
        uri = reverse("reservedips_handler")
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        vlan = subnet.vlan

        response = self.client.post(
            uri,
            {
                "ip": "10.0.0.70",
                "subnet": subnet.id,
                "vlan": vlan.id,
                "mac_address": "00:11:22:33:44:55",
                "comment": "this is a comment",
            },
        )

        status_code = response.status_code
        content = json_load_bytes(response.content)
        self.assertEqual(status_code, http.client.OK)
        self.assertEqual(content["ip"], "10.0.0.70")
        self.assertEqual(content["subnet"]["id"], subnet.id)
        self.assertEqual(content["vlan"]["id"], vlan.id)
        self.assertEqual(content["mac_address"], "00:11:22:33:44:55")
        self.assertEqual(content["comment"], "this is a comment")

    def test_create_requires_a_valid_ip_address(self):
        uri = reverse("reservedips_handler")
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        vlan = subnet.vlan

        response = self.client.post(
            uri,
            {
                "subnet": subnet.id,
                "vlan": vlan.id,
                "mac_address": "00:11:22:33:44:55",
                "comment": "this is a comment",
            },
        )

        status_code = response.status_code
        content = json_load_bytes(response.content)
        self.assertEqual(status_code, http.client.BAD_REQUEST)
        self.assertEqual(
            content,
            {"ip": ["This field is required.", "This field cannot be null."]},
        )

    def test_create_requires_ip_address_that_has_not_been_reserved(self):
        uri = reverse("reservedips_handler")
        subnet = factory.make_Subnet(cidr="192.168.0.0/24")
        self.client.post(
            uri,
            {"ip": "192.168.0.15", "subnet": subnet.id},
        )

        response = self.client.post(
            uri,
            {"ip": "192.168.0.15", "subnet": subnet.id},
        )

        status_code = response.status_code
        content = json_load_bytes(response.content)
        self.assertEqual(status_code, http.client.BAD_REQUEST)
        self.assertEqual(
            content,
            {"ip": ["Reserved IP with this IP address already exists."]},
        )

    def test_create_requires_mac_address_that_has_not_been_reserved(self):
        uri = reverse("reservedips_handler")
        subnet = factory.make_Subnet(cidr="192.168.0.0/24")
        self.client.post(
            uri,
            {
                "ip": "192.168.0.15",
                "subnet": subnet.id,
                "mac_address": "00:11:22:33:44:55",
            },
        )

        response = self.client.post(
            uri,
            {
                "ip": "192.168.0.16",
                "subnet": subnet.id,
                "mac_address": "00:11:22:33:44:55",
            },
        )

        status_code = response.status_code
        content = json_load_bytes(response.content)
        self.assertEqual(status_code, http.client.BAD_REQUEST)
        self.assertEqual(
            content,
            {
                "__all__": [
                    "Reserved IP with this MAC address and VLAN already exists."
                ]
            },
        )

    def test_create_requires_mac_addresses_and_vlan_that_have_not_been_reserved_together(
        self,
    ):
        uri = reverse("reservedips_handler")
        subnet_1 = factory.make_Subnet(cidr="192.168.0.0/24")
        vlan_1 = subnet_1.vlan
        subnet_2 = factory.make_Subnet(cidr="10.10.0.0/24")
        vlan_2 = subnet_2.vlan
        self.client.post(
            uri,
            {
                "ip": "192.168.0.15",
                "vlan": vlan_1.id,
                "mac_address": "00:11:22:33:44:55",
            },
        )

        # reserving an IP for the same device in a different VLAN
        response = self.client.post(
            uri,
            {
                "ip": "10.10.0.101",
                "vlan": vlan_2.id,
                "mac_address": "00:11:22:33:44:55",
            },
        )
        # is accepted
        status_code = response.status_code
        self.assertEqual(status_code, http.client.OK)

        # reserving an IP for the same device in the same VLAN
        response = self.client.post(
            uri,
            {
                "ip": "192.168.0.49",
                "vlan": vlan_1.id,
                "mac_address": "00:11:22:33:44:55",
            },
        )
        # is not accepted
        status_code = response.status_code
        content = json_load_bytes(response.content)
        self.assertEqual(status_code, http.client.BAD_REQUEST)
        self.assertEqual(
            content,
            {
                "__all__": [
                    "Reserved IP with this MAC address and VLAN already exists."
                ]
            },
        )

    def test_create_requires_ip_within_subnet(self):
        uri = reverse("reservedips_handler")
        subnet = factory.make_Subnet(cidr="192.168.0.0/24")

        response = self.client.post(
            uri,
            {
                "ip": "192.168.1.10",
                "subnet": subnet.id,
                "mac_address": "00:11:22:33:44:55",
                "comment": "Test: creating a reserved IP",
            },
        )

        status_code = response.status_code
        content = json_load_bytes(response.content)
        self.assertEqual(status_code, http.client.BAD_REQUEST)
        self.assertEqual(
            content,
            {"ip": ["The provided IP is not part of the subnet."]},
        )

    def test_create_requires_ip_not_to_be_broadcast_address(self):
        uri = reverse("reservedips_handler")
        subnet = factory.make_Subnet(cidr="192.168.0.0/24")

        response = self.client.post(
            uri,
            {
                "ip": "192.168.0.255",
                "subnet": subnet.id,
                "mac_address": "00:11:22:33:44:55",
                "comment": "Test: creating a reserved IP",
            },
        )

        status_code = response.status_code
        content = json_load_bytes(response.content)
        self.assertEqual(status_code, http.client.BAD_REQUEST)
        self.assertEqual(
            content, {"ip": ["The broadcast address cannot be a reserved IP."]}
        )

    def test_create_requires_ip_not_to_be_network_address(self):
        uri = reverse("reservedips_handler")
        subnet = factory.make_Subnet(cidr="192.168.0.0/24")

        response = self.client.post(
            uri,
            {
                "ip": "192.168.0.0",
                "subnet": subnet.id,
                "mac_address": "00:11:22:33:44:55",
                "comment": "Test: creating a reserved IP",
            },
        )

        status_code = response.status_code
        content = json_load_bytes(response.content)
        self.assertEqual(status_code, http.client.BAD_REQUEST)
        self.assertEqual(
            content, {"ip": ["The network address cannot be a reserved IP."]}
        )

    def test_create_requires_ip_not_to_be_anycast_address(self):
        uri = reverse("reservedips_handler")
        subnet = factory.make_Subnet(cidr="2001::/64")

        response = self.client.post(
            uri,
            {
                "ip": "2001::",
                "subnet": subnet.id,
                "mac_address": "00:11:22:33:44:55",
                "comment": "Test: creating a reserved IP",
            },
        )

        status_code = response.status_code
        content = json_load_bytes(response.content)

        assert status_code == http.client.BAD_REQUEST
        assert content == {
            "ip": ["The network address cannot be a reserved IP."]
        }

    def test_create_requires_a_valid_mac_address(self):
        uri = reverse("reservedips_handler")
        subnet = factory.make_Subnet(cidr="192.168.0.0/24")

        # valid MAC address
        response = self.client.post(
            uri,
            {
                "ip": "192.168.0.10",
                "subnet": subnet.id,
                "mac_address": "00:11:22:33:44:55",
            },
        )
        assert response.status_code == http.client.OK
        response = self.client.post(
            uri,
            {"ip": "192.168.0.14", "subnet": subnet.id},
        )
        assert response.status_code == http.client.OK

        # invalid MAC address
        msgs = [
            "'00:11:22:33:44:gg' is not a valid MAC address.",
            "'0011:22:33:44:55' is not a valid MAC address.",
        ]
        for ip_value, mac_value, msg in [
            ("192.168.0.11", "00:11:22:33:44:gg", {"mac_address": [msgs[0]]}),
            ("192.168.0.15", "0011:22:33:44:55", {"mac_address": [msgs[1]]}),
        ]:
            response = self.client.post(
                uri,
                {
                    "ip": ip_value,
                    "subnet": subnet.id,
                    "mac_address": mac_value,
                },
            )
            status_code = response.status_code
            content = json_load_bytes(response.content)

            assert status_code == http.client.BAD_REQUEST
            assert content == msg


class TestReservedIPAPI(APITestCase.ForUserAndAdmin):
    def test_handler_path(self):
        reserved_ip = factory.make_ReservedIP()

        self.assertEqual(
            f"/MAAS/api/2.0/reservedips/{reserved_ip.id}/",
            reverse("reservedip_handler", args=[reserved_ip.id]),
        )

    def test_read(self):
        reserved_ip = factory.make_ReservedIP()
        uri = reverse("reservedip_handler", args=[reserved_ip.id])

        response = self.client.get(uri)

        status_code = response.status_code
        content = json_load_bytes(response.content)
        self.assertEqual(status_code, http.client.OK)
        self.assertEqual(content["id"], reserved_ip.id)
        self.assertEqual(content["ip"], reserved_ip.ip)
        self.assertEqual(content["subnet"]["id"], reserved_ip.subnet.id)
        self.assertEqual(content["mac_address"], reserved_ip.mac_address)
        self.assertEqual(content["comment"], reserved_ip.comment)

    def test_read_when_no_id_matches_the_request(self):
        uri = reverse("reservedip_handler", args=[101])
        response = self.client.get(uri)

        status_code = response.status_code
        self.assertEqual(status_code, http.client.NOT_FOUND)

    def test_update(self):
        reserved_ip = factory.make_ReservedIP()
        uri = reverse("reservedip_handler", args=[reserved_ip.id])

        response = self.client.put(
            uri,
            {
                "ip": reserved_ip.ip,
                "mac_address": "00:11:22:33:44:55",
                "comment": "updated comment",
            },
        )

        status_code = response.status_code
        content = json_load_bytes(response.content)
        self.assertEqual(status_code, http.client.OK)
        self.assertEqual(content["id"], reserved_ip.id)
        self.assertEqual(content["ip"], reserved_ip.ip)
        self.assertEqual(content["subnet"]["id"], reserved_ip.subnet.id)
        self.assertEqual(content["vlan"]["id"], reserved_ip.subnet.vlan.id)
        self.assertEqual(content["mac_address"], "00:11:22:33:44:55")
        self.assertEqual(content["comment"], "updated comment")

    def test_update_return_400_with_ip_in_different_subnet(self):
        factory.make_Subnet(cidr="192.168.0.0/24")
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        reserved_ip = factory.make_ReservedIP(
            ip="10.0.0.121", subnet=subnet, vlan=subnet.vlan
        )
        uri = reverse("reservedip_handler", args=[reserved_ip.id])

        response = self.client.put(
            uri,
            {"ip": "192.168.0.45"},
        )

        status_code = response.status_code
        self.assertEqual(status_code, http.client.BAD_REQUEST)

    def test_update_returns_404_with_invalid_id(self):
        uri = reverse("reservedip_handler", args=[101])

        response = self.client.put(
            uri,
            {
                "ip": "10.0.0.45",
                "mac_address": "00:11:22:33:44:55",
                "comment": "updated comment",
            },
        )

        status_code = response.status_code
        self.assertEqual(status_code, http.client.NOT_FOUND)

    def test_update_returns_400_when_using_ip_already_reserved(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        factory.make_ReservedIP(
            ip="10.0.0.150", subnet=subnet, vlan=subnet.vlan
        )
        reserved_ip = factory.make_ReservedIP(
            ip="10.0.0.121", subnet=subnet, vlan=subnet.vlan
        )
        uri = reverse("reservedip_handler", args=[reserved_ip.id])

        response = self.client.put(
            uri,
            {"ip": "10.0.0.150"},
        )

        status_code = response.status_code
        content = json_load_bytes(response.content)
        self.assertEqual(status_code, http.client.BAD_REQUEST)
        self.assertEqual(
            content,
            {"ip": ["Reserved IP with this IP address already exists."]},
        )

    def test_delete(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        reserved_ip = factory.make_ReservedIP(
            ip="10.0.0.121", subnet=subnet, vlan=subnet.vlan
        )
        uri = reverse("reservedip_handler", args=[reserved_ip.id])

        response = self.client.delete(uri)

        status_code = response.status_code
        self.assertEqual(status_code, http.client.NO_CONTENT)

    def test_delete_return_404_when_no_id_matches_the_request(self):
        uri = reverse("reservedip_handler", args=[101])
        response = self.client.delete(uri)

        status_code = response.status_code
        self.assertEqual(status_code, http.client.NOT_FOUND)
