# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver account views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django.conf import settings
from lxml.html import fromstring
from maasserver.testing import extract_redirect
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestLogin(MAASServerTestCase):

    def test_login_contains_input_tags_if_user(self):
        factory.make_user()
        response = self.client.get('/accounts/login/')
        doc = fromstring(response.content)
        self.assertFalse(response.context['no_users'])
        self.assertEqual(1, len(doc.cssselect('input#id_username')))
        self.assertEqual(1, len(doc.cssselect('input#id_password')))

    def test_login_displays_createadmin_message_if_no_user(self):
        path = factory.getRandomString()
        self.patch(settings, 'MAAS_CLI', path)
        response = self.client.get('/accounts/login/')
        self.assertTrue(response.context['no_users'])
        self.assertEqual(path, response.context['create_command'])

    def test_login_redirects_when_authenticated(self):
        password = factory.getRandomString()
        user = factory.make_user(password=password)
        self.client.login(username=user.username, password=password)
        response = self.client.get('/accounts/login/')
        self.assertEqual('/', extract_redirect(response))
