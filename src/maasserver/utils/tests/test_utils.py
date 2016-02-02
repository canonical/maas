# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for miscellaneous helpers."""

__all__ = []

import threading
from urllib.parse import (
    urlencode,
    urljoin,
    urlparse,
)

from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.http import HttpRequest
from django.test.client import RequestFactory
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import (
    absolute_reverse,
    absolute_url_reverse,
    build_absolute_uri,
    find_rack_controller,
    get_local_cluster_UUID,
    make_validation_error_message,
    strip_domain,
    synchronised,
)
from maastesting.testcase import MAASTestCase
from mock import sentinel
from provisioningserver.testing.config import ClusterConfigurationFixture


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
        user = factory.make_User()
        self.useFixture(RegionConfigurationFixture(maas_url=maas_url))
        absolute_url = absolute_reverse(
            'accounts-edit', kwargs={'username': user.username})
        reversed_url = reverse('accounts-edit', args=[user.username])
        expected_url = self.expected_from_maas_url_and_reverse(
            maas_url,
            reversed_url)
        self.assertEqual(expected_url, absolute_url)

    def test_absolute_reverse_uses_args(self):
        maas_url = factory.make_simple_http_url()
        user = factory.make_User()
        self.useFixture(RegionConfigurationFixture(maas_url=maas_url))

        observed_url = absolute_reverse(
            'accounts-edit', kwargs={'username': user.username})

        reversed_url = reverse('accounts-edit', args=[user.username])
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
        self.assertEqual(results, list(map(strip_domain, inputs)))


class TestGetLocalClusterUUID(MAASTestCase):

    def test_get_local_cluster_UUID_returns_None_if_not_set(self):
        self.useFixture(ClusterConfigurationFixture())
        self.assertIsNone(get_local_cluster_UUID())

    def test_get_local_cluster_UUID_returns_cluster_UUID(self):
        uuid = factory.make_UUID()
        self.useFixture(ClusterConfigurationFixture(cluster_uuid=uuid))
        self.assertEqual(uuid, get_local_cluster_UUID())


def make_request(origin_ip):
    """Return a fake HTTP request with the given remote address."""
    return RequestFactory().post('/', REMOTE_ADDR=str(origin_ip))


class TestFindRackController(MAASServerTestCase):

    def test_returns_None_when_unknown_subnet(self):
        self.assertIsNone(
            find_rack_controller(make_request(factory.make_ip_address())))

    def test_returns_None_when_subnet_is_not_managed(self):
        subnet = factory.make_Subnet()
        self.assertIsNone(
            find_rack_controller(
                make_request(factory.pick_ip_in_Subnet(subnet))))

    def test_returns_primary_rack_when_subnet_is_managed(self):
        subnet = factory.make_Subnet()
        rack_controller = factory.make_RackController()
        subnet.vlan.dhcp_on = True
        subnet.vlan.primary_rack = rack_controller
        subnet.vlan.save()
        self.assertEquals(
            rack_controller.system_id, find_rack_controller(
                make_request(factory.pick_ip_in_Subnet(subnet))).system_id)


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
