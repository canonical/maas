# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maascli.api`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import collections
import httplib
import io
import json
import sys

from apiclient.creds import convert_tuple_to_string
import httplib2
from maascli import api
from maascli.command import CommandError
from maastesting.factory import factory
from maastesting.testcase import TestCase
from mock import sentinel
from testtools.matchers import (
    Equals,
    IsInstance,
    MatchesAll,
    MatchesListwise,
    )


class TestFunctions(TestCase):
    """Test for miscellaneous functions in `maascli.api`."""

    def test_try_getpass(self):
        getpass = self.patch(api, "getpass")
        getpass.return_value = sentinel.credentials
        self.assertIs(sentinel.credentials, api.try_getpass(sentinel.prompt))
        getpass.assert_called_once_with(sentinel.prompt)

    def test_try_getpass_eof(self):
        getpass = self.patch(api, "getpass")
        getpass.side_effect = EOFError
        self.assertIsNone(api.try_getpass(sentinel.prompt))
        getpass.assert_called_once_with(sentinel.prompt)

    @staticmethod
    def make_credentials():
        return (
            factory.make_name("cred"),
            factory.make_name("cred"),
            factory.make_name("cred"),
            )

    def test_obtain_credentials_from_stdin(self):
        # When "-" is passed to obtain_credentials, it reads credentials from
        # stdin, trims whitespace, and converts it into a 3-tuple of creds.
        credentials = self.make_credentials()
        stdin = self.patch(sys, "stdin")
        stdin.readline.return_value = (
            convert_tuple_to_string(credentials) + "\n")
        self.assertEqual(credentials, api.obtain_credentials("-"))
        stdin.readline.assert_called_once()

    def test_obtain_credentials_via_getpass(self):
        # When None is passed to obtain_credentials, it attempts to obtain
        # credentials via getpass, then converts it into a 3-tuple of creds.
        credentials = self.make_credentials()
        getpass = self.patch(api, "getpass")
        getpass.return_value = convert_tuple_to_string(credentials)
        self.assertEqual(credentials, api.obtain_credentials(None))
        getpass.assert_called_once()

    def test_obtain_credentials_empty(self):
        # If the entered credentials are empty or only whitespace,
        # obtain_credentials returns None.
        getpass = self.patch(api, "getpass")
        getpass.return_value = None
        self.assertEqual(None, api.obtain_credentials(None))
        getpass.assert_called_once()

    def test_fetch_api_description(self):
        content = factory.make_name("content")
        request = self.patch(httplib2.Http, "request")
        response = httplib2.Response({})
        response.status = httplib.OK
        response["content-type"] = "application/json"
        request.return_value = response, json.dumps(content)
        self.assertEqual(
            content, api.fetch_api_description("http://example.com/api/1.0/"))
        request.assert_called_once_with(
            b"http://example.com/api/1.0/describe/", "GET")

    def test_fetch_api_description_not_okay(self):
        # If the response is not 200 OK, fetch_api_description throws toys.
        content = factory.make_name("content")
        request = self.patch(httplib2.Http, "request")
        response = httplib2.Response({})
        response.status = httplib.BAD_REQUEST
        response.reason = httplib.responses[httplib.BAD_REQUEST]
        request.return_value = response, json.dumps(content)
        error = self.assertRaises(
            CommandError, api.fetch_api_description,
            "http://example.com/api/1.0/")
        error_expected = "%d %s:\n%s" % (
            httplib.BAD_REQUEST, httplib.responses[httplib.BAD_REQUEST],
            json.dumps(content))
        self.assertEqual(error_expected, "%s" % error)

    def test_fetch_api_description_wrong_content_type(self):
        # If the response's content type is not application/json,
        # fetch_api_description throws toys again.
        content = factory.make_name("content")
        request = self.patch(httplib2.Http, "request")
        response = httplib2.Response({})
        response.status = httplib.OK
        response["content-type"] = "text/css"
        request.return_value = response, json.dumps(content)
        error = self.assertRaises(
            CommandError, api.fetch_api_description,
            "http://example.com/api/1.0/")
        self.assertEqual(
            "Expected application/json, got: text/css",
            "%s" % error)

    def test_get_response_content_type_returns_content_type_header(self):
        response = httplib2.Response(
            {"content-type": "application/json"})
        self.assertEqual(
            "application/json",
            api.get_response_content_type(response))

    def test_get_response_content_type_omits_parameters(self):
        response = httplib2.Response(
            {"content-type": "application/json; charset=utf-8"})
        self.assertEqual(
            "application/json",
            api.get_response_content_type(response))

    def test_get_response_content_type_return_None_when_type_not_found(self):
        response = httplib2.Response({})
        self.assertIsNone(api.get_response_content_type(response))

    def test_print_headers(self):
        # print_headers() prints the given headers, in order, with each
        # hyphen-delimited part of the header name capitalised, to the given
        # file, with the names right aligned, and with a 2 space left margin.
        headers = collections.OrderedDict()
        headers["two-two"] = factory.make_name("two")
        headers["one"] = factory.make_name("one")
        buf = io.StringIO()
        api.print_headers(headers, buf)
        self.assertEqual(
            ("      One: %(one)s\n"
             "  Two-Two: %(two-two)s\n") % headers,
            buf.getvalue())


