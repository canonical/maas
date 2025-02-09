# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for static route API."""

import http.client
import random

from django.urls import reverse

from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object


def get_staticroutes_uri():
    """Return a static route's URI on the API."""
    return reverse("staticroutes_handler", args=[])


def get_staticroute_uri(route):
    """Return a static route URI on the API."""
    return reverse("staticroute_handler", args=[route.id])


class TestStaticRoutesAPI(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/static-routes/", get_staticroutes_uri()
        )

    def test_read(self):
        routes = [factory.make_StaticRoute().id for _ in range(3)]
        uri = get_staticroutes_uri()
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        result_ids = [
            route["id"] for route in json_load_bytes(response.content)
        ]
        self.assertCountEqual(routes, result_ids)

    def test_create(self):
        self.become_admin()
        source = factory.make_Subnet()
        destination = factory.make_Subnet(
            version=source.get_ipnetwork().version
        )
        gateway_ip = factory.pick_ip_in_Subnet(source)
        uri = get_staticroutes_uri()
        response = self.client.post(
            uri,
            {
                "source": source.id,
                "destination": destination.id,
                "gateway_ip": gateway_ip,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            gateway_ip, json_load_bytes(response.content)["gateway_ip"]
        )

    def test_create_admin_only(self):
        source = factory.make_Subnet()
        destination = factory.make_Subnet(
            version=source.get_ipnetwork().version
        )
        gateway_ip = factory.pick_ip_in_Subnet(source)
        uri = get_staticroutes_uri()
        response = self.client.post(
            uri,
            {
                "source": source.id,
                "destination": destination.id,
                "gateway_ip": gateway_ip,
            },
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )


class TestStaticRouteAPI(APITestCase.ForUser):
    def test_handler_path(self):
        route = factory.make_StaticRoute()
        self.assertEqual(
            "/MAAS/api/2.0/static-routes/%s/" % route.id,
            get_staticroute_uri(route),
        )

    def test_read(self):
        route = factory.make_StaticRoute()
        uri = get_staticroute_uri(route)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_route = json_load_bytes(response.content)
        self.assertEqual(parsed_route.get("id"), route.id)
        self.assertEqual(
            parsed_route.get("source", {}).get("cidr"), route.source.cidr
        )
        self.assertEqual(
            parsed_route.get("destination", {}).get("cidr"),
            route.destination.cidr,
        )
        self.assertEqual(parsed_route.get("gateway_ip"), route.gateway_ip)
        self.assertEqual(parsed_route.get("metric"), route.metric)

    def test_read_404_when_bad_id(self):
        uri = reverse("staticroute_handler", args=[random.randint(100, 1000)])
        response = self.client.get(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_update(self):
        self.become_admin()
        route = factory.make_StaticRoute()
        new_metric = random.randint(0, 100)
        uri = get_staticroute_uri(route)
        response = self.client.put(uri, {"metric": new_metric})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            new_metric, json_load_bytes(response.content)["metric"]
        )
        self.assertEqual(new_metric, reload_object(route).metric)

    def test_update_admin_only(self):
        route = factory.make_StaticRoute()
        new_metric = random.randint(0, 100)
        uri = get_staticroute_uri(route)
        response = self.client.put(uri, {"metric": new_metric})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_delete_deletes_fabric(self):
        self.become_admin()
        route = factory.make_StaticRoute()
        uri = get_staticroute_uri(route)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(route))

    def test_delete_403_when_not_admin(self):
        route = factory.make_StaticRoute()
        uri = get_staticroute_uri(route)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )
        self.assertIsNotNone(reload_object(route))

    def test_delete_404_when_invalid_id(self):
        self.become_admin()
        uri = reverse("staticroute_handler", args=[random.randint(100, 1000)])
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )
