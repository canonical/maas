# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Space API."""

__all__ = []

import http.client
import json
import random

from django.conf import settings
from django.core.urlresolvers import reverse
from maasserver.models.space import Space
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from testtools.matchers import (
    ContainsDict,
    Equals,
)


def get_spaces_uri():
    """Return a Space's URI on the API."""
    return reverse('spaces_handler', args=[])


def get_space_uri(space):
    """Return a Space URI on the API."""
    return reverse(
        'space_handler', args=[space.id])


class TestSpacesAPI(APITestCase):

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/spaces/', get_spaces_uri())

    def test_read(self):
        for _ in range(3):
            factory.make_Space()
        uri = get_spaces_uri()
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        expected_ids = [
            space.id
            for space in Space.objects.all()
            ]
        result_ids = [
            space["id"]
            for space in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET))
            ]
        self.assertItemsEqual(expected_ids, result_ids)

    def test_create(self):
        self.become_admin()
        space_name = factory.make_name("space")
        uri = get_spaces_uri()
        response = self.client.post(uri, {
            "name": space_name,
        })
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        self.assertEqual(
            space_name,
            json.loads(
                response.content.decode(settings.DEFAULT_CHARSET))['name'])

    def test_create_admin_only(self):
        space_name = factory.make_name("space")
        uri = get_spaces_uri()
        response = self.client.post(uri, {
            "name": space_name,
        })
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content)

    def test_create_does_not_require_name(self):
        self.become_admin()
        uri = get_spaces_uri()
        response = self.client.post(uri, {})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        data = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual("space-%d" % data['id'], data['name'])


class TestSpaceAPI(APITestCase):

    def test_handler_path(self):
        space = factory.make_Space()
        self.assertEqual(
            '/api/1.0/spaces/%s/' % space.id,
            get_space_uri(space))

    def test_read(self):
        space = factory.make_Space()
        subnet_ids = [
            factory.make_Subnet(space=space).id
            for _ in range(3)
        ]
        uri = get_space_uri(space)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_space = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertThat(parsed_space, ContainsDict({
            "id": Equals(space.id),
            "name": Equals(space.get_name()),
            }))
        parsed_subnets = [
            subnet["id"]
            for subnet in parsed_space["subnets"]
        ]
        self.assertItemsEqual(subnet_ids, parsed_subnets)

    def test_read_404_when_bad_id(self):
        uri = reverse(
            'space_handler', args=[random.randint(100, 1000)])
        response = self.client.get(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content)

    def test_update(self):
        self.become_admin()
        space = factory.make_Space()
        new_name = factory.make_name("space")
        uri = get_space_uri(space)
        response = self.client.put(uri, {
            "name": new_name,
        })
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        self.assertEqual(
            new_name,
            json.loads(
                response.content.decode(settings.DEFAULT_CHARSET))['name'])
        self.assertEqual(new_name, reload_object(space).name)

    def test_update_admin_only(self):
        space = factory.make_Space()
        new_name = factory.make_name("space")
        uri = get_space_uri(space)
        response = self.client.put(uri, {
            "name": new_name,
        })
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content)

    def test_delete_deletes_space(self):
        self.become_admin()
        space = factory.make_Space()
        uri = get_space_uri(space)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(space))

    def test_delete_403_when_not_admin(self):
        space = factory.make_Space()
        uri = get_space_uri(space)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content)
        self.assertIsNotNone(reload_object(space))

    def test_delete_404_when_invalid_id(self):
        self.become_admin()
        uri = reverse(
            'space_handler', args=[random.randint(100, 1000)])
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content)
