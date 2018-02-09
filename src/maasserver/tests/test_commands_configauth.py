# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the configauth command."""

import unittest

from django.core.management import call_command
from maasserver.management.commands import configauth
from maasserver.models import Config
from maasserver.testing.testcase import MAASServerTestCase


class TestChangeAuthCommand(MAASServerTestCase):

    def setUp(self):
        super().setUp()
        self.read_input = self.patch(configauth, 'read_input')
        self.read_input.return_value = ''

    def test_configauth_changes_external_auth_url_local_empty_string(self):
        Config.objects.set_config(
            'external_auth_url', 'http://example.com/idm')
        call_command('configauth', external_auth_url='')

        self.assertEqual(
            '', Config.objects.get_config('external_auth_url'))

    def test_configauth_changes_external_auth_url_local_none(self):
        Config.objects.set_config(
            'external_auth_url', 'http://example.com/idm')
        call_command('configauth', external_auth_url='none')

        self.assertEqual(
            '', Config.objects.get_config('external_auth_url'))

    def test_configauth_changes_external_auth_url_url(self):
        call_command('configauth', external_auth_url='http://example.com/idm')

        self.assertEqual(
            'http://example.com/idm',
            Config.objects.get_config('external_auth_url'))

    def test_configauth_changes_auth_prompts(self):
        self.read_input.return_value = 'http://idm.example.com/'
        call_command('configauth')

        self.assertEqual(
            'http://idm.example.com/',
            Config.objects.get_config('external_auth_url'))

    def test_configauth_changes_auth_prompt_default(self):
        self.read_input.return_value = ''
        call_command('configauth')

        self.assertEqual(
            '', Config.objects.get_config('external_auth_url'))

    def test_configauth_changes_auth_prompt_default_existing(self):
        Config.objects.set_config(
            'external_auth_url', 'http://example.com/idm')
        self.read_input.return_value = ''
        call_command('configauth')

        self.assertEqual(
            'http://example.com/idm',
            Config.objects.get_config('external_auth_url'))

    def test_configauth_changes_auth_invalid_url(self):
        self.assertRaises(
            configauth.InvalidURLError,
            call_command, 'configauth', external_auth_url='example.com')


class TestIsValidAuthSource(unittest.TestCase):

    def test_valid_schemes(self):
        for scheme in ['http', 'https']:
            url = '{}://example.com/idm'.format(scheme)
            self.assertTrue(configauth.is_valid_auth_url(url))

    def test_invalid_schemes(self):
        for scheme in ['ftp', 'git+ssh']:
            url = '{}://example.com/idm'.format(scheme)
            self.assertFalse(configauth.is_valid_auth_url(url))
