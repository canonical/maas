# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver API."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import httplib

from django.contrib.auth.models import User
from lxml.html import fromstring
from maasserver.testing import LoggedInTestCase


class UserPrefsViewTest(LoggedInTestCase):

    def test_prefs_GET_profile(self):
        # The preferences page (profile tab) displays a form with the
        # user's personal information.
        user = self.logged_in_user
        user.first_name = 'Steve'
        user.last_name = 'Bam'
        user.save()
        response = self.client.get('/account/prefs/')
        doc = fromstring(response.content)
        self.assertSequenceEqual(
            ['User preferences for %s' % user.username],
            [elem.text for elem in doc.cssselect('h2')])
        self.assertSequenceEqual(
            ['Bam'],
            [elem.value for elem in
                doc.cssselect('input#id_profile-last_name')])
        self.assertSequenceEqual(
            ['Steve'],
            [elem.value for elem in
                doc.cssselect('input#id_profile-first_name')])

    def test_prefs_GET_api(self):
        # The preferences page (api tab) displays the API access tokens.
        user = self.logged_in_user
        response = self.client.get('/account/prefs/?tab=1')
        doc = fromstring(response.content)
        # The consumer key and the token key/secret are displayed.
        consumer = user.get_profile().get_authorisation_consumer()
        token = user.get_profile().get_authorisation_token()
        self.assertSequenceEqual(
            [consumer.key],
            [elem.text.strip() for elem in
                doc.cssselect('div#consumer_key')])
        self.assertSequenceEqual(
            [token.key],
            [elem.text.strip() for elem in
                doc.cssselect('div#token_key')])
        self.assertSequenceEqual(
            [token.secret],
            [elem.text.strip() for elem in
                doc.cssselect('div#token_secret')])

    def test_prefs_POST_profile(self):
        # The preferences page allows the user the update its profile
        # information.
        response = self.client.post(
            '/account/prefs/',
            {
                'profile_submit': 1, 'profile-first_name': 'John',
                'profile-last_name': 'Doe', 'profile-email': 'jon@example.com'
            })

        self.assertEqual(httplib.FOUND, response.status_code)
        user = User.objects.get(id=self.logged_in_user.id)
        self.assertEqual('John', user.first_name)
        self.assertEqual('Doe', user.last_name)
        self.assertEqual('jon@example.com', user.email)

    def test_prefs_POST_password(self):
        # The preferences page allows the user to change his password.
        self.logged_in_user.set_password('password')
        old_pw = self.logged_in_user.password
        response = self.client.post(
            '/account/prefs/',
            {
                'password_submit': 1,
                'password-old_password': 'test',
                'password-new_password1': 'new',
                'password-new_password2': 'new',
            })
        self.assertEqual(httplib.FOUND, response.status_code)
        user = User.objects.get(id=self.logged_in_user.id)
        # The password is SHA1ized, we just make sure that it has changed.
        self.assertNotEqual(old_pw, user.password)
