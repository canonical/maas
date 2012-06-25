# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver account views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from django.conf import settings
from lxml.html import fromstring
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase


class TestLogin(TestCase):

    def test_login_contains_input_tags_if_user(self):
        factory.make_user()
        response = self.client.get('/accounts/login/')
        doc = fromstring(response.content)
        self.assertFalse(response.context['no_users'])
        self.assertEqual(1, len(doc.cssselect('input#id_username')))
        self.assertEqual(1, len(doc.cssselect('input#id_password')))

    def test_login_displays_createsuperuser_message_if_no_user(self):
        path = factory.getRandomString()
        self.patch(settings, 'MAAS_CLI', path)
        response = self.client.get('/accounts/login/')
        self.assertTrue(response.context['no_users'])
        self.assertEqual(path, response.context['create_command'])
