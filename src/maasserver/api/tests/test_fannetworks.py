# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for FanNetwork API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import json
import random

from django.core.urlresolvers import reverse
from maasserver.models.fannetwork import FanNetwork
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from testtools.matchers import (
    ContainsDict,
    Equals,
)


def get_fannetworks_uri():
    """Return a FanNetwork's URI on the API."""
    return reverse('fannetworks_handler', args=[])


def get_fannetwork_uri(fannetwork):
    """Return a FanNetwork URI on the API."""
    return reverse(
        'fannetwork_handler', args=[fannetwork.id])


class TestFanNetworksAPI(APITestCase):

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/fannetworks/', get_fannetworks_uri())

    def test_read(self):
        # Create specific fan networks so creation doesn't fail because of
        # randomness. Reported in bug lp:1512832.
        factory.make_FanNetwork(overlay="10.0.0.0/8", underlay="172.16.0.0/16")
        factory.make_FanNetwork(overlay="11.0.0.0/8", underlay="172.17.0.0/16")
        factory.make_FanNetwork(overlay="12.0.0.0/8", underlay="172.18.0.0/16")
        uri = get_fannetworks_uri()
        response = self.client.get(uri)

        self.assertEqual(httplib.OK, response.status_code, response.content)
        expected_ids = [
            fannetwork.id
            for fannetwork in FanNetwork.objects.all()
            ]
        result_ids = [
            fannetwork["id"]
            for fannetwork in json.loads(response.content)
            ]
        self.assertItemsEqual(expected_ids, result_ids)

    def test_create(self):
        self.become_admin()
        fannetwork_name = factory.make_name("fannetwork")
        uri = get_fannetworks_uri()
        slash = random.randint(12, 28)
        underlay = factory.make_ipv4_network(slash=slash)
        overlay = factory.make_ipv4_network(slash=slash - 4)
        response = self.client.post(uri, {
            "name": fannetwork_name,
            "underlay": unicode(underlay),
            "overlay": unicode(overlay),
        })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual(fannetwork_name, json.loads(response.content)['name'])
        self.assertEqual(
            unicode(underlay), json.loads(response.content)['underlay'])
        self.assertEqual(
            unicode(overlay), json.loads(response.content)['overlay'])

    def test_create_admin_only(self):
        fannetwork_name = factory.make_name("fannetwork")
        uri = get_fannetworks_uri()
        slash = random.randint(12, 28)
        underlay = factory.make_ipv4_network(slash=slash)
        overlay = factory.make_ipv4_network(slash=slash - 4)
        response = self.client.post(uri, {
            "name": fannetwork_name,
            "underlay": unicode(underlay),
            "overlay": unicode(overlay),
        })
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_create_requires_fields(self):
        self.become_admin()
        uri = get_fannetworks_uri()
        response = self.client.post(uri, {})
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)
        self.assertEqual({
            "name": ["This field is required."],
            "overlay": ["This field is required."],
            "underlay": ["This field is required."],
            }, json.loads(response.content))


class TestFanNetworkAPI(APITestCase):

    def test_handler_path(self):
        fannetwork = factory.make_FanNetwork()
        self.assertEqual(
            '/api/1.0/fannetworks/%s/' % fannetwork.id,
            get_fannetwork_uri(fannetwork))

    def test_read(self):
        fannetwork = factory.make_FanNetwork()
        uri = get_fannetwork_uri(fannetwork)
        response = self.client.get(uri)

        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_fannetwork = json.loads(response.content)
        self.assertThat(parsed_fannetwork, ContainsDict({
            "id": Equals(fannetwork.id),
            "name": Equals(fannetwork.name),
            }))

    def test_read_404_when_bad_id(self):
        uri = reverse(
            'fannetwork_handler', args=[random.randint(100, 1000)])
        response = self.client.get(uri)
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_update(self):
        self.become_admin()
        fannetwork = factory.make_FanNetwork()
        new_name = factory.make_name("fannetwork")
        uri = get_fannetwork_uri(fannetwork)
        response = self.client.put(uri, {
            "name": new_name,
        })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual(new_name, json.loads(response.content)['name'])
        self.assertEqual(new_name, reload_object(fannetwork).name)

    def test_update_admin_only(self):
        fannetwork = factory.make_FanNetwork()
        new_name = factory.make_name("fannetwork")
        uri = get_fannetwork_uri(fannetwork)
        response = self.client.put(uri, {
            "name": new_name,
        })
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_delete_deletes_fannetwork(self):
        self.become_admin()
        fannetwork = factory.make_FanNetwork()
        uri = get_fannetwork_uri(fannetwork)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(fannetwork))

    def test_delete_403_when_not_admin(self):
        fannetwork = factory.make_FanNetwork()
        uri = get_fannetwork_uri(fannetwork)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)
        self.assertIsNotNone(reload_object(fannetwork))

    def test_delete_404_when_invalid_id(self):
        self.become_admin()
        uri = reverse(
            'fannetwork_handler', args=[random.randint(100, 1000)])
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)
