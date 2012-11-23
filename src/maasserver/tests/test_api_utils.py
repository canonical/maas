# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for API helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from collections import namedtuple

from django.http import QueryDict
from maasserver.api_utils import (
    extract_oauth_key,
    extract_oauth_key_from_auth_header,
    get_oauth_token,
    get_overrided_query_dict,
    )
from maasserver.exceptions import Unauthorized
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase


class TestGetOverridedQueryDict(TestCase):

    def test_returns_QueryDict(self):
        defaults = {factory.getRandomString(): factory.getRandomString()}
        results = get_overrided_query_dict(defaults, QueryDict(''))
        expected_results = QueryDict('').copy()
        expected_results.update(defaults)
        self.assertEqual(expected_results, results)

    def test_data_values_override_defaults(self):
        key = factory.getRandomString()
        defaults = {key: factory.getRandomString()}
        data_value = factory.getRandomString()
        data = {key: data_value}
        results = get_overrided_query_dict(defaults, data)
        self.assertEqual([data_value], results.getlist(key))


class TestOAuthHelpers(TestCase):

    def make_fake_request(self, auth_header):
        """Create a very simple fake request, with just an auth header."""
        FakeRequest = namedtuple('FakeRequest', ['META'])
        return FakeRequest(META={'HTTP_AUTHORIZATION': auth_header})

    def test_extract_oauth_key_from_auth_header_returns_key(self):
        token = factory.getRandomString(18)
        self.assertEqual(
            token,
            extract_oauth_key_from_auth_header(
                factory.make_oauth_header(oauth_token=token)))

    def test_extract_oauth_key_from_auth_header_returns_None_if_missing(self):
        self.assertIs(None, extract_oauth_key_from_auth_header(''))

    def test_extract_oauth_key_raises_Unauthorized_if_no_auth_header(self):
        self.assertRaises(
            Unauthorized,
            extract_oauth_key, self.make_fake_request(None))

    def test_extract_oauth_key_raises_Unauthorized_if_no_key(self):
        self.assertRaises(
            Unauthorized,
            extract_oauth_key, self.make_fake_request(''))

    def test_extract_oauth_key_returns_key(self):
        token = factory.getRandomString(18)
        self.assertEqual(
            token,
            extract_oauth_key(self.make_fake_request(
                factory.make_oauth_header(oauth_token=token))))

    def test_get_oauth_token_finds_token(self):
        user = factory.make_user()
        consumer, token = user.get_profile().create_authorisation_token()
        self.assertEqual(
            token,
            get_oauth_token(
                self.make_fake_request(
                    factory.make_oauth_header(oauth_token=token.key))))

    def test_get_oauth_token_raises_Unauthorized_for_unknown_token(self):
        fake_token = factory.getRandomString(18)
        header = factory.make_oauth_header(oauth_token=fake_token)
        self.assertRaises(
            Unauthorized,
            get_oauth_token, self.make_fake_request(header))
