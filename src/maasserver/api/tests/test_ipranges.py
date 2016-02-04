# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for IPRange API."""

__all__ = []

import http.client
import json
import random

from django.conf import settings
from django.core.urlresolvers import reverse
from maasserver.models.iprange import IPRange
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from testtools.matchers import (
    ContainsDict,
    Equals,
)


def get_ipranges_uri():
    """Return a Space's URI on the API."""
    return reverse('ipranges_handler', args=[])


def get_iprange_uri(iprange):
    """Return a Space URI on the API."""
    return reverse(
        'iprange_handler', args=[iprange.id])


class TestIPRangesAPI(APITestCase):

    def test_handler_path(self):
        self.assertEqual(
            '/api/2.0/ipranges/', get_ipranges_uri())

    def test_read(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        factory.make_IPRange(subnet, '10.0.0.1', '10.0.0.10')
        factory.make_IPRange(subnet, '10.0.0.11', '10.0.0.20')
        factory.make_IPRange(subnet, '10.0.0.21', '10.0.0.30')
        uri = get_ipranges_uri()
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        expected_ids = [
            iprange.id
            for iprange in IPRange.objects.all()
            ]
        result_ids = [
            iprange["id"]
            for iprange in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET))
            ]
        self.assertItemsEqual(expected_ids, result_ids)

    def test_create(self):
        self.become_admin()
        uri = get_ipranges_uri()
        subnet = factory.make_Subnet(cidr='10.0.0.0/24')
        response = self.client.post(uri, {
            "type": "dynamic",
            "start_ip": "10.0.0.10",
            "end_ip": "10.0.0.20",
            "subnet": "%d" % subnet.id,
        })
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        data = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertThat(data['start_ip'], Equals('10.0.0.10'))
        self.assertThat(data['end_ip'], Equals('10.0.0.20'))
        self.assertThat(data['subnet']['id'], Equals(subnet.id))

    def test_create_does_not_require_subnet(self):
        self.become_admin()
        uri = get_ipranges_uri()
        subnet = factory.make_Subnet(cidr='10.0.0.0/24')
        response = self.client.post(uri, {
            "type": "dynamic",
            "start_ip": "10.0.0.10",
            "end_ip": "10.0.0.20",
        })
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        data = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertThat(data['start_ip'], Equals('10.0.0.10'))
        self.assertThat(data['end_ip'], Equals('10.0.0.20'))
        self.assertThat(data['subnet']['id'], Equals(subnet.id))


class TestIPRangeAPI(APITestCase):

    def test_handler_path(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        iprange = factory.make_IPRange(subnet, '10.0.0.1', '10.0.0.10')
        self.assertEqual(
            '/api/2.0/ipranges/%s/' % iprange.id,
            get_iprange_uri(iprange))

    def test_read(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        iprange = factory.make_IPRange(subnet, '10.0.0.1', '10.0.0.10')
        factory.make_IPRange(subnet, '10.0.0.11', '10.0.0.20')
        factory.make_IPRange(subnet, '10.0.0.21', '10.0.0.30')
        uri = get_iprange_uri(iprange)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_ipranges = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertThat(parsed_ipranges, ContainsDict({
            "id": Equals(iprange.id),
            "start_ip": Equals(iprange.start_ip),
            "end_ip": Equals(iprange.end_ip),
            "comment": Equals(iprange.comment),
            "type": Equals(iprange.type),
            "user": Equals(iprange.user),
            }))

    def test_read_404_when_bad_id(self):
        uri = reverse(
            'iprange_handler', args=[random.randint(10000, 20000)])
        response = self.client.get(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content)

    def test_update(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        iprange = factory.make_IPRange(subnet, '10.0.0.1', '10.0.0.10')
        uri = get_iprange_uri(iprange)
        comment = factory.make_name("comment")
        response = self.client.put(uri, {
            "comment": comment,
        })
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        self.assertEqual(
            comment,
            json.loads(
                response.content.decode(settings.DEFAULT_CHARSET))['comment'])
        self.assertEqual(comment, reload_object(iprange).comment)

    def test_delete_deletes_iprange(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        iprange = factory.make_IPRange(subnet, '10.0.0.1', '10.0.0.10')
        uri = get_iprange_uri(iprange)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(iprange))

    def test_delete_404_when_invalid_id(self):
        uri = reverse(
            'iprange_handler', args=[random.randint(100, 1000)])
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content)
