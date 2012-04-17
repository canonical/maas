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
import os

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from maasserver.models import FileStorage
from maasserver.testing.factory import factory
from maastesting.testcase import TestCase


class TestCommands(TestCase):
    """Happy-path integration testing for custom commands.

    Detailed testing does not belong here.  If there's any complexity at all
    in a command's code, it should be extracted and unit-tested separately.
    """

    def test_gc(self):
        upload_dir = os.path.join(settings.MEDIA_ROOT, FileStorage.upload_dir)
        os.makedirs(upload_dir)
        self.addCleanup(os.removedirs, upload_dir)
        call_command('gc')
        # The test is that we get here without errors.
        pass

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
        users = list(User.objects.filter(username=username))

        self.assertEquals('', stderr.getvalue().strip())
        self.assertEquals('', stdout.getvalue().strip())
        self.assertEqual(1, len(users))  # One user with that name.
        self.assertTrue(users[0].check_password(password))
        self.assertTrue(users[0].is_superuser)
        self.assertEqual(email, users[0].email)

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
