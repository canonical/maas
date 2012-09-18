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

import httplib
import json
import sys

from apiclient.creds import convert_tuple_to_string
import httplib2
from maascli import (
    api,
    CommandError,
    )
from maastesting.factory import factory
from maastesting.testcase import TestCase
from mock import sentinel


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
