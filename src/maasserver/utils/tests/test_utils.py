# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for miscellaneous helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from urllib import urlencode

from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpRequest
from django.test.client import RequestFactory
from maasserver.enum import (
    NODE_STATUS_CHOICES,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.models import (
    NodeGroup,
    nodegroupinterface,
    NodeGroupInterface,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase as DjangoTestCase
from maasserver.utils import (
    absolute_reverse,
    build_absolute_uri,
    find_nodegroup,
    get_db_state,
    map_enum,
    strip_domain,
    )
from maastesting.testcase import TestCase
from netaddr import IPNetwork


class TestEnum(TestCase):

    def test_map_enum_includes_all_enum_values(self):

        class Enum:
            ONE = 1
            TWO = 2

        self.assertItemsEqual(['ONE', 'TWO'], map_enum(Enum).keys())

    def test_map_enum_omits_private_or_special_methods(self):

        class Enum:
            def __init__(self):
                pass

            def __repr__(self):
                return "Enum"

            def _save(self):
                pass

            VALUE = 9

        self.assertItemsEqual(['VALUE'], map_enum(Enum).keys())

    def test_map_enum_maps_values(self):

        class Enum:
            ONE = 1
            THREE = 3

        self.assertEqual({'ONE': 1, 'THREE': 3}, map_enum(Enum))


class TestAbsoluteReverse(DjangoTestCase):

    def test_absolute_reverse_uses_DEFAULT_MAAS_URL_by_default(self):
        maas_url = 'http://%s' % factory.getRandomString()
        self.patch(settings, 'DEFAULT_MAAS_URL', maas_url)
        absolute_url = absolute_reverse('settings')
        expected_url = settings.DEFAULT_MAAS_URL + reverse('settings')
        self.assertEqual(expected_url, absolute_url)

    def test_absolute_reverse_uses_given_base_url(self):
        maas_url = 'http://%s' % factory.getRandomString()
        absolute_url = absolute_reverse('settings', base_url=maas_url)
        expected_url = maas_url + reverse('settings')
        self.assertEqual(expected_url, absolute_url)

    def test_absolute_reverse_uses_query_string(self):
        self.patch(settings, 'DEFAULT_MAAS_URL', '')
        parameters = {factory.getRandomString(): factory.getRandomString()}
        absolute_url = absolute_reverse('settings', query=parameters)
        expected_url = '%s?%s' % (reverse('settings'), urlencode(parameters))
        self.assertEqual(expected_url, absolute_url)

    def test_absolute_reverse_uses_kwargs(self):
        node = factory.make_node()
        self.patch(settings, 'DEFAULT_MAAS_URL', '')
        absolute_url = absolute_reverse(
            'node-view', kwargs={'system_id': node.system_id})
        expected_url = reverse('node-view', args=[node.system_id])
        self.assertEqual(expected_url, absolute_url)

    def test_absolute_reverse_uses_args(self):
        node = factory.make_node()
        self.patch(settings, 'DEFAULT_MAAS_URL', '')
        absolute_url = absolute_reverse('node-view', args=[node.system_id])
        expected_url = reverse('node-view', args=[node.system_id])
        self.assertEqual(expected_url, absolute_url)


class GetDbStateTest(DjangoTestCase):
    """Testing for the method `get_db_state`."""

    def test_get_db_state_returns_db_state(self):
        status = factory.getRandomChoice(NODE_STATUS_CHOICES)
        node = factory.make_node(status=status)
        another_status = factory.getRandomChoice(
            NODE_STATUS_CHOICES, but_not=[status])
        node.status = another_status
        self.assertEqual(status, get_db_state(node, 'status'))


class TestBuildAbsoluteURI(TestCase):
    """Tests for `build_absolute_uri`."""

    def make_request(self, host="example.com", port=80, script_name="",
                     is_secure=False):
        """Return a :class:`HttpRequest` with the given parameters."""
        request = HttpRequest()
        request.META["SERVER_NAME"] = host
        request.META["SERVER_PORT"] = port
        request.META["SCRIPT_NAME"] = script_name
        request.is_secure = lambda: is_secure
        return request

    def test_simple(self):
        request = self.make_request()
        self.assertEqual(
            "http://example.com/fred",
            build_absolute_uri(request, "/fred"))

    def test_different_port(self):
        request = self.make_request(port=1234)
        self.assertEqual(
            "http://example.com:1234/fred",
            build_absolute_uri(request, "/fred"))

    def test_script_name_is_ignored(self):
        # The given path already includes the script_name, so the
        # script_name passed in the request is not included again.
        request = self.make_request(script_name="/foo/bar")
        self.assertEqual(
            "http://example.com/foo/bar/fred",
            build_absolute_uri(request, "/foo/bar/fred"))

    def test_secure(self):
        request = self.make_request(port=443, is_secure=True)
        self.assertEqual(
            "https://example.com/fred",
            build_absolute_uri(request, "/fred"))

    def test_different_port_and_secure(self):
        request = self.make_request(port=9443, is_secure=True)
        self.assertEqual(
            "https://example.com:9443/fred",
            build_absolute_uri(request, "/fred"))

    def test_preserve_two_leading_slashes(self):
        # Whilst this shouldn't ordinarily happen, two leading slashes in the
        # path should be preserved, and not treated specially.
        request = self.make_request()
        self.assertEqual(
            "http://example.com//foo",
            build_absolute_uri(request, "//foo"))


class TestStripDomain(TestCase):

    def test_strip_domain(self):
        input_and_results = [
            ('name.domain',  'name'),
            ('name', 'name'),
            ('name.domain.what', 'name'),
            ('name..domain', 'name'),
            ]
        inputs = [input for input, _ in input_and_results]
        results = [result for _, result in input_and_results]
        self.assertEqual(results, map(strip_domain, inputs))


def get_request(origin_ip):
    return RequestFactory().post('/', REMOTE_ADDR=origin_ip)


class TestFindNodegroup(DjangoTestCase):

    def test_finds_nodegroup_by_network_address(self):
        nodegroup = factory.make_node_group(
            network=IPNetwork("192.168.28.1/24"))
        self.assertEqual(
            nodegroup,
            find_nodegroup(get_request('192.168.28.0')))

    def test_find_nodegroup_looks_up_nodegroup_by_controller_ip(self):
        nodegroup = factory.make_node_group()
        ip = nodegroup.get_managed_interface().ip
        self.assertEqual(
            nodegroup,
            find_nodegroup(get_request(ip)))

    def test_find_nodegroup_looks_up_only_configured_interfaces(self):
        network = IPNetwork("192.168.41.0/24")
        factory.make_node_group(
            network=network,
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        ip = factory.getRandomIPInNetwork(network)
        self.assertIsNone(find_nodegroup(get_request(ip)))

    def test_find_nodegroup_accepts_any_ip_in_nodegroup_subnet(self):
        nodegroup = factory.make_node_group(
            network=IPNetwork("192.168.41.0/24"))
        self.assertEqual(
            nodegroup,
            find_nodegroup(get_request('192.168.41.199')))

    def test_find_nodegroup_returns_None_if_not_found(self):
        self.assertIsNone(
            find_nodegroup(get_request(factory.getRandomIPAddress())))

    def test_find_nodegroup_errors_if_multiple_matches(self):
        self.patch(nodegroupinterface, "MINIMUM_NETMASK_BITS", 1)
        factory.make_node_group(network=IPNetwork("10/8"))
        factory.make_node_group(network=IPNetwork("10.1.1/24"))
        self.assertRaises(
            NodeGroup.MultipleObjectsReturned,
            find_nodegroup, get_request('10.1.1.2'))

    def test_find_nodegroup_handles_multiple_matches_on_same_nodegroup(self):
        self.patch(nodegroupinterface, "MINIMUM_NETMASK_BITS", 1)
        nodegroup = factory.make_node_group(network=IPNetwork("10/8"))
        NodeGroupInterface.objects.create(
            nodegroup=nodegroup, ip='10.0.0.2', subnet_mask='255.0.0.0',
            broadcast_ip='10.0.0.1', interface='eth71')
        NodeGroupInterface.objects.create(
            nodegroup=nodegroup, ip='10.0.0.3', subnet_mask='255.0.0.0',
            broadcast_ip='10.0.0.2', interface='eth72')
        self.assertEqual(nodegroup, find_nodegroup(get_request('10.0.0.9')))
