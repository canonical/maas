# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Subnet API."""

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


def get_subnets_uri():
    """Return a Subnet's URI on the API."""
    return reverse('subnets_handler', args=[])


def get_subnet_uri(subnet):
    """Return a Subnet URI on the API."""
    return reverse(
        'subnet_handler', args=[subnet.id])


class TestSubnetsAPI(APITestCase):

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/subnets/', get_subnets_uri())

    def test_read(self):
        subnets = [
            factory.make_Subnet()
            for _ in range(3)
        ]
        uri = get_subnets_uri()
        response = self.client.get(uri)

        self.assertEqual(httplib.OK, response.status_code, response.content)
        expected_ids = [
            subnet.id
            for subnet in subnets
            ]
        result_ids = [
            subnet["id"]
            for subnet in json.loads(response.content)
            ]
        self.assertItemsEqual(expected_ids, result_ids)

    def test_create(self):
        self.become_admin()
        subnet_name = factory.make_name("subnet")
        vlan = factory.make_VLAN()
        space = factory.make_Space()
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network.cidr)
        gateway_ip = factory.pick_ip_in_network(network)
        dns_servers = []
        for _ in range(2):
            dns_servers.append(
                factory.pick_ip_in_network(
                    network, but_not=[gateway_ip] + dns_servers))
        uri = get_subnets_uri()
        response = self.client.post(uri, {
            "name": subnet_name,
            "vlan": vlan.id,
            "space": space.id,
            "cidr": cidr,
            "gateway_ip": gateway_ip,
            "dns_servers": ','.join(dns_servers),
        })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        created_subnet = json.loads(response.content)
        self.assertEqual(subnet_name, created_subnet['name'])
        self.assertEqual(vlan.id, created_subnet['vlan']['id'])
        self.assertEqual(space.name, created_subnet['space'])
        self.assertEqual(cidr, created_subnet['cidr'])
        self.assertEqual(gateway_ip, created_subnet['gateway_ip'])
        self.assertEqual(dns_servers, created_subnet['dns_servers'])

    def test_create_admin_only(self):
        subnet_name = factory.make_name("subnet")
        uri = get_subnets_uri()
        response = self.client.post(uri, {
            "name": subnet_name,
        })
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_create_requires_name_vlan_space_cidr(self):
        self.become_admin()
        uri = get_subnets_uri()
        response = self.client.post(uri, {})
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)
        self.assertEqual({
            "cidr": ["This field is required."],
            }, json.loads(response.content))


class TestSubnetAPI(APITestCase):

    def test_handler_path(self):
        subnet = factory.make_Subnet()
        self.assertEqual(
            '/api/1.0/subnets/%s/' % subnet.id,
            get_subnet_uri(subnet))

    def test_read(self):
        subnet = factory.make_Subnet()
        uri = get_subnet_uri(subnet)
        response = self.client.get(uri)

        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_subnet = json.loads(response.content)
        self.assertThat(parsed_subnet, ContainsDict({
            "id": Equals(subnet.id),
            "name": Equals(subnet.name),
            "vlan": ContainsDict({
                "id": Equals(subnet.vlan.id),
                }),
            "space": Equals(subnet.space.name),
            "cidr": Equals(subnet.cidr),
            "gateway_ip": Equals(subnet.gateway_ip),
            "dns_servers": Equals(subnet.dns_servers),
            }))

    def test_read_404_when_bad_id(self):
        uri = reverse(
            'subnet_handler', args=[random.randint(100, 1000)])
        response = self.client.get(uri)
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_update(self):
        self.become_admin()
        subnet = factory.make_Subnet()
        new_name = factory.make_name("subnet")
        uri = get_subnet_uri(subnet)
        response = self.client.put(uri, {
            "name": new_name,
        })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual(new_name, json.loads(response.content)['name'])
        self.assertEqual(new_name, reload_object(subnet).name)

    def test_update_admin_only(self):
        subnet = factory.make_Subnet()
        new_name = factory.make_name("subnet")
        uri = get_subnet_uri(subnet)
        response = self.client.put(uri, {
            "name": new_name,
        })
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_delete_deletes_subnet(self):
        self.become_admin()
        subnet = factory.make_Subnet()
        uri = get_subnet_uri(subnet)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(subnet))

    def test_delete_403_when_not_admin(self):
        subnet = factory.make_Subnet()
        uri = get_subnet_uri(subnet)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)
        self.assertIsNotNone(reload_object(subnet))

    def test_delete_404_when_invalid_id(self):
        self.become_admin()
        uri = reverse(
            'subnet_handler', args=[random.randint(100, 1000)])
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)
