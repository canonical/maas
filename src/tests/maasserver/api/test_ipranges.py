# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for IPRange API."""

import http.client
import json
import random
from urllib import parse

from django.conf import settings
from django.urls import reverse

from maasserver.models.iprange import IPRange
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.orm import reload_object


def get_ipranges_uri():
    """Return a Space's URI on the API."""
    return reverse("ipranges_handler", args=[])


def get_iprange_uri(iprange):
    """Return a Space URI on the API."""
    return reverse("iprange_handler", args=[iprange.id])


class TestIPRangesAPI(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual("/MAAS/api/2.0/ipranges/", get_ipranges_uri())

    def test_read(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        factory.make_IPRange(subnet, "10.0.0.2", "10.0.0.10")
        factory.make_IPRange(subnet, "10.0.0.11", "10.0.0.20")
        factory.make_IPRange(subnet, "10.0.0.21", "10.0.0.30")
        uri = get_ipranges_uri()
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [iprange.id for iprange in IPRange.objects.all()]
        result_ids = [
            iprange["id"]
            for iprange in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertCountEqual(expected_ids, result_ids)

    def test_create_dynamic(self):
        self.become_admin()
        uri = get_ipranges_uri()
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        response = self.client.post(
            uri,
            {
                "type": "dynamic",
                "start_ip": "10.0.0.10",
                "end_ip": "10.0.0.20",
                "subnet": "%d" % subnet.id,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        data = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual("10.0.0.10", data["start_ip"])
        self.assertEqual("10.0.0.20", data["end_ip"])
        self.assertEqual(subnet.id, data["subnet"]["id"])

    def test_create_dynamic_encoded(self):
        """
        There is a quirk in Django where the resulting handler will get a
        mutable dictionary in some instances (with just a json body) and an
        immutable dictionary in others (In the case for form encoded body).

        Specifying a content type of x-www-form-urlencoded should cause
        Django to produce an immutable dictionary.

        :return:
        """
        self.become_admin()
        uri = get_ipranges_uri()
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        response = self.client.post(
            uri,
            parse.urlencode(
                {
                    "type": "dynamic",
                    "start_ip": "10.0.0.10",
                    "end_ip": "10.0.0.20",
                    "subnet": "%d" % subnet.id,
                }
            ),
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        data = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual("10.0.0.10", data["start_ip"])
        self.assertEqual("10.0.0.20", data["end_ip"])
        self.assertEqual(subnet.id, data["subnet"]["id"])

    def test_create_dynamic_requires_admin(self):
        uri = get_ipranges_uri()
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        response = self.client.post(
            uri,
            {
                "type": "dynamic",
                "start_ip": "10.0.0.10",
                "end_ip": "10.0.0.20",
                "subnet": "%d" % subnet.id,
            },
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_does_not_require_subnet(self):
        uri = get_ipranges_uri()
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        response = self.client.post(
            uri,
            {
                "type": "reserved",
                "start_ip": "10.0.0.10",
                "end_ip": "10.0.0.20",
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        data = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual("10.0.0.10", data["start_ip"])
        self.assertEqual("10.0.0.20", data["end_ip"])
        self.assertEqual(subnet.id, data["subnet"]["id"])

    def test_create_requires_type_and_reports_simple_error_if_missing(self):
        uri = get_ipranges_uri()
        factory.make_Subnet(cidr="10.0.0.0/24")
        response = self.client.post(
            uri, {"start_ip": "10.0.0.10", "end_ip": "10.0.0.20"}
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            b'{"type": ["This field is required."]}', response.content
        )

    def test_create_sets_user_to_authenticated_user(self):
        uri = get_ipranges_uri()
        factory.make_Subnet(cidr="10.0.0.0/24")
        response = self.client.post(
            uri,
            {
                "type": "reserved",
                "start_ip": "10.0.0.10",
                "end_ip": "10.0.0.20",
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        data = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(self.user.username, data["user"]["username"])


class TestIPRangeAPI(APITestCase.ForUser):
    def test_handler_path(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        iprange = factory.make_IPRange(subnet, "10.0.0.2", "10.0.0.10")
        self.assertEqual(
            "/MAAS/api/2.0/ipranges/%s/" % iprange.id, get_iprange_uri(iprange)
        )

    def test_read(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        iprange = factory.make_IPRange(subnet, "10.0.0.2", "10.0.0.10")
        factory.make_IPRange(subnet, "10.0.0.11", "10.0.0.20")
        factory.make_IPRange(subnet, "10.0.0.21", "10.0.0.30")
        uri = get_iprange_uri(iprange)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_ipranges = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(parsed_ipranges.get("id"), iprange.id)
        self.assertEqual(parsed_ipranges.get("start_ip"), iprange.start_ip)
        self.assertEqual(parsed_ipranges.get("end_ip"), iprange.end_ip)
        self.assertEqual(parsed_ipranges.get("comment"), iprange.comment)
        self.assertEqual(parsed_ipranges.get("type"), iprange.type)
        self.assertEqual(parsed_ipranges.get("user"), iprange.user)

    def test_read_404_when_bad_id(self):
        uri = reverse("iprange_handler", args=[random.randint(10000, 20000)])
        response = self.client.get(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_update(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        iprange = factory.make_IPRange(
            subnet, "10.0.0.2", "10.0.0.10", user=self.user
        )
        uri = get_iprange_uri(iprange)
        comment = factory.make_name("comment")
        response = self.client.put(uri, {"comment": comment})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            comment,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "comment"
            ],
        )
        self.assertEqual(comment, reload_object(iprange).comment)

    def test_update_403_when_not_user(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        iprange = factory.make_IPRange(
            subnet, "10.0.0.2", "10.0.0.10", user=factory.make_User()
        )
        uri = get_iprange_uri(iprange)
        response = self.client.put(uri, {})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_update_404_when_invalid_id(self):
        uri = reverse("iprange_handler", args=[random.randint(100, 1000)])
        response = self.client.put(uri, {})
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_delete_deletes_iprange(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        iprange = factory.make_IPRange(
            subnet, "10.0.0.2", "10.0.0.10", user=self.user
        )
        uri = get_iprange_uri(iprange)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(iprange))

    def test_delete_403_when_not_user(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        iprange = factory.make_IPRange(
            subnet, "10.0.0.2", "10.0.0.10", user=factory.make_User()
        )
        uri = get_iprange_uri(iprange)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )
        self.assertIsNotNone(reload_object(iprange))

    def test_delete_404_when_invalid_id(self):
        uri = reverse("iprange_handler", args=[random.randint(100, 1000)])
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )
