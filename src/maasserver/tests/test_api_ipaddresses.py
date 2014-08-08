# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for IP addresses API."""

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

from django.core.urlresolvers import reverse
from maasserver.enum import (
    IPADDRESS_TYPE,
    NODEGROUP_STATUS,
    )
from maasserver.models import StaticIPAddress
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object


class TestNetworksAPI(APITestCase):

    def make_interface(self, status=NODEGROUP_STATUS.ACCEPTED, **kwargs):
        cluster = factory.make_node_group(status=status, **kwargs)
        return factory.make_node_group_interface(cluster)

    def post_reservation_request(self, net):
        params = {
            'op': 'reserve',
            'network': unicode(net),
        }
        return self.client.post(reverse('ipaddresses_handler'), params)

    def post_release_request(self, ip):
        params = {
            'op': 'release',
            'ip': ip,
        }
        return self.client.post(reverse('ipaddresses_handler'), params)

    def assertNoMatchingNetworkError(self, response, net):
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)
        self.assertEqual(
            "No network found matching %s" % unicode(net),
            response.content)

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/ipaddresses/', reverse('ipaddresses_handler'))

    def test_POST_reserve_creates_ipaddress(self):
        interface = self.make_interface()
        net = interface.network
        response = self.post_reservation_request(net)
        self.assertEqual(httplib.OK, response.status_code)
        returned_address = json.loads(response.content)
        [staticipaddress] = StaticIPAddress.objects.all()
        # We don't need to test the value of the 'created' datetime
        # field. By removing it, we also test for its presence.
        del returned_address['created']
        expected = dict(
            alloc_type=staticipaddress.alloc_type,
            ip=staticipaddress.ip,
            resource_uri=reverse('ipaddresses_handler'),
            )
        self.assertEqual(expected, returned_address)
        self.assertEqual(
            IPADDRESS_TYPE.USER_RESERVED, staticipaddress.alloc_type)
        self.assertEqual(self.logged_in_user, staticipaddress.user)

    def test_POST_reserve_errors_for_no_matching_interface(self):
        interface = self.make_interface()
        net = factory.getRandomNetwork(but_not=[interface.network])
        response = self.post_reservation_request(net)
        self.assertNoMatchingNetworkError(response, net)

    def test_POST_reserve_errors_for_interface_with_no_IP_range(self):
        interface = self.make_interface()
        net = interface.network
        interface.static_ip_range_low = None
        interface.static_ip_range_high = None
        interface.save()
        response = self.post_reservation_request(net)
        self.assertNoMatchingNetworkError(response, net)

    def test_POST_reserve_errors_for_invalid_network(self):
        net = factory.make_string()
        response = self.post_reservation_request(net)
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)
        self.assertEqual(
            "Invalid network parameter %s" % net,
            response.content)

    def test_GET_returns_ipaddresses(self):
        original_ipaddress = factory.make_staticipaddress(
            user=self.logged_in_user)
        response = self.client.get(reverse('ipaddresses_handler'))
        self.assertEqual(httplib.OK, response.status_code, response.content)

        parsed_result = json.loads(response.content)
        self.assertEqual(1, len(parsed_result), response.content)
        [returned_address] = parsed_result
        fields = {'alloc_type', 'ip'}
        self.assertEqual(
            fields.union({'resource_uri', 'created'}),
            set(returned_address.keys()))
        expected_values = {
            field: getattr(original_ipaddress, field)
            for field in fields
            if field not in ('resource_uri', 'created')
        }
        # We don't need to test the value of the 'created' datetime
        # field.
        del returned_address['created']
        expected_values['resource_uri'] = reverse('ipaddresses_handler')
        self.assertEqual(expected_values, returned_address)

    def test_GET_returns_empty_if_no_ipaddresses(self):
        response = self.client.get(reverse('ipaddresses_handler'))
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual([], json.loads(response.content))

    def test_GET_only_returns_request_users_addresses(self):
        ipaddress = factory.make_staticipaddress(user=self.logged_in_user)
        factory.make_staticipaddress(user=factory.make_user())
        response = self.client.get(reverse('ipaddresses_handler'))
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        [returned_address] = parsed_result
        self.assertEqual(ipaddress.ip, returned_address['ip'])

    def test_GET_sorts_by_id(self):
        addrs = []
        for _ in range(3):
            addrs.append(
                factory.make_staticipaddress(user=self.logged_in_user))
        response = self.client.get(reverse('ipaddresses_handler'))
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        expected = [
            addr.ip for addr in
            sorted(addrs, key=lambda addr: getattr(addr, "id"))]
        observed = [result['ip'] for result in parsed_result]
        self.assertEqual(expected, observed)

    def test_POST_release_deallocates_address(self):
        ipaddress = factory.make_staticipaddress(user=self.logged_in_user)
        response = self.post_release_request(ipaddress.ip)
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertIsNone(reload_object(ipaddress))

    def test_POST_release_does_not_delete_IP_that_I_dont_own(self):
        ipaddress = factory.make_staticipaddress(user=factory.make_user())
        response = self.post_release_request(ipaddress.ip)
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_POST_release_does_not_delete_other_IPs_I_own(self):
        ipaddress = factory.make_staticipaddress(user=self.logged_in_user)
        other_address = factory.make_staticipaddress(user=self.logged_in_user)
        response = self.post_release_request(ipaddress.ip)
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertIsNotNone(reload_object(other_address))