class TestIsResponseTextual(TestCase):
    """Tests for `is_response_textual`."""

    content_types_textual_map = {
        "text/plain": True,
        "text/yaml": True,
        "text/foobar": True,
        "application/json": True,
        "image/png": False,
        "video/webm": False,
        }

    scenarios = sorted(
        (ctype, {"content_type": ctype, "is_textual": is_textual})
        for ctype, is_textual in content_types_textual_map.items()
        )

    def test_type(self):
        grct = self.patch(api, "get_response_content_type")
        grct.return_value = self.content_type
        self.assertEqual(
            self.is_textual,
            api.is_response_textual(sentinel.response))
        grct.assert_called_once_with(sentinel.response)


class TestAction(TestCase):
    """Tests for :class:`maascli.api.Action`."""

    def test_name_value_pair_returns_2_tuple(self):
        # The tuple is important because this is used as input to
        # urllib.urlencode, which doesn't let the data it consumes walk and
        # quack like a duck. It insists that the first item in a non-dict
        # sequence is a tuple. Of any size. It does this in the name of
        # avoiding *string* input.
        result = api.Action.name_value_pair("foo=bar")
        self.assertThat(
            result, MatchesAll(
                Equals(("foo", "bar")),
                IsInstance(tuple)))

    def test_name_value_pair_demands_two_parts(self):
        self.assertRaises(
            CommandError, api.Action.name_value_pair, "foo bar")

    def test_name_value_pair_does_not_strip_whitespace(self):
        self.assertEqual(
            (" foo ", " bar "),
            api.Action.name_value_pair(" foo = bar "))


