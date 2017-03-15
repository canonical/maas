# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver account views."""

__all__ = []

import http.client

from django.conf import settings
from django.contrib.auth import (
    REDIRECT_FIELD_NAME,
    SESSION_KEY,
)
from django.core.urlresolvers import reverse
from lxml.html import (
    fromstring,
    tostring,
)
from maasserver.testing import (
    extract_redirect,
    get_content_links,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestLoginLegacy(MAASServerTestCase):

    def test_login_contains_input_tags_if_user(self):
        factory.make_User()
        response = self.client.get('/accounts/login/')
        doc = fromstring(response.content)
        self.assertFalse(response.context_data['no_users'])
        self.assertEqual(1, len(doc.cssselect('input#id_username')))
        self.assertEqual(1, len(doc.cssselect('input#id_password')))

    def test_login_displays_createadmin_message_if_no_user(self):
        path = factory.make_string()
        self.patch(settings, 'MAAS_CLI', path)
        response = self.client.get('/accounts/login/')
        self.assertTrue(response.context_data['no_users'])
        self.assertEqual(path, response.context_data['create_command'])


class TestLogin(MAASServerTestCase):

    def test_login_redirects_when_authenticated(self):
        password = factory.make_string()
        user = factory.make_User(password=password)
        self.client.login(username=user.username, password=password)
        response = self.client.get('/accounts/login/')
        self.assertEqual('/', extract_redirect(response))

    def test_login_doesnt_redirect_to_logout_GET(self):
        password = factory.make_string()
        user = factory.make_User(password=password)
        response = self.client.post(
            '/accounts/login/?%s=%s' % (
                REDIRECT_FIELD_NAME, reverse('logout')),
            {'username': user.username, 'password': password})
        self.assertEqual('/', extract_redirect(response))

    def test_login_redirects_GET(self):
        password = factory.make_string()
        user = factory.make_User(password=password)
        response = self.client.post(
            '/accounts/login/?%s=%s' % (
                REDIRECT_FIELD_NAME, reverse('prefs')),
            {'username': user.username, 'password': password})
        self.assertEqual(reverse('prefs'), extract_redirect(response))

    def test_login_doesnt_redirect_to_logout_POST(self):
        password = factory.make_string()
        user = factory.make_User(password=password)
        response = self.client.post(
            '/accounts/login/', {
                'username': user.username,
                'password': password,
                REDIRECT_FIELD_NAME: reverse('logout'),
            })
        self.assertEqual('/', extract_redirect(response))

    def test_login_redirects_POST(self):
        password = factory.make_string()
        user = factory.make_User(password=password)
        response = self.client.post(
            '/accounts/login/', {
                'username': user.username,
                'password': password,
                REDIRECT_FIELD_NAME: reverse('prefs'),
            })
        self.assertEqual(reverse('prefs'), extract_redirect(response))

    def test_login_sets_autocomplete_off_in_production(self):
        self.patch(settings, 'DEBUG', False)
        factory.make_User()
        response = self.client.get('/accounts/login/')
        doc = fromstring(response.content)
        form = doc.cssselect("form")[0]
        self.assertIn(b'autocomplete="off"', tostring(form))

    def test_login_sets_autocomplete_on_in_debug_mode(self):
        self.patch(settings, 'DEBUG', True)
        factory.make_User()
        response = self.client.get('/accounts/login/')
        doc = fromstring(response.content)
        form = doc.cssselect("form")[0]
        self.assertNotIn(b'autocomplete="off"', tostring(form))


class TestLogout(MAASServerTestCase):

    def test_logout_doesnt_redirect_when_intro_not_completed(self):
        password = factory.make_string()
        user = factory.make_User(password=password, completed_intro=False)
        self.client.login(username=user.username, password=password)
        response = self.client.get(reverse('logout'))
        self.assertEqual(http.client.OK, response.status_code)

    def test_logout_link_present_on_homepage(self):
        password = factory.make_string()
        user = factory.make_User(password=password)
        self.client.login(username=user.username, password=password)
        response = self.client.get(reverse('index'))
        logout_link = reverse('logout')
        self.assertIn(
            logout_link,
            get_content_links(response, element='#user-options'))

    def test_loggout_uses_POST(self):
        # Using POST for logging out, along with Django's csrf_token
        # tag, guarantees that we're protected against CSRF attacks on
        # the loggout page.
        password = factory.make_string()
        user = factory.make_User(password=password)
        self.client.login(username=user.username, password=password)
        self.client.post(reverse('logout'))
        self.assertNotIn(SESSION_KEY, self.client.session)
