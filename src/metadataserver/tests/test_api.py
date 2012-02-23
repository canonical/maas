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
from random import randint
from time import time

from maasserver.exceptions import Unauthorized
from maasserver.testing.factory import factory
from maasserver.testing.oauthclient import OAuthAuthenticatedClient
from maastesting import TestCase
from metadataserver.api import (
    check_version,
    extract_oauth_key,
    get_node_for_request,
    make_list_response,
    make_text_response,
    MetaDataHandler,
    UnknownMetadataVersion,
    )
from metadataserver.models import NodeKey
from metadataserver.nodeinituser import get_node_init_user


class TestHelpers(TestCase):
    """Tests for the API helper functions."""

    def make_oauth_header(self, **kwargs):
        """Fake an OAuth authorization header.

        This will use arbitrary values.  Pass as keyword arguments any
        header items that you wish to override.
        """
        items = {
            'realm': factory.getRandomString(),
            'oauth_nonce': randint(0, 99999),
            'oauth_timestamp': time(),
            'oauth_consumer_key': factory.getRandomString(18),
            'oauth_signature_method': 'PLAINTEXT',
            'oauth_version': '1.0',
            'oauth_token': factory.getRandomString(18),
            'oauth_signature': "%%26%s" % factory.getRandomString(32),
        }
        items.update(kwargs)
        return "OAuth " + ", ".join([
            '%s="%s"' % (key, value) for key, value in items.items()])

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

    def test_extract_oauth_key_extracts_oauth_token_from_oauth_header(self):
        token = factory.getRandomString(18)
        self.assertEqual(
            token,
            extract_oauth_key(self.make_oauth_header(oauth_token=token)))

    def test_extract_oauth_key_rejects_auth_without_oauth_key(self):
        self.assertRaises(Unauthorized, extract_oauth_key, '')

    def test_get_node_for_request_finds_node(self):
        node = factory.make_node()
        token = NodeKey.objects.create_token(node)
        request = self.fake_request(
            HTTP_AUTHORIZATION=self.make_oauth_header(oauth_token=token.key))
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
        token = NodeKey.objects.create_token(node)
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

    def test_metadata_index_shows_latest(self):
        client = self.make_node_client()
        self.assertIn('latest', self.get('/', client).content)

    def test_metadata_index_shows_only_known_versions(self):
        client = self.make_node_client()
        for item in self.get('/', client).content.splitlines():
            check_version(item)
        # The test is that we get here without exception.
        pass

    def test_version_index_shows_meta_data_and_user_data(self):
        client = self.make_node_client()
        items = self.get('/latest/', client).content.splitlines()
        self.assertIn('meta-data', items)
        self.assertIn('user-data', items)

    def test_meta_data_view_lists_fields(self):
        client = self.make_node_client()
        response = self.get('/latest/meta-data/', client)
        self.assertIn('text/plain', response['Content-Type'])
        self.assertItemsEqual(
            MetaDataHandler.fields, response.content.split())

    def test_meta_data_view_is_sorted(self):
        client = self.make_node_client()
        response = self.get('/latest/meta-data/', client)
        attributes = response.content.split()
        self.assertEqual(sorted(attributes), attributes)

    def test_meta_data_unknown_item_is_not_found(self):
        client = self.make_node_client()
        response = self.get('/latest/meta-data/UNKNOWN-ITEM-HA-HA-HA', client)
        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_get_attribute_producer_supports_all_fields(self):
        handler = MetaDataHandler()
        producers = map(handler.get_attribute_producer, handler.fields)
        self.assertNotIn(None, producers)

    def test_meta_data_local_hostname_returns_hostname(self):
        hostname = factory.getRandomString()
        client = self.make_node_client(factory.make_node(hostname=hostname))
        response = self.get('/latest/meta-data/local-hostname', client)
        self.assertEqual(
            (httplib.OK, hostname),
            (response.status_code, response.content.decode('ascii')))
        self.assertIn('text/plain', response['Content-Type'])

    def test_meta_data_instance_id_returns_system_id(self):
        node = factory.make_node()
        client = self.make_node_client(node)
        response = self.get('/latest/meta-data/instance-id', client)
        self.assertEqual(
            (httplib.OK, node.system_id),
            (response.status_code, response.content.decode('ascii')))
        self.assertIn('text/plain', response['Content-Type'])

    def test_user_data_view_returns_binary_blob(self):
        client = self.make_node_client()
        response = self.get('/latest/user-data', client)
        self.assertEqual('application/octet-stream', response['Content-Type'])
        self.assertIsInstance(response.content, str)
