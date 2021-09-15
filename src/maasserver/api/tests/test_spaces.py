# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Space API."""


import http.client
import json
import random

from django.conf import settings
from django.urls import reverse
from testtools.matchers import ContainsDict, Equals

from maasserver.models import VLAN
from maasserver.models.space import Space
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.orm import reload_object


def get_spaces_uri():
    """Return a Space's URI on the API."""
    return reverse("spaces_handler", args=[])


def get_space_uri(space):
    """Return a Space URI on the API."""
    return reverse("space_handler", args=[space.id])


def get_undefined_space_uri():
    """Return a Space URI on the API."""
    return reverse("space_handler", args=["undefined"])


def fill_empty_spaces(space=None):
    if space is None:
        space = Space.objects.first()
    for vlan in VLAN.objects.all():
        if vlan.space is None:
            vlan.space = space
            vlan.save()


class TestSpacesAPI(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual("/MAAS/api/2.0/spaces/", get_spaces_uri())

    def test_read(self):
        for _ in range(3):
            factory.make_Space()
        uri = get_spaces_uri()
        fill_empty_spaces()
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [space.id for space in Space.objects.all()]
        result_ids = [
            space["id"]
            for space in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertCountEqual(expected_ids, result_ids)

    def test_read_undefined_space(self):
        factory.make_VLAN(space=None)
        uri = get_spaces_uri()
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [-1]
        result_ids = [
            space["id"]
            for space in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertEqual(expected_ids, result_ids)

    def test_read_with_no_undefined_space(self):
        factory.make_VLAN()
        space = factory.make_Space()
        uri = get_spaces_uri()
        fill_empty_spaces(space)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        # Does not include the undefined space.
        expected_ids = [space.id]
        result_ids = [
            space["id"]
            for space in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertCountEqual(expected_ids, result_ids)

    def test_create(self):
        self.become_admin()
        space_name = factory.make_name("space")
        uri = get_spaces_uri()
        fill_empty_spaces()
        response = self.client.post(uri, {"name": space_name})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            space_name,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "name"
            ],
        )

    def test_create_admin_only(self):
        space_name = factory.make_name("space")
        uri = get_spaces_uri()
        response = self.client.post(uri, {"name": space_name})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_does_not_require_name(self):
        self.become_admin()
        uri = get_spaces_uri()
        response = self.client.post(uri, {})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        data = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual("space-%d" % data["id"], data["name"])


class TestSpaceAPI(APITestCase.ForUser):
    def test_handler_path(self):
        space = factory.make_Space()
        self.assertEqual(
            "/MAAS/api/2.0/spaces/%s/" % space.id, get_space_uri(space)
        )

    def test_read(self):
        space = factory.make_Space()
        subnet_ids = [factory.make_Subnet(space=space).id for _ in range(3)]
        uri = get_space_uri(space)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_space = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertThat(
            parsed_space,
            ContainsDict(
                {"id": Equals(space.id), "name": Equals(space.get_name())}
            ),
        )
        parsed_subnets = [subnet["id"] for subnet in parsed_space["subnets"]]
        self.assertCountEqual(subnet_ids, parsed_subnets)

    def test_read_undefined(self):
        for _ in range(3):
            factory.make_VLAN(space=None).id
        vlan_ids = VLAN.objects.all().values_list("id", flat=True)
        uri = get_undefined_space_uri()
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_space = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertThat(
            parsed_space,
            ContainsDict({"id": Equals(-1), "name": Equals(Space.UNDEFINED)}),
        )
        parsed_vlans = [vlan["id"] for vlan in parsed_space["vlans"]]
        self.assertCountEqual(vlan_ids, parsed_vlans)

    def test_includes_vlan_objects(self):
        space = factory.make_Space()
        vlan = factory.make_VLAN(space=space)
        uri = get_space_uri(space)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_space = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        parsed_vlan = parsed_space["vlans"][0]
        self.assertThat(
            parsed_vlan,
            ContainsDict(
                {
                    "id": Equals(vlan.id),
                    "vid": Equals(vlan.vid),
                    "fabric_id": Equals(vlan.fabric_id),
                }
            ),
        )

    def test_includes_legacy_subnet_objects(self):
        space = factory.make_Space()
        subnet = factory.make_Subnet(space=space)
        uri = get_space_uri(space)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_space = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        parsed_subnet = parsed_space["subnets"][0]
        self.assertThat(
            parsed_subnet,
            ContainsDict(
                {"id": Equals(subnet.id), "cidr": Equals(str(subnet.cidr))}
            ),
        )
        self.assertThat(
            parsed_subnet["vlan"],
            ContainsDict(
                {
                    "id": Equals(subnet.vlan.id),
                    "vid": Equals(subnet.vlan.vid),
                    "fabric_id": Equals(subnet.vlan.fabric_id),
                }
            ),
        )

    def test_read_404_when_bad_id(self):
        uri = reverse("space_handler", args=[random.randint(100, 1000)])
        response = self.client.get(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_update(self):
        self.become_admin()
        space = factory.make_Space()
        new_name = factory.make_name("space")
        uri = get_space_uri(space)
        response = self.client.put(uri, {"name": new_name})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            new_name,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "name"
            ],
        )
        self.assertEqual(new_name, reload_object(space).name)

    def test_update_undefined_space_not_allowed(self):
        self.become_admin()
        factory.make_VLAN(space=None)
        uri = get_undefined_space_uri()
        response = self.client.put(uri, {"name": "defined"})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_update_admin_only(self):
        space = factory.make_Space()
        new_name = factory.make_name("space")
        uri = get_space_uri(space)
        response = self.client.put(uri, {"name": new_name})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_delete_deletes_space(self):
        self.become_admin()
        space = factory.make_Space()
        uri = get_space_uri(space)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(space))

    def test_delete_undefined_vlan_not_allowed(self):
        self.become_admin()
        factory.make_VLAN(space=None)
        uri = get_undefined_space_uri()
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_delete_403_when_not_admin(self):
        space = factory.make_Space()
        uri = get_space_uri(space)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )
        self.assertIsNotNone(reload_object(space))

    def test_delete_404_when_invalid_id(self):
        self.become_admin()
        uri = reverse("space_handler", args=[random.randint(100, 1000)])
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )
