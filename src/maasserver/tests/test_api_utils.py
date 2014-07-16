# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for API helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from collections import namedtuple

from django.http import QueryDict
from maasserver.api_utils import (
    extract_bool,
    extract_oauth_key,
    extract_oauth_key_from_auth_header,
    get_oauth_token,
    get_overridden_query_dict,
    )
from maasserver.exceptions import Unauthorized
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestExtractBool(MAASServerTestCase):
    def test_asserts_against_raw_bytes(self):
        self.assertRaises(AssertionError, extract_bool, b'0')

    def test_asserts_against_None(self):
        self.assertRaises(AssertionError, extract_bool, None)

    def test_asserts_against_number(self):
        self.assertRaises(AssertionError, extract_bool, 0)

    def test_0_means_False(self):
        self.assertEquals(extract_bool('0'), False)

    def test_1_means_True(self):
        self.assertEquals(extract_bool('1'), True)

    def test_rejects_other_numeric_strings(self):
        self.assertRaises(ValueError, extract_bool, '00')
        self.assertRaises(ValueError, extract_bool, '2')
        self.assertRaises(ValueError, extract_bool, '-1')

    def test_rejects_empty_string(self):
        self.assertRaises(ValueError, extract_bool, '')


class TestGetOverridedQueryDict(MAASServerTestCase):

    def test_returns_QueryDict(self):
        fields = [factory.make_name('field')]
        defaults = {fields[0]: factory.make_name('field')}
        results = get_overridden_query_dict(defaults, QueryDict(''), fields)
        expected_results = QueryDict('').copy()
        expected_results.update(defaults)
        self.assertEqual(expected_results, results)

    def test_data_values_override_defaults(self):
        key = factory.make_name('key')
        defaults = {key: factory.make_name('key')}
        data_value = factory.make_name('value')
        data = {key: data_value}
        results = get_overridden_query_dict(defaults, data, [key])
        self.assertEqual([data_value], results.getlist(key))

    def test_takes_multiple_values_in_default_parameters(self):
        values = [factory.make_name('value') for i in range(2)]
        key = factory.make_name('key')
        defaults = {key: values}
        results = get_overridden_query_dict(defaults, {}, [key])
        self.assertEqual(values, results.getlist(key))

    def test_querydict_data_values_override_defaults(self):
        key = factory.make_name('key')
        defaults = {key: factory.make_name('name')}
        data_values = [factory.make_name('value') for i in range(2)]
        data = QueryDict('').copy()
        data.setlist(key, data_values)
        results = get_overridden_query_dict(defaults, data, [key])
        self.assertEqual(data_values, results.getlist(key))

    def test_fields_filter_results(self):
        key1 = factory.make_string()
        key2 = factory.make_string()
        defaults = {
            key1: factory.make_string(),
            key2: factory.make_string(),
        }
        data_value1 = factory.make_string()
        data_value2 = factory.make_string()
        data = {key1: data_value1, key2: data_value2}
        results = get_overridden_query_dict(defaults, data, [key1])
        self.assertEqual([data_value2], results.getlist(key2))


class TestOAuthHelpers(MAASServerTestCase):

    def make_fake_request(self, auth_header):
        """Create a very simple fake request, with just an auth header."""
        FakeRequest = namedtuple('FakeRequest', ['META'])
        return FakeRequest(META={'HTTP_AUTHORIZATION': auth_header})

    def test_extract_oauth_key_from_auth_header_returns_key(self):
        token = factory.make_string(18)
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
        token = factory.make_string(18)
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
        fake_token = factory.make_string(18)
        header = factory.make_oauth_header(oauth_token=fake_token)
        self.assertRaises(
            Unauthorized,
            get_oauth_token, self.make_fake_request(header))
