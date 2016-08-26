# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Neighbours API."""

__all__ = []

from datetime import datetime
import http.client
import json
import random

from django.conf import settings
from django.core.urlresolvers import reverse
from maasserver.models.neighbour import Neighbour
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from testtools.matchers import (
    Equals,
    HasLength,
)


def get_neighbours_uri():
    """Return a Neighbour's URI on the API."""
    return reverse('neighbours_handler', args=[])


def get_neighbour_uri(neighbour):
    """Return a Neighbour URI on the API."""
    return reverse(
        'neighbour_handler', args=[neighbour.id])


def get_neighbour_uri_by_specifiers(specifiers):
    """Return a Neighbour URI on the API."""
    return reverse(
        'neighbour_handler', args=[specifiers])


def make_neighbours(count=3, interface=None):
    return [
        factory.make_Neighbour(
            interface=interface, time=time,
            updated=datetime.fromtimestamp(time))
        for time in range(count)
        ]


class TestNeighboursAPI(APITestCase.ForUser):

    def test_handler_path(self):
        self.assertEqual(
            '/api/2.0/neighbours/', get_neighbours_uri())

    def test_read(self):
        rack = factory.make_RackController()
        iface = rack.interface_set.first()
        neighbours = make_neighbours(interface=iface)
        uri = get_neighbours_uri()
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        results = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertThat(results, HasLength(3))
        expected_ids = [neighbour.id for neighbour in neighbours]
        result_ids = [neighbour["id"] for neighbour in results]
        self.assertItemsEqual(expected_ids, result_ids)

    def test_read_sorts_by_last_seen(self):
        rack = factory.make_RackController()
        iface = rack.interface_set.first()
        make_neighbours(interface=iface)
        uri = get_neighbours_uri()
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        results = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertTrue(results[0]['time'] < results[2]['time'])
        self.assertTrue(results[0]['time'] < results[1]['time'])
        self.assertTrue(results[1]['time'] < results[2]['time'])


class TestNeighbourAPI(APITestCase.ForUser):

    def test_handler_path(self):
        neighbour = factory.make_Neighbour()
        self.assertEqual(
            '/api/2.0/neighbours/%s/' % neighbour.id,
            get_neighbour_uri(neighbour))

    def test_read(self):
        rack = factory.make_RackController()
        iface = rack.interface_set.first()
        neighbours = make_neighbours(interface=iface)
        neighbour = neighbours[1]
        uri = get_neighbour_uri(neighbour)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        # Spot check expected values in the results
        self.assertThat(
            result["resource_uri"],
            Equals(get_neighbour_uri(neighbour)))
        self.assertThat(
            result["system_id"],
            Equals(rack.system_id))
        self.assertThat(
            result["ifname"],
            Equals(iface.name))
        self.assertThat(
            result["ip"],
            Equals(neighbour.ip))
        self.assertThat(
            result["count"],
            Equals(neighbour.count))
        self.assertThat(
            result["mac_address"],
            Equals(neighbour.mac_address))
        self.assertThat(
            result["time"],
            Equals(neighbour.time))

    def test_read_by_specifiers(self):
        rack = factory.make_RackController()
        iface = rack.interface_set.first()
        [neighbour] = make_neighbours(interface=iface, count=1)
        uri = get_neighbour_uri_by_specifiers("ip:" + str(neighbour.ip))
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertThat(
            result["ip"],
            Equals(neighbour.ip))

    def test_read_404_when_bad_id(self):
        uri = reverse(
            'neighbour_handler', args=[random.randint(10000, 20000)])
        response = self.client.get(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content)

    def test_update_not_allowed(self):
        rack = factory.make_RackController()
        iface = rack.interface_set.first()
        neighbours = make_neighbours(interface=iface)
        neighbour = neighbours[1]
        uri = get_neighbour_uri(neighbour)
        response = self.client.put(uri, {
            "ip": factory.make_ip_address(),
        })
        self.assertEqual(
            http.client.METHOD_NOT_ALLOWED, response.status_code,
            response.content)

    def test_delete_allowed_for_admin(self):
        self.become_admin()
        rack = factory.make_RackController()
        iface = rack.interface_set.first()
        neighbours = make_neighbours(interface=iface, count=3)
        neighbour = neighbours[1]
        uri = get_neighbour_uri(neighbour)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content)
        # Neighbour should be gone now.
        self.assertThat(Neighbour.objects.count(), Equals(2))

    def test_delete_not_allowed_for_non_admin(self):
        rack = factory.make_RackController()
        iface = rack.interface_set.first()
        neighbours = make_neighbours(interface=iface, count=3)
        neighbour = neighbours[1]
        uri = get_neighbour_uri(neighbour)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content)
