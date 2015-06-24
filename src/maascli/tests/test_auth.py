# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maascli.auth`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from argparse import Namespace
import httplib
import json
import sys

from apiclient.creds import (
    convert_string_to_tuple,
    convert_tuple_to_string,
)
import httplib2
from maascli import auth
from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import (
    ANY,
    sentinel,
)


def make_credentials():
    return (
        factory.make_name('consumer_key'),
        factory.make_name('token_key'),
        factory.make_name('secret_key'),
        )


def make_options():
    credentials = ':'.join(make_credentials())
    url = u'http://example.com/api/1.0/'
    options = Namespace(
        credentials=credentials, execute=None, insecure=False,
        profile_name='test', url=url)
    return options


class TestAuth(MAASTestCase):

    def test_try_getpass(self):
        getpass = self.patch(auth, "getpass")
        getpass.return_value = sentinel.credentials
        self.assertIs(sentinel.credentials, auth.try_getpass(sentinel.prompt))
        self.assertThat(getpass, MockCalledOnceWith(sentinel.prompt))

    def test_try_getpass_eof(self):
        getpass = self.patch(auth, "getpass")
        getpass.side_effect = EOFError
        self.assertIsNone(auth.try_getpass(sentinel.prompt))
        self.assertThat(getpass, MockCalledOnceWith(sentinel.prompt))

    def test_obtain_credentials_from_stdin(self):
        # When "-" is passed to obtain_credentials, it reads credentials from
        # stdin, trims whitespace, and converts it into a 3-tuple of creds.
        credentials = make_credentials()
        stdin = self.patch(sys, "stdin")
        stdin.readline.return_value = (
            convert_tuple_to_string(credentials) + "\n")
        self.assertEqual(credentials, auth.obtain_credentials("-"))
        self.assertThat(stdin.readline, MockCalledOnceWith())

    def test_obtain_credentials_via_getpass(self):
        # When None is passed to obtain_credentials, it attempts to obtain
        # credentials via getpass, then converts it into a 3-tuple of creds.
        credentials = make_credentials()
        getpass = self.patch(auth, "getpass")
        getpass.return_value = convert_tuple_to_string(credentials)
        self.assertEqual(credentials, auth.obtain_credentials(None))
        self.assertThat(getpass, MockCalledOnceWith(ANY))

    def test_obtain_credentials_empty(self):
        # If the entered credentials are empty or only whitespace,
        # obtain_credentials returns None.
        getpass = self.patch(auth, "getpass")
        getpass.return_value = None
        self.assertEqual(None, auth.obtain_credentials(None))
        self.assertThat(getpass, MockCalledOnceWith(ANY))

    def test_check_valid_apikey_passes_valid_key(self):
        options = make_options()
        content = factory.make_name('content')
        mock_request = self.patch(httplib2.Http, 'request')
        response = httplib2.Response({})
        response['status'] = httplib.OK
        mock_request.return_value = response, json.dumps(content)
        self.assertTrue(auth.check_valid_apikey(
            options.url, convert_string_to_tuple(options.credentials),
            options.insecure))

    def test_check_valid_apikey_catches_invalid_key(self):
        options = make_options()
        content = factory.make_name('content')
        mock_request = self.patch(httplib2.Http, 'request')
        response = httplib2.Response({})
        response['status'] = httplib.UNAUTHORIZED
        mock_request.return_value = response, json.dumps(content)
        self.assertFalse(auth.check_valid_apikey(
            options.url, convert_string_to_tuple(options.credentials),
            options.insecure))

    def test_check_valid_apikey_raises_if_unexpected_response(self):
        options = make_options()
        content = factory.make_name('content')
        mock_request = self.patch(httplib2.Http, 'request')
        response = httplib2.Response({})
        response['status'] = httplib.GONE
        mock_request.return_value = response, json.dumps(content)
        self.assertRaises(
            auth.UnexpectedResponse, auth.check_valid_apikey,
            options.url, convert_string_to_tuple(options.credentials),
            options.insecure)
