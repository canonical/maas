# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Fabric API."""


import http.client
import random

from django.urls import reverse

from maasserver.models.fabric import Fabric
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object
from maastesting.djangotestcase import count_queries


def get_fabrics_uri():
    """Return a Fabric's URI on the API."""
    return reverse("fabrics_handler", args=[])


def get_fabric_uri(fabric):
    """Return a Fabric URI on the API."""
    return reverse("fabric_handler", args=[fabric.id])


def make_complex_fabric():
    # use a single space for all VLANs to avoid extra queries based on whether
    # other spaces are created
    space = factory.make_Space()
    fabric = factory.make_Fabric()
    vlans = [fabric.get_default_vlan()]
    for _ in range(3):
        vlan = factory.make_VLAN(fabric=fabric, dhcp_on=True, space=space)
        rack_controller = factory.make_RackController(vlan=vlan)
        vlan.primary_rack = rack_controller
        vlan.save()
        vlans.append(vlan)
    for vlan in vlans:
        factory.make_VLAN(fabric=fabric, relay_vlan=vlan, space=space)
    return fabric


class TestFabricsAPI(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual("/MAAS/api/2.0/fabrics/", get_fabrics_uri())

    def test_read(self):
        for _ in range(3):
            factory.make_Fabric()
        uri = get_fabrics_uri()
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [fabric.id for fabric in Fabric.objects.all()]
        result_ids = [
            fabric["id"] for fabric in json_load_bytes(response.content)
        ]
        self.assertCountEqual(expected_ids, result_ids)

    def test_read_has_constant_number_of_queries(self):
        for _ in range(3):
            make_complex_fabric()

        uri = get_fabrics_uri()
        num_queries1, response1 = count_queries(self.client.get, uri)

        for _ in range(3):
            make_complex_fabric()

        num_queries2, response2 = count_queries(self.client.get, uri)

        # Make sure the responses are ok as it's not useful to compare the
        # number of queries if they are not.
        parsed_result_1 = json_load_bytes(response1.content)
        parsed_result_2 = json_load_bytes(response2.content)
        self.assertEqual(
            [http.client.OK, http.client.OK, 3, 6],
            [
                response1.status_code,
                response2.status_code,
                len(parsed_result_1),
                len(parsed_result_2),
            ],
        )
        self.assertEqual(num_queries1, num_queries2)

    def test_create(self):
        self.become_admin()
        fabric_name = factory.make_name("fabric")
        uri = get_fabrics_uri()
        response = self.client.post(uri, {"name": fabric_name})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            fabric_name, json_load_bytes(response.content)["name"]
        )

    def test_create_admin_only(self):
        fabric_name = factory.make_name("fabric")
        uri = get_fabrics_uri()
        response = self.client.post(uri, {"name": fabric_name})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )


class TestFabricAPI(APITestCase.ForUser):
    def test_handler_path(self):
        fabric = factory.make_Fabric()
        self.assertEqual(
            "/MAAS/api/2.0/fabrics/%s/" % fabric.id, get_fabric_uri(fabric)
        )

    def test_read(self):
        class_type = factory.make_name("class")
        fabric = factory.make_Fabric(class_type=class_type)
        for vid in range(1, 4):
            factory.make_VLAN(fabric=fabric, vid=vid).id
        uri = get_fabric_uri(fabric)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_fabric = json_load_bytes(response.content)
        self.assertEqual(parsed_fabric.get("id"), fabric.id)
        self.assertEqual(parsed_fabric.get("name"), fabric.get_name())
        self.assertEqual(parsed_fabric.get("class_type"), class_type)
        self.assertCountEqual(
            [vlan.id for vlan in fabric.vlan_set.all()],
            [vlan["id"] for vlan in parsed_fabric["vlans"]],
        )

    def test_read_404_when_bad_id(self):
        uri = reverse("fabric_handler", args=[random.randint(100, 1000)])
        response = self.client.get(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_update(self):
        self.become_admin()
        fabric = factory.make_Fabric()
        new_name = factory.make_name("fabric")
        uri = get_fabric_uri(fabric)
        response = self.client.put(uri, {"name": new_name})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(new_name, json_load_bytes(response.content)["name"])
        self.assertEqual(new_name, reload_object(fabric).name)

    def test_update_admin_only(self):
        fabric = factory.make_Fabric()
        new_name = factory.make_name("fabric")
        uri = get_fabric_uri(fabric)
        response = self.client.put(uri, {"name": new_name})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_delete_deletes_fabric(self):
        self.become_admin()
        fabric = factory.make_Fabric()
        uri = get_fabric_uri(fabric)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(fabric))

    def test_delete_403_when_not_admin(self):
        fabric = factory.make_Fabric()
        uri = get_fabric_uri(fabric)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )
        self.assertIsNotNone(reload_object(fabric))

    def test_delete_404_when_invalid_id(self):
        self.become_admin()
        uri = reverse("fabric_handler", args=[random.randint(100, 1000)])
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )
