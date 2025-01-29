# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ReserveIPs API."""

import http.client

from django.urls import reverse
from twisted.internet import defer

import maasserver.api.reservedip as reservedip_module
from maasserver.dhcp import configure_dhcp_on_agents
from maasserver.models import ReservedIP
from maasserver.models import subnet as subnet_module
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes


class TestReservedIPsAPI(APITestCase.ForUser):
    def setUp(self):
        super().setUp()
        d = defer.succeed(None)
        self.patch(reservedip_module, "post_commit_do").return_value = d
        self.patch(subnet_module, "start_workflow")

    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/reservedips/", reverse("reservedips_handler")
        )

    def test_read(self):
        uri = reverse("reservedips_handler")
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        factory.make_ReservedIP("10.0.0.121", subnet)
        factory.make_ReservedIP("10.0.0.105", subnet)
        factory.make_ReservedIP("10.0.0.15", subnet)

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
        self.become_admin()
        uri = reverse("reservedips_handler")
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")

        response = self.client.post(
            uri,
            {
                "ip": "10.0.0.70",
                "subnet": subnet.id,
                "mac_address": "00:11:22:33:44:55",
                "comment": "this is a comment",
            },
        )

        status_code = response.status_code
        content = json_load_bytes(response.content)
        self.assertEqual(status_code, http.client.OK)
        self.assertEqual(content["ip"], "10.0.0.70")
        self.assertEqual(content["subnet"]["id"], subnet.id)
        self.assertEqual(content["mac_address"], "00:11:22:33:44:55")
        self.assertEqual(content["comment"], "this is a comment")

        reservedip_module.post_commit_do.assert_called_once_with(
            configure_dhcp_on_agents, reserved_ip_ids=[content["id"]]
        )

    def test_create_requires_admin(self):
        uri = reverse("reservedips_handler")
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")

        response = self.client.post(
            uri,
            {
                "ip": "10.0.0.70",
                "subnet": subnet.id,
                "mac_address": "01:02:03:04:05:06",
            },
        )

        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )


class TestReservedIPAPI(APITestCase.ForUser):

    def setUp(self):
        super().setUp()
        d = defer.succeed(None)
        self.patch(reservedip_module, "post_commit_do").return_value = d
        self.patch(subnet_module, "start_workflow")

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
        self.become_admin()
        reserved_ip = factory.make_ReservedIP()
        uri = reverse("reservedip_handler", args=[reserved_ip.id])

        response = self.client.put(
            uri,
            {
                "ip": reserved_ip.ip,
                "mac_address": reserved_ip.mac_address,
                "comment": "updated comment",
            },
        )

        status_code = response.status_code
        content = json_load_bytes(response.content)
        self.assertEqual(status_code, http.client.OK)
        self.assertEqual(content["id"], reserved_ip.id)
        self.assertEqual(content["ip"], reserved_ip.ip)
        self.assertEqual(content["subnet"]["id"], reserved_ip.subnet.id)
        self.assertEqual(content["mac_address"], reserved_ip.mac_address)
        self.assertEqual(content["comment"], "updated comment")

        reservedip_module.post_commit_do.assert_not_called()

    def test_update_return_400_with_ip_in_different_subnet(self):
        self.become_admin()
        factory.make_Subnet(cidr="192.168.0.0/24")
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        reserved_ip = factory.make_ReservedIP(ip="10.0.0.121", subnet=subnet)
        uri = reverse("reservedip_handler", args=[reserved_ip.id])

        response = self.client.put(
            uri,
            {"ip": "192.168.0.45"},
        )

        status_code = response.status_code
        self.assertEqual(status_code, http.client.BAD_REQUEST)
        reservedip_module.post_commit_do.assert_not_called()

    def test_update_returns_404_with_invalid_id(self):
        self.become_admin()
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

    def test_update_requires_admin(self):
        reserved_ip = factory.make_ReservedIP()
        uri = reverse("reservedip_handler", args=[reserved_ip.id])

        response = self.client.put(
            uri,
            {
                "ip": reserved_ip.ip,
                "mac_address": reserved_ip.mac_address,
                "comment": "updated comment",
            },
        )

        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_delete(self):
        self.become_admin()
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        reserved_ip = factory.make_ReservedIP(ip="10.0.0.121", subnet=subnet)
        uri = reverse("reservedip_handler", args=[reserved_ip.id])

        response = self.client.delete(uri)

        status_code = response.status_code
        self.assertEqual(status_code, http.client.NO_CONTENT)
        reservedip_module.post_commit_do.assert_called_once_with(
            configure_dhcp_on_agents, subnet_ids=[reserved_ip.subnet.id]
        )

    def test_delete_return_404_when_no_id_matches_the_request(self):
        self.become_admin()
        uri = reverse("reservedip_handler", args=[101])
        response = self.client.delete(uri)

        status_code = response.status_code
        self.assertEqual(status_code, http.client.NOT_FOUND)
        reservedip_module.post_commit_do.assert_not_called()

    def test_delete_requires_admin(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        reserved_ip = factory.make_ReservedIP(ip="10.0.0.121", subnet=subnet)
        uri = reverse("reservedip_handler", args=[reserved_ip.id])

        response = self.client.delete(uri)

        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )
