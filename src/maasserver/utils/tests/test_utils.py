# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for miscellaneous helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import threading
from urllib import urlencode
from urlparse import (
    urljoin,
    urlparse,
)

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.http import HttpRequest
from django.test.client import RequestFactory
from maasserver.enum import (
    NODE_STATUS_CHOICES,
    NODEGROUPINTERFACE_MANAGEMENT,
)
from maasserver.exceptions import NodeGroupMisconfiguration
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import (
    absolute_reverse,
    absolute_url_reverse,
    build_absolute_uri,
    find_nodegroup,
    get_db_state,
    get_local_cluster_UUID,
    make_validation_error_message,
    strip_domain,
    synchronised,
)
from maastesting.testcase import MAASTestCase
from mock import sentinel
from netaddr import IPAddress


class TestAbsoluteReverse(MAASServerTestCase):

    def expected_from_maas_url_and_reverse(self, maas_url, reversed_url):
        # We need to remove the leading '/' from the reversed url, or
        # urljoin won't actually join.
        return urljoin(maas_url, reversed_url.lstrip("/"))

    def test_absolute_reverse_uses_maas_url_by_default(self):
        maas_url = factory.make_simple_http_url(path='')
        self.useFixture(RegionConfigurationFixture(maas_url=maas_url))
        absolute_url = absolute_reverse('settings')
        expected_url = self.expected_from_maas_url_and_reverse(
            maas_url, reverse('settings'))
        self.assertEqual(expected_url, absolute_url)

    def test_absolute_reverse_uses_given_base_url(self):
        maas_url = factory.make_simple_http_url()
        absolute_url = absolute_reverse('settings', base_url=maas_url)
        expected_url = self.expected_from_maas_url_and_reverse(
            maas_url,
            reverse('settings'))
        self.assertEqual(expected_url, absolute_url)

    def test_absolute_reverse_uses_query_string(self):
        maas_url = factory.make_simple_http_url()
        self.useFixture(RegionConfigurationFixture(maas_url=maas_url))

        parameters = {factory.make_string(): factory.make_string()}
        absolute_url = absolute_reverse('settings', query=parameters)
        reversed_url = '%s?%s' % (reverse('settings'), urlencode(parameters))
        expected_url = self.expected_from_maas_url_and_reverse(
            maas_url,
            reversed_url)
        self.assertEqual(expected_url, absolute_url)

    def test_absolute_reverse_uses_kwargs(self):
        maas_url = factory.make_simple_http_url()
        nodegroup = factory.make_NodeGroup()
        self.useFixture(RegionConfigurationFixture(maas_url=maas_url))
        absolute_url = absolute_reverse(
            'cluster-edit', kwargs={'uuid': nodegroup.uuid})
        reversed_url = reverse('cluster-edit', args=[nodegroup.uuid])
        expected_url = self.expected_from_maas_url_and_reverse(
            maas_url,
            reversed_url)
        self.assertEqual(expected_url, absolute_url)

    def test_absolute_reverse_uses_args(self):
        nodegroup = factory.make_NodeGroup()
        maas_url = factory.make_simple_http_url()
        self.useFixture(RegionConfigurationFixture(maas_url=maas_url))

        observed_url = absolute_reverse('cluster-edit', args=[nodegroup.uuid])

        reversed_url = reverse('cluster-edit', args=[nodegroup.uuid])
        expected_url = self.expected_from_maas_url_and_reverse(
            maas_url,
            reversed_url)
        self.assertEqual(expected_url, observed_url)


