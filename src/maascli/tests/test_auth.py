# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
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

import sys

from apiclient.creds import convert_tuple_to_string
from maascli import auth
from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import (
    ANY,
    sentinel,
    )


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
        self.assertEqual(credentials, auth.obtain_credentials("-"))
        self.assertThat(stdin.readline, MockCalledOnceWith())

    def test_obtain_credentials_via_getpass(self):
        # When None is passed to obtain_credentials, it attempts to obtain
        # credentials via getpass, then converts it into a 3-tuple of creds.
        credentials = self.make_credentials()
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
