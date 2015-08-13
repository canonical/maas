# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for VLAN API."""

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
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from testtools.matchers import (
    ContainsDict,
    Equals,
)


def get_vlans_uri(fabric):
    """Return a Fabric's VLAN's URI on the API."""
    return reverse('vlans_handler', args=[fabric.id])


def get_vlan_uri(vlan, fabric=None):
    """Return a Fabric VLAN URI on the API."""
    if fabric is None:
        fabric = vlan.fabric
    return reverse(
        'vlan_handler', args=[fabric.id, vlan.id])


class TestVlansAPI(APITestCase):

    def test_handler_path(self):
        fabric = factory.make_Fabric()
        self.assertEqual(
            '/api/1.0/fabrics/%s/vlans/' % (fabric.id),
            get_vlans_uri(fabric))

    def test_read(self):
        fabric = factory.make_Fabric()
        for vid in range(1, 4):
            factory.make_VLAN(vid=vid, fabric=fabric)
        uri = get_vlans_uri(fabric)
        response = self.client.get(uri)

        self.assertEqual(httplib.OK, response.status_code, response.content)
        expected_ids = [
            vlan.id
            for vlan in fabric.vlan_set.all()
            ]
        result_ids = [
            vlan["id"]
            for vlan in json.loads(response.content)
            ]
        self.assertItemsEqual(expected_ids, result_ids)


class TestVlanAPI(APITestCase):

    def test_handler_path(self):
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        self.assertEqual(
            '/api/1.0/fabrics/%s/vlans/%s/' % (
                fabric.id, vlan.id),
            get_vlan_uri(vlan))

    def test_read(self):
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        uri = get_vlan_uri(vlan)
        response = self.client.get(uri)

        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_vlan = json.loads(response.content)
        self.assertThat(parsed_vlan, ContainsDict({
            "id": Equals(vlan.id),
            "name": Equals(vlan.name),
            "vid": Equals(vlan.vid),
            "fabric": Equals(fabric.name),
            "resource_uri": Equals(get_vlan_uri(vlan)),
            }))

    def test_read_404_when_bad_id(self):
        fabric = factory.make_Fabric()
        uri = reverse(
            'vlan_handler', args=[fabric.id, random.randint(100, 1000)])
        response = self.client.get(uri)
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_delete_deletes_vlan(self):
        self.become_admin()
        vlan = factory.make_VLAN()
        uri = get_vlan_uri(vlan)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(vlan))

    def test_delete_403_when_not_admin(self):
        vlan = factory.make_VLAN()
        uri = get_vlan_uri(vlan)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)
        self.assertIsNotNone(reload_object(vlan))

    def test_delete_404_when_invalid_id(self):
        self.become_admin()
        fabric = factory.make_Fabric()
        uri = reverse(
            'vlan_handler', args=[fabric.id, random.randint(100, 1000)])
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)