class TestPayloadPreparation(TestCase):
    """Tests for `maascli.api.Action.prepare_payload`."""

    uri_base = "http://example.com/MAAS/api/1.0/"

    # Scenarios for ReSTful operations; i.e. without an "op" parameter.
    scenarios_without_op = (
        # Without data, all requests have an empty request body and no extra
        # headers.
        ("create",
         {"method": "POST", "data": [],
          "expected_uri": uri_base,
          "expected_body": None,
          "expected_headers": {}}),
        ("read",
         {"method": "GET", "data": [],
          "expected_uri": uri_base,
          "expected_body": None,
          "expected_headers": {}}),
        ("update",
         {"method": "PUT", "data": [],
          "expected_uri": uri_base,
          "expected_body": None,
          "expected_headers": {}}),
        ("delete",
         {"method": "DELETE", "data": [],
          "expected_uri": uri_base,
          "expected_body": None,
          "expected_headers": {}}),
        # With data, PUT, POST, and DELETE requests have their body and extra
        # headers prepared by encode_multipart_data. For GET requests, the
        # data is encoded into the query string, and both the request body and
        # extra headers are empty.
        ("create-with-data",
         {"method": "POST", "data": [("foo", "bar"), ("foo", "baz")],
          "expected_uri": uri_base,
          "expected_body": sentinel.body,
          "expected_headers": sentinel.headers}),
        ("read-with-data",
         {"method": "GET", "data": [("foo", "bar"), ("foo", "baz")],
          "expected_uri": uri_base + "?foo=bar&foo=baz",
          "expected_body": None,
          "expected_headers": {}}),
        ("update-with-data",
         {"method": "PUT", "data": [("foo", "bar"), ("foo", "baz")],
          "expected_uri": uri_base,
          "expected_body": sentinel.body,
          "expected_headers": sentinel.headers}),
        ("delete-with-data",
         {"method": "DELETE", "data": [("foo", "bar"), ("foo", "baz")],
          "expected_uri": uri_base,
          "expected_body": sentinel.body,
          "expected_headers": sentinel.headers}),
        )

    # Scenarios for non-ReSTful operations; i.e. with an "op" parameter.
    scenarios_with_op = (
        # Without data, all requests have an empty request body and no extra
        # headers. The operation is encoded into the query string.
        ("create",
         {"method": "POST", "data": [],
          "expected_uri": uri_base + "?op=something",
          "expected_body": None,
          "expected_headers": {}}),
        ("read",
         {"method": "GET", "data": [],
          "expected_uri": uri_base + "?op=something",
          "expected_body": None,
          "expected_headers": {}}),
        ("update",
         {"method": "PUT", "data": [],
          "expected_uri": uri_base + "?op=something",
          "expected_body": None,
          "expected_headers": {}}),
        ("delete",
         {"method": "DELETE", "data": [],
          "expected_uri": uri_base + "?op=something",
          "expected_body": None,
          "expected_headers": {}}),
        # With data, PUT, POST, and DELETE requests have their body and extra
        # headers prepared by encode_multipart_data. For GET requests, the
        # data is encoded into the query string, and both the request body and
        # extra headers are empty. The operation is encoded into the query
        # string.
        ("create-with-data",
         {"method": "POST", "data": [("foo", "bar"), ("foo", "baz")],
          "expected_uri": uri_base + "?op=something",
          "expected_body": sentinel.body,
          "expected_headers": sentinel.headers}),
        ("read-with-data",
         {"method": "GET", "data": [("foo", "bar"), ("foo", "baz")],
          "expected_uri": uri_base + "?op=something&foo=bar&foo=baz",
          "expected_body": None,
          "expected_headers": {}}),
        ("update-with-data",
         {"method": "PUT", "data": [("foo", "bar"), ("foo", "baz")],
          "expected_uri": uri_base + "?op=something",
          "expected_body": sentinel.body,
          "expected_headers": sentinel.headers}),
        ("delete-with-data",
         {"method": "DELETE", "data": [("foo", "bar"), ("foo", "baz")],
          "expected_uri": uri_base + "?op=something",
          "expected_body": sentinel.body,
          "expected_headers": sentinel.headers}),
        )

    scenarios_without_op = tuple(
        ("%s-without-op" % name, dict(scenario, op=None))
        for name, scenario in scenarios_without_op)

    scenarios_with_op = tuple(
        ("%s-with-op" % name, dict(scenario, op="something"))
        for name, scenario in scenarios_with_op)

    scenarios = scenarios_without_op + scenarios_with_op

    def test_prepare_payload(self):
        # Patch encode_multipart_data to match the scenarios.
        encode_multipart_data = self.patch(api, "encode_multipart_data")
        encode_multipart_data.return_value = sentinel.body, sentinel.headers
        # The payload returned is a 3-tuple of (uri, body, headers).
        payload = api.Action.prepare_payload(
            op=self.op, method=self.method,
            uri=self.uri_base, data=self.data)
        expected = (
            Equals(self.expected_uri),
            Equals(self.expected_body),
            Equals(self.expected_headers),
            )
        self.assertThat(payload, MatchesListwise(expected))
        # encode_multipart_data, when called, is passed the data
        # unadulterated.
        if self.expected_body is sentinel.body:
            api.encode_multipart_data.assert_called_once_with(self.data)
