# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the metadata API."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maastesting import TestCase
from metadataserver.api import (
    check_version,
    make_list_response,
    make_text_response,
    UnknownMetadataVersion,
    )


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

    def get(self, path):
        # Root of the metadata API service.
        metadata_root = "/metadata"
        return self.client.get(metadata_root + path)

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
        self.assertEqual(
            'text/plain', self.get('/latest/meta-data/')['Content-Type'])

    def test_user_data_view_returns_binary_blob(self):
        response = self.get('/latest/user-data')
        self.assertEqual('application/octet-stream', response['Content-Type'])
        self.assertIsInstance(response.content, str)