class TestAbsoluteUrlReverse(MAASServerTestCase):

    def setUp(self):
        super(TestAbsoluteUrlReverse, self).setUp()
        self.useFixture(RegionConfigurationFixture())

    def test_absolute_url_reverse_uses_path_from_maas_url(self):
        maas_url = factory.make_simple_http_url()
        self.useFixture(RegionConfigurationFixture(maas_url=maas_url))
        path = urlparse(maas_url).path
        absolute_url = absolute_url_reverse('settings')
        expected_url = path + reverse('settings')
        self.assertEqual(expected_url, absolute_url)

    def test_absolute_url_reverse_copes_with_trailing_slash(self):
        maas_url = factory.make_simple_http_url()
        path = urlparse(maas_url).path + '/'
        self.useFixture(RegionConfigurationFixture(maas_url=maas_url))
        absolute_url = absolute_url_reverse('settings')
        expected_url = path[:-1] + reverse('settings')
        self.assertEqual(expected_url, absolute_url)

    def test_absolute_url_reverse_uses_query_string(self):
        maas_url = factory.make_simple_http_url()
        path = urlparse(maas_url).path
        self.useFixture(RegionConfigurationFixture(maas_url=maas_url))
        parameters = {factory.make_string(): factory.make_string()}
        absolute_url = absolute_url_reverse('settings', query=parameters)
        expected_url = path + "%s?%s" % (
            reverse('settings'), urlencode(parameters))
        self.assertEqual(expected_url, absolute_url)


class GetDbStateTest(MAASServerTestCase):
    """Testing for the method `get_db_state`."""

    def test_get_db_state_returns_db_state(self):
        status = factory.pick_choice(NODE_STATUS_CHOICES)
        node = factory.make_Node(status=status)
        another_status = factory.pick_choice(
            NODE_STATUS_CHOICES, but_not=[status])
        node.status = another_status
        self.assertEqual(status, get_db_state(node, 'status'))


class TestBuildAbsoluteURI(MAASTestCase):
    """Tests for `build_absolute_uri`."""

    def setUp(self):
        super(TestBuildAbsoluteURI, self).setUp()
        self.useFixture(RegionConfigurationFixture())

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


class TestStripDomain(MAASTestCase):

    def test_strip_domain(self):
        input_and_results = [
            ('name.domain', 'name'),
            ('name', 'name'),
            ('name.domain.what', 'name'),
            ('name..domain', 'name'),
            ]
        inputs = [input for input, _ in input_and_results]
        results = [result for _, result in input_and_results]
        self.assertEqual(results, map(strip_domain, inputs))


class TestGetLocalClusterUUID(MAASTestCase):

    def test_get_local_cluster_UUID_returns_None_if_no_config_file(self):
        bogus_file_name = '/tmp/bogus/%s' % factory.make_name('name')
        self.patch(settings, 'LOCAL_CLUSTER_CONFIG', bogus_file_name)
        self.assertIsNone(get_local_cluster_UUID())

    def test_get_local_cluster_UUID_returns_None_if_parsing_fails(self):
        file_name = self.make_file(contents="wrong content")
        self.patch(settings, 'LOCAL_CLUSTER_CONFIG', file_name)
        self.assertIsNone(get_local_cluster_UUID())

    def test_get_local_cluster_UUID_returns_cluster_UUID(self):
        uuid = factory.make_UUID()
        file_name = self.make_file(contents='CLUSTER_UUID="%s"' % uuid)
        self.patch(settings, 'LOCAL_CLUSTER_CONFIG', file_name)
        self.assertEqual(uuid, get_local_cluster_UUID())


def make_request(origin_ip):
    """Return a fake HTTP request with the given remote address."""
    return RequestFactory().post('/', REMOTE_ADDR=unicode(origin_ip))


