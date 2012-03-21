# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the metadata API."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from collections import namedtuple
import httplib

from maasserver.exceptions import Unauthorized
from maasserver.testing.factory import factory
from maasserver.testing.oauthclient import OAuthAuthenticatedClient
from maastesting.rabbit import uses_rabbit_fixture
from maastesting.testcase import TestCase
from metadataserver.api import (
    check_version,
    get_node_for_request,
    make_list_response,
    make_text_response,
    MetaDataHandler,
    UnknownMetadataVersion,
    )
from metadataserver.models import (
    NodeKey,
    NodeUserData,
    )
from metadataserver.nodeinituser import get_node_init_user


class TestHelpers(TestCase):
    """Tests for the API helper functions."""

    def fake_request(self, **kwargs):
        """Produce a cheap fake request, fresh from the sweat shop.

        Pass as arguments any header items you want to include.
        """
        return namedtuple('FakeRequest', ['META'])(kwargs)

    def test_make_text_response_presents_text_as_text_plain(self):
        input_text = "Hello."
        response = make_text_response(input_text)
        self.assertEqual('text/plain', response['Content-Type'])
        self.assertEqual(input_text, response.content)

    def test_make_list_response_presents_list_as_newline_separated_text(self):
        response = make_list_response(['aaa', 'bbb'])
        self.assertEqual('text/plain', response['Content-Type'])
        self.assertEqual("aaa\nbbb", response.content)

    def test_check_version_accepts_latest(self):
        check_version('latest')
        # The test is that we get here without exception.
        pass

    def test_check_version_reports_unknown_version(self):
        self.assertRaises(UnknownMetadataVersion, check_version, '1.0')

    @uses_rabbit_fixture
    def test_get_node_for_request_finds_node(self):
        node = factory.make_node()
        token = NodeKey.objects.get_token_for_node(node)
        request = self.fake_request(
            HTTP_AUTHORIZATION=factory.make_oauth_header(
                oauth_token=token.key))
        self.assertEqual(node, get_node_for_request(request))

    def test_get_node_for_request_reports_missing_auth_header(self):
        self.assertRaises(
            Unauthorized,
            get_node_for_request, self.fake_request())


class TestViews(TestCase):
    """Tests for the API views."""

    def make_node_client(self, node=None):
        """Create a test client logged in as if it were `node`."""
        if node is None:
            node = factory.make_node()
        token = NodeKey.objects.get_token_for_node(node)
        return OAuthAuthenticatedClient(get_node_init_user(), token)

    def get(self, path, client=None):
        """GET a resource from the metadata API.

        :param path: Path within the metadata API to access.  Should start
            with a slash.
        :param token: If given, authenticate the request using this token.
        :type token: oauth.oauth.OAuthToken
        :return: A response to the GET request.
        :rtype: django.http.HttpResponse
        """
        assert path.startswith('/'), "Give absolute metadata API path."
        if client is None:
            client = self.client
        # Root of the metadata API service.
        metadata_root = "/metadata"
        return client.get(metadata_root + path)

    def test_no_anonymous_access(self):
        self.assertEqual(httplib.UNAUTHORIZED, self.get('/').status_code)

    @uses_rabbit_fixture
    def test_metadata_index_shows_latest(self):
        client = self.make_node_client()
        self.assertIn('latest', self.get('/', client).content)

    @uses_rabbit_fixture
    def test_metadata_index_shows_only_known_versions(self):
        client = self.make_node_client()
        for item in self.get('/', client).content.splitlines():
            check_version(item)
        # The test is that we get here without exception.
        pass

    @uses_rabbit_fixture
    def test_version_index_shows_meta_data(self):
        client = self.make_node_client()
        items = self.get('/latest/', client).content.splitlines()
        self.assertIn('meta-data', items)

    @uses_rabbit_fixture
    def test_version_index_does_not_show_user_data_if_not_available(self):
        client = self.make_node_client()
        items = self.get('/latest/', client).content.splitlines()
        self.assertNotIn('user-data', items)

    @uses_rabbit_fixture
    def test_version_index_shows_user_data_if_available(self):
        node = factory.make_node()
        NodeUserData.objects.set_user_data(node, b"User data for node")
        client = self.make_node_client(node)
        items = self.get('/latest/', client).content.splitlines()
        self.assertIn('user-data', items)

    @uses_rabbit_fixture
    def test_meta_data_view_lists_fields(self):
        client = self.make_node_client()
        response = self.get('/latest/meta-data/', client)
        self.assertIn('text/plain', response['Content-Type'])
        self.assertItemsEqual(
            MetaDataHandler.fields, response.content.split())

    @uses_rabbit_fixture
    def test_meta_data_view_is_sorted(self):
        client = self.make_node_client()
        response = self.get('/latest/meta-data/', client)
        attributes = response.content.split()
        self.assertEqual(sorted(attributes), attributes)

    @uses_rabbit_fixture
    def test_meta_data_unknown_item_is_not_found(self):
        client = self.make_node_client()
        response = self.get('/latest/meta-data/UNKNOWN-ITEM-HA-HA-HA', client)
        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_get_attribute_producer_supports_all_fields(self):
        handler = MetaDataHandler()
        producers = map(handler.get_attribute_producer, handler.fields)
        self.assertNotIn(None, producers)

    @uses_rabbit_fixture
    def test_meta_data_local_hostname_returns_hostname(self):
        hostname = factory.getRandomString()
        client = self.make_node_client(factory.make_node(hostname=hostname))
        response = self.get('/latest/meta-data/local-hostname', client)
        self.assertEqual(
            (httplib.OK, hostname),
            (response.status_code, response.content.decode('ascii')))
        self.assertIn('text/plain', response['Content-Type'])

    @uses_rabbit_fixture
    def test_meta_data_instance_id_returns_system_id(self):
        node = factory.make_node()
        client = self.make_node_client(node)
        response = self.get('/latest/meta-data/instance-id', client)
        self.assertEqual(
            (httplib.OK, node.system_id),
            (response.status_code, response.content.decode('ascii')))
        self.assertIn('text/plain', response['Content-Type'])

    @uses_rabbit_fixture
    def test_user_data_view_returns_binary_data(self):
        data = b"\x00\xff\xff\xfe\xff"
        node = factory.make_node()
        NodeUserData.objects.set_user_data(node, data)
        client = self.make_node_client(node)
        response = self.get('/latest/user-data', client)
        self.assertEqual('application/octet-stream', response['Content-Type'])
        self.assertIsInstance(response.content, str)
        self.assertEqual(
            (httplib.OK, data), (response.status_code, response.content))

    @uses_rabbit_fixture
    def test_user_data_for_node_without_user_data_returns_not_found(self):
        response = self.get('/latest/user-data', self.make_node_client())
        self.assertEqual(httplib.NOT_FOUND, response.status_code)
