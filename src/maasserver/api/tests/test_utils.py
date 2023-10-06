# Copyright 2012-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for API helpers."""


from collections import namedtuple

from django.forms import CharField
from django.http import QueryDict
from testtools.matchers import Equals, IsInstance, MatchesDict

from maasserver.api.utils import (
    extract_bool,
    extract_oauth_key,
    extract_oauth_key_from_auth_header,
    get_oauth_token,
    get_overridden_query_dict,
)
from maasserver.config_forms import DictCharField
from maasserver.exceptions import Unauthorized
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.testcase import MAASTestCase


class TestExtractBool(MAASTestCase):
    def test_asserts_against_raw_bytes(self):
        self.assertRaises(AssertionError, extract_bool, b"0")

    def test_asserts_against_None(self):
        self.assertRaises(AssertionError, extract_bool, None)

    def test_asserts_against_number(self):
        self.assertRaises(AssertionError, extract_bool, 0)

    def test_0_means_False(self):
        self.assertFalse(extract_bool("0"))

    def test_1_means_True(self):
        self.assertTrue(extract_bool("1"))

    def test_rejects_other_numeric_strings(self):
        self.assertRaises(ValueError, extract_bool, "00")
        self.assertRaises(ValueError, extract_bool, "2")
        self.assertRaises(ValueError, extract_bool, "-1")

    def test_rejects_empty_string(self):
        self.assertRaises(ValueError, extract_bool, "")


class TestGetOverridedQueryDict(MAASTestCase):
    def test_returns_QueryDict(self):
        fields = [factory.make_name("field")]
        defaults = {fields[0]: factory.make_name("field")}
        results = get_overridden_query_dict(defaults, QueryDict(""), fields)
        expected_results = QueryDict("").copy()
        expected_results.update(defaults)
        self.assertEqual(expected_results, results)

    def test_data_values_override_defaults(self):
        key = factory.make_name("key")
        defaults = {key: factory.make_name("key")}
        data_value = factory.make_name("value")
        data = {key: data_value}
        results = get_overridden_query_dict(defaults, data, [key])
        self.assertEqual([data_value], results.getlist(key))

    def test_takes_multiple_values_in_default_parameters(self):
        values = [factory.make_name("value") for _ in range(2)]
        key = factory.make_name("key")
        defaults = {key: values}
        results = get_overridden_query_dict(defaults, {}, [key])
        self.assertEqual(values, results.getlist(key))

    def test_querydict_data_values_override_defaults(self):
        key = factory.make_name("key")
        defaults = {key: factory.make_name("name")}
        data_values = [factory.make_name("value") for _ in range(2)]
        data = QueryDict("").copy()
        data.setlist(key, data_values)
        results = get_overridden_query_dict(defaults, data, [key])
        self.assertEqual(data_values, results.getlist(key))

    def test_fields_filter_results(self):
        key1 = factory.make_string()
        key2 = factory.make_string()
        defaults = {key1: factory.make_string(), key2: factory.make_string()}
        data_value1 = factory.make_string()
        data_value2 = factory.make_string()
        data = {key1: data_value1, key2: data_value2}
        results = get_overridden_query_dict(defaults, data, [key1])
        self.assertEqual([data_value2], results.getlist(key2))

    def test_expands_dict_fields(self):
        field_name = factory.make_name("field_name")
        sub_fields = {
            factory.make_name("sub_field"): CharField() for _ in range(3)
        }
        fields = {field_name: DictCharField(sub_fields)}
        defaults = {
            f"{field_name}_{field}": factory.make_name("subfield")
            for field in sub_fields.keys()
        }
        data = {field_name: DictCharField(fields)}
        results = get_overridden_query_dict(defaults, data, fields)
        expected = {key: Equals(value) for key, value in defaults.items()}
        expected.update(
            {
                name: IsInstance(value.__class__)
                for name, value in fields.items()
            }
        )
        self.assertThat(results, MatchesDict(expected))


def make_fake_request(auth_header):
    """Create a very simple fake request, with just an auth header."""
    FakeRequest = namedtuple("FakeRequest", ["headers"])
    return FakeRequest(headers={"authorization": auth_header})


class TestOAuthHelpers(MAASTestCase):
    def test_extract_oauth_key_from_auth_header_returns_key(self):
        token = factory.make_string(18)
        self.assertEqual(
            token,
            extract_oauth_key_from_auth_header(
                factory.make_oauth_header(oauth_token=token)
            ),
        )

    def test_extract_oauth_key_from_auth_header_no_whitespace_rtns_key(self):
        token = factory.make_string(18)
        auth_header = factory.make_oauth_header(oauth_token=token)
        auth_header = auth_header.replace(", ", ",")
        self.assertEqual(
            token, extract_oauth_key_from_auth_header(auth_header)
        )

    def test_extract_oauth_key_from_auth_header_returns_None_if_missing(self):
        self.assertIsNone(extract_oauth_key_from_auth_header(""))

    def test_extract_oauth_key_raises_Unauthorized_if_no_auth_header(self):
        self.assertRaises(
            Unauthorized, extract_oauth_key, make_fake_request(None)
        )

    def test_extract_oauth_key_raises_Unauthorized_if_no_key(self):
        self.assertRaises(
            Unauthorized, extract_oauth_key, make_fake_request("")
        )

    def test_extract_oauth_key_returns_key(self):
        token = factory.make_string(18)
        self.assertEqual(
            token,
            extract_oauth_key(
                make_fake_request(factory.make_oauth_header(oauth_token=token))
            ),
        )


class TestOAuthHelpersWithDatabase(MAASServerTestCase):
    def test_get_oauth_token_finds_token(self):
        user = factory.make_User()
        consumer, token = user.userprofile.create_authorisation_token()
        self.assertEqual(
            token,
            get_oauth_token(
                make_fake_request(
                    factory.make_oauth_header(oauth_token=token.key)
                )
            ),
        )

    def test_get_oauth_token_raises_Unauthorized_for_unknown_token(self):
        fake_token = factory.make_string(18)
        header = factory.make_oauth_header(oauth_token=fake_token)
        self.assertRaises(
            Unauthorized, get_oauth_token, make_fake_request(header)
        )