class TestFindNodegroup(MAASServerTestCase):

    scenarios = [
        ('ipv4', {'network_factory': factory.make_ipv4_network}),
        ('ipv6', {'network_factory': factory.make_ipv6_network}),
        ]

    def make_cluster_interface(self, network, management=None):
        """Create a cluster interface.

        The interface is managed by default.
        """
        if management is None:
            management = factory.pick_enum(
                NODEGROUPINTERFACE_MANAGEMENT,
                but_not=[NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED])
        cluster = factory.make_NodeGroup()
        return factory.make_NodeGroupInterface(
            cluster, network=network, management=management)

    def test_find_nodegroup_looks_up_nodegroup_by_controller_ip(self):
        nodegroup = factory.make_NodeGroup()
        interface = factory.make_NodeGroupInterface(nodegroup)
        self.assertEqual(
            nodegroup,
            find_nodegroup(make_request(interface.ip)))

    def test_find_nodegroup_returns_None_if_not_found(self):
        requesting_ip = factory.pick_ip_in_network(self.network_factory())
        self.assertIsNone(find_nodegroup(make_request(requesting_ip)))

    #
    # Finding a node's nodegroup (aka cluster controller) in a nutshell:
    #
    #   when 1 managed interface on the network = choose this one
    #   when >1 managed interfaces on the network = misconfiguration
    #   when 1 unmanaged interface on a network = choose this one
    #   when >1 unmanaged interfaces on a network = choose any
    #

    def test_1_managed_interface(self):
        network = self.network_factory()
        interface = self.make_cluster_interface(network)
        self.assertEqual(
            interface.nodegroup,
            find_nodegroup(
                make_request(factory.pick_ip_in_network(network))))

    def test_1_managed_interface_and_1_unmanaged(self):
        # The managed nodegroup is chosen in preference to the unmanaged
        # nodegroup.
        network = self.network_factory()
        interface = self.make_cluster_interface(network)
        self.make_cluster_interface(
            network, management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        self.assertEqual(
            interface.nodegroup,
            find_nodegroup(
                make_request(factory.pick_ip_in_network(network))))

    def test_more_than_1_managed_interface(self):
        network = self.network_factory()
        requesting_ip = factory.pick_ip_in_network(network)
        self.make_cluster_interface(network=network)
        self.make_cluster_interface(network=network)
        exception = self.assertRaises(
            NodeGroupMisconfiguration,
            find_nodegroup, make_request(requesting_ip))
        self.assertEqual(
            (httplib.CONFLICT,
             "Multiple clusters on the same network; only "
             "one cluster may manage the network of which "
             "%s is a member." % requesting_ip),
            (exception.api_error,
             "%s" % exception))

    def test_1_unmanaged_interface(self):
        network = self.network_factory()
        interface = self.make_cluster_interface(network)
        self.assertEqual(
            interface.nodegroup,
            find_nodegroup(
                make_request(factory.pick_ip_in_network(network))))

    def test_more_than_1_unmanaged_interface(self):
        network = self.network_factory()
        interfaces = [
            self.make_cluster_interface(
                network, management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
            for _ in range(2)
            ]
        self.assertEqual(
            interfaces[0].nodegroup,
            find_nodegroup(
                make_request(factory.pick_ip_in_network(network))))

    def test_handles_mixed_IPv4_and_IPv6(self):
        matching_network = self.network_factory()
        requesting_ip = factory.pick_ip_in_network(matching_network)
        self.make_cluster_interface(factory.make_ipv4_network())
        self.make_cluster_interface(factory.make_ipv6_network())
        matching_interface = self.make_cluster_interface(matching_network)
        self.assertEqual(
            matching_interface.nodegroup,
            find_nodegroup(make_request(requesting_ip)))

    def test_includes_lower_bound(self):
        network = self.network_factory()
        interface = self.make_cluster_interface(network)
        self.assertEqual(
            interface.nodegroup,
            find_nodegroup(make_request(IPAddress(network.first))))

    def test_includes_upper_bound(self):
        network = self.network_factory()
        interface = self.make_cluster_interface(network)
        self.assertEqual(
            interface.nodegroup,
            find_nodegroup(make_request(IPAddress(network.last))))

    def test_excludes_lower_bound_predecessor(self):
        network = self.network_factory()
        self.make_cluster_interface(network)
        self.assertIsNone(
            find_nodegroup(make_request(IPAddress(network.first - 1))))

    def test_excludes_upper_bound_successor(self):
        network = self.network_factory()
        self.make_cluster_interface(network)
        self.assertIsNone(
            find_nodegroup(make_request(IPAddress(network.last + 1))))


class TestSynchronised(MAASTestCase):

    def test_locks_when_calling(self):
        lock = threading.Lock()

        @synchronised(lock)
        def example_synchronised_function():
            self.assertTrue(lock.locked())
            return sentinel.called

        self.assertFalse(lock.locked())
        self.assertEqual(sentinel.called, example_synchronised_function())
        self.assertFalse(lock.locked())


class TestMakeValidationErrorMessage(MAASTestCase):

    def test__formats_message_with_all_errors(self):
        error = ValidationError({
            "foo": [ValidationError("bar")],
            "alice": [ValidationError("bob")],
            "__all__": ["all is lost"],
        })
        self.assertEqual(
            "* all is lost\n"
            "* alice: bob\n"
            "* foo: bar",
            make_validation_error_message(error))
