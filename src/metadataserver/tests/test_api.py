# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the metadata API."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import httplib

from maasserver.testing.factory import factory
from maastesting import TestCase
from metadataserver.api import (
    check_version,
    make_list_response,
    make_text_response,
    UnknownMetadataVersion,
    )
from metadataserver.models import NodeKey


class TestHelpers(TestCase):
    """Tests for the API helper functions."""

    def make_text_response_presents_text_as_text_plain(self):
        input_text = "Hello."
        response = make_text_response(input_text)
        self.assertEqual('text/plain', response['Content-Type'])
        self.assertEqual(input_text, response.content)

    def make_list_response_presents_list_as_newline_separated_text(self):
        response = make_list_response(['aaa', 'bbb'])
        self.assertEqual('text/plain', response['Content-Type'])
        self.assertEqual("aaa\nbbb", response.content)

    def check_version_accepts_latest(self):
        check_version('latest')
        # The test is that we get here without exception.
        pass

    def check_version_raises_UnknownMetadataVersion_for_unknown_version(self):
        self.assertRaises(UnknownMetadataVersion, check_version, '1.0')


class TestViews(TestCase):
    """Tests for the API views."""

    def get(self, path, **headers):
        # Root of the metadata API service.
        metadata_root = "/metadata"
        return self.client.get(metadata_root + path, **headers)

    def make_node_and_auth_header(self):
        node = factory.make_node()
        token = NodeKey.objects.create_token(node)
        header = 'oauth_token=%s' % token.key
        return node, header

    def test_metadata_index_shows_latest(self):
        self.assertIn('latest', self.get('/').content)

    def test_metadata_index_shows_only_known_versions(self):
        for item in self.get('/').content.splitlines():
            check_version(item)
        # The test is that we get here without exception.
        pass

    def test_version_index_shows_meta_data_and_user_data(self):
        items = self.get('/latest/').content.splitlines()
        self.assertIn('meta-data', items)
        self.assertIn('user-data', items)

    def test_meta_data_view_returns_text_response(self):
        self.assertIn(
            'text/plain', self.get('/latest/meta-data/')['Content-Type'])

    def test_meta_data_unknown_item_is_not_found(self):
        node, header = self.make_node_and_auth_header()
        response = self.get(
            '/latest/meta-data/UNKNOWN-ITEM-HA-HA-HA',
            HTTP_AUTHORIZATION=header)
        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_meta_data_local_hostname(self):
        node, header = self.make_node_and_auth_header()
        response = self.get(
            '/latest/meta-data/local-hostname', HTTP_AUTHORIZATION=header)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertIn('text/plain', response['Content-Type'])
        self.assertEqual(node.hostname, response.content)

    def test_user_data_view_returns_binary_blob(self):
        response = self.get('/latest/user-data')
        self.assertEqual('application/octet-stream', response['Content-Type'])
        self.assertIsInstance(response.content, str)
