# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test custom commands, as found in src/maasserver/management/commands."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from codecs import getwriter
from io import BytesIO

from apiclient.creds import convert_tuple_to_string
import django
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from maasserver.management.commands import createadmin
from maasserver.models.user import get_creds_tuple
from maasserver.testing.factory import factory
from maasserver.utils.orm import get_one
from maastesting.djangotestcase import DjangoTestCase
from testtools.matchers import StartsWith


def assertCommandErrors(runner, command, *args, **kwargs):
    """Assert that the given django command fails.

    This method returns the error text.
    """
    # This helper helps dealing with the difference in how
    # call_command() reports failure between Django 1.4 and Django
    # 1.5. See the 4th bullet point ("Management commands do not raise...")
    # in
    # https://docs.djangoproject.com/en/dev/releases/1.5/#minor-features
    if django.VERSION >= (1, 5):
        # Django >= 1.5 puts error text in exception.
        exception = runner.assertRaises(
            CommandError, call_command, command, *args, **kwargs)
        return unicode(exception)
    else:
        # Django < 1.5 prints error text on stderr.
        stderr = BytesIO()
        kwargs['stderr'] = stderr
        runner.assertRaises(
            SystemExit, call_command, command, *args, **kwargs)
        return stderr.getvalue().strip()


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
        # The documentation starts with a link target: "region-controller-api".
        self.assertThat(result[:100], StartsWith('.. _region-controller-api:'))
        # It also contains a ReST title (not indented).
        self.assertIn('===', result[:100])

    def test_createadmin_prompts_for_password_if_not_given(self):
        stderr = BytesIO()
        stdout = BytesIO()
        username = factory.make_name('user')
        password = factory.getRandomString()
        email = factory.getRandomEmail()
        self.patch(createadmin, 'prompt_for_password').return_value = password

        call_command(
            'createadmin', username=username, email=email, stdout=stdout,
            stderr=stderr)
        user = User.objects.get(username=username)

        self.assertEquals('', stderr.getvalue().strip())
        self.assertEquals('', stdout.getvalue().strip())
        self.assertTrue(user.check_password(password))

    def test_createadmin_requires_email(self):
        username = factory.getRandomString()
        password = factory.getRandomString()
        error_text = assertCommandErrors(
            self, 'createadmin',
            username=username, password=password)
        self.assertIn(
            "You must provide an email with --email.",
            error_text)

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

    def test_prompt_for_password_returns_selected_password(self):
        password = factory.getRandomString()
        self.patch(createadmin, 'getpass').return_value = password

        self.assertEqual(password, createadmin.prompt_for_password())

    def test_prompt_for_password_checks_for_consistent_password(self):
        self.patch(createadmin, 'getpass', lambda x: factory.getRandomString())

        self.assertRaises(
            createadmin.InconsistentPassword,
            createadmin.prompt_for_password)

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
        error_text = assertCommandErrors(self, 'apikey')
        self.assertIn(
            "You must provide a username with --username.",
            error_text)

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
            get_creds_tuple(expected_token)) + '\n'
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
            get_creds_tuple(expected_token)) + '\n'
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
        user = factory.make_user()
        error_text = assertCommandErrors(
            self, 'apikey',
            username=user.username, generate=True, delete="foo")
        self.assertIn(
            "Specify one of --generate or --delete",
            error_text)

    def test_apikey_rejects_deletion_of_bad_key(self):
        user = factory.make_user()
        error_text = assertCommandErrors(
            self, 'apikey',
            username=user.username, delete="foo")
        self.assertIn(
            "Malformed credentials string",
            error_text)

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
        error_text = assertCommandErrors(
            self, 'apikey', username=user.username, delete=token_string)
        self.assertIn(
            "No matching api key found", error_text)
