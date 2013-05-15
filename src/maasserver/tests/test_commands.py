# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test custom commands, as found in src/maasserver/management/commands."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from codecs import getwriter
from io import BytesIO

from apiclient.creds import convert_tuple_to_string
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from maasserver.models.user import get_creds_tuple
from maasserver.testing.factory import factory
from maasserver.utils.orm import get_one
from maastesting.djangotestcase import DjangoTestCase


class TestCommands(DjangoTestCase):
    """Happy-path integration testing for custom commands.

    Detailed testing does not belong here.  If there's any complexity at all
    in a command's code, it should be extracted and unit-tested separately.
    """

    def test_generate_api_doc(self):
        out = BytesIO()
        stdout = getwriter("UTF-8")(out)
        call_command('generate_api_doc', stdout=stdout)
        result = stdout.getvalue()
        # Just check that the documentation looks all right.
        self.assertIn("POST /api/1.0/account/", result)
        self.assertIn("MAAS API", result)
        # The documentation starts with a ReST title (not indented).
        self.assertEqual('=', result[0])

    def test_createadmin_requires_username(self):
        stderr = BytesIO()
        self.assertRaises(
            SystemExit, call_command, 'createadmin', stderr=stderr)
        command_output = stderr.getvalue().strip()

        self.assertIn(
            "Error: You must provide a username with --username.",
             command_output)

    def test_createadmin_requires_password(self):
        username = factory.getRandomString()
        stderr = BytesIO()
        self.assertRaises(
            SystemExit, call_command, 'createadmin', username=username,
            stderr=stderr)
        command_output = stderr.getvalue().strip()

        self.assertIn(
            "Error: You must provide a password with --password.",
             command_output)

    def test_createadmin_requires_email(self):
        username = factory.getRandomString()
        password = factory.getRandomString()
        stderr = BytesIO()
        self.assertRaises(
            SystemExit, call_command, 'createadmin', username=username,
            password=password, stderr=stderr)
        command_output = stderr.getvalue().strip()

        self.assertIn(
            "Error: You must provide an email with --email.",
             command_output)

    def test_createadmin_creates_admin(self):
        stderr = BytesIO()
        stdout = BytesIO()
        username = factory.getRandomString()
        password = factory.getRandomString()
        email = '%s@example.com' % factory.getRandomString()
        call_command(
            'createadmin', username=username, password=password,
            email=email, stderr=stderr, stdout=stdout)
        user = get_one(User.objects.filter(username=username))

        self.assertEquals('', stderr.getvalue().strip())
        self.assertEquals('', stdout.getvalue().strip())
        self.assertTrue(user.check_password(password))
        self.assertTrue(user.is_superuser)
        self.assertEqual(email, user.email)

    def test_clearcache_clears_entire_cache(self):
        key = factory.getRandomString()
        cache.set(key, factory.getRandomString())
        call_command('clearcache')
        self.assertIsNone(cache.get(key, None))

    def test_clearcache_clears_specific_key(self):
        key = factory.getRandomString()
        cache.set(key, factory.getRandomString())
        another_key = factory.getRandomString()
        cache.set(another_key, factory.getRandomString())
        call_command('clearcache', key=key)
        self.assertIsNone(cache.get(key, None))
        self.assertIsNotNone(cache.get(another_key, None))


class TestApikeyCommand(DjangoTestCase):

    def test_apikey_requires_username(self):
        stderr = BytesIO()
        self.assertRaises(
            SystemExit, call_command, 'apikey', stderr=stderr)
        command_output = stderr.getvalue().strip()

        self.assertIn(
            "Error: You must provide a username with --username.",
             command_output)

    def test_apikey_gets_keys(self):
        stderr = BytesIO()
        out = BytesIO()
        stdout = getwriter("UTF-8")(out)
        user = factory.make_user()
        call_command(
            'apikey', username=user.username, stderr=stderr, stdout=stdout)
        self.assertEqual('', stderr.getvalue().strip())

        expected_token = get_one(
            user.get_profile().get_authorisation_tokens())
        expected_string = convert_tuple_to_string(
            get_creds_tuple(expected_token))
        self.assertEqual(expected_string, stdout.getvalue())

    def test_apikey_generates_key(self):
        stderr = BytesIO()
        out = BytesIO()
        stdout = getwriter("UTF-8")(out)
        user = factory.make_user()
        num_keys = len(user.get_profile().get_authorisation_tokens())
        call_command(
            'apikey', username=user.username, generate=True, stderr=stderr,
            stdout=stdout)
        self.assertEqual('', stderr.getvalue().strip())
        keys_after = user.get_profile().get_authorisation_tokens()
        expected_num_keys = num_keys + 1
        self.assertEqual(expected_num_keys, len(keys_after))
        expected_token = user.get_profile().get_authorisation_tokens()[1]
        expected_string = convert_tuple_to_string(
            get_creds_tuple(expected_token))
        self.assertEqual(expected_string, stdout.getvalue())

    def test_apikey_deletes_key(self):
        stderr = BytesIO()
        stdout = BytesIO()
        user = factory.make_user()
        existing_token = get_one(
            user.get_profile().get_authorisation_tokens())
        token_string = convert_tuple_to_string(
            get_creds_tuple(existing_token))
        call_command(
            'apikey', username=user.username, delete=token_string,
            stderr=stderr, stdout=stdout)
        self.assertEqual('', stderr.getvalue().strip())

        keys_after = user.get_profile().get_authorisation_tokens()
        self.assertEqual(0, len(keys_after))

    def test_apikey_rejects_mutually_exclusive_options(self):
        stderr = BytesIO()
        user = factory.make_user()
        self.assertRaises(
            SystemExit,
            call_command, 'apikey', username=user.username, generate=True,
            delete="foo", stderr=stderr)
        self.assertIn(
            "Specify one of --generate or --delete",
            stderr.getvalue())

    def test_apikey_rejects_deletion_of_bad_key(self):
        stderr = BytesIO()
        user = factory.make_user()
        self.assertRaises(
            SystemExit,
            call_command, 'apikey', username=user.username, delete="foo",
            stderr=stderr)
        self.assertIn(
            "Malformed credentials string", stderr.getvalue())

    def test_api_key_rejects_deletion_of_nonexistent_key(self):
        stderr = BytesIO()
        user = factory.make_user()
        existing_token = get_one(
            user.get_profile().get_authorisation_tokens())
        token_string = convert_tuple_to_string(
            get_creds_tuple(existing_token))
        call_command(
            'apikey', username=user.username, delete=token_string,
            stderr=stderr)
        self.assertEqual('', stderr.getvalue().strip())

        # Delete it again. Check that there's a sensible rejection.
        self.assertRaises(
            SystemExit,
            call_command, 'apikey', username=user.username,
            delete=token_string, stderr=stderr)
        self.assertIn("No matching api key found", stderr.getvalue())
