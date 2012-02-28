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
from django.core.urlresolvers import reverse
from lxml.html import fromstring
from maasserver.models import UserProfile
from maasserver.testing import (
    factory,
    LoggedInTestCase,
    )


class UserPrefsViewTest(LoggedInTestCase):

    def test_prefs_GET_profile(self):
        # The preferences page displays a form with the user's personal
        # information.
        user = self.logged_in_user
        user.first_name = 'Steve'
        user.last_name = 'Bam'
        user.save()
        response = self.client.get('/account/prefs/')
        doc = fromstring(response.content)
        self.assertSequenceEqual(
            ['Bam'],
            [elem.value for elem in
                doc.cssselect('input#id_profile-last_name')])
        self.assertSequenceEqual(
            ['Steve'],
            [elem.value for elem in
                doc.cssselect('input#id_profile-first_name')])

    def test_prefs_GET_api(self):
        # The preferences page displays the API access tokens.
        user = self.logged_in_user
        # Create a few tokens.
        for i in xrange(3):
            user.get_profile().create_authorisation_token()
        response = self.client.get('/account/prefs/')
        doc = fromstring(response.content)
        # The OAuth tokens are displayed.
        for token in user.get_profile().get_authorisation_tokens():
            consumer = token.consumer
            # The token string is a compact representation of the keys.
            token_string = '%s:%s:%s' % (consumer.key, token.key, token.secret)
            self.assertSequenceEqual(
                [token_string],
                [elem.text.strip() for elem in
                    doc.cssselect('td#%s' % token.key)])

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


class AdminLoggedInTestCase(LoggedInTestCase):

    def setUp(self):
        super(AdminLoggedInTestCase, self).setUp()
        # Promote the logged-in user to admin.
        self.logged_in_user.is_superuser = True
        self.logged_in_user.save()


class SettingsTest(AdminLoggedInTestCase):

    def test_settings_list_users(self):
        # The settings page displays a list of the users with links to view,
        # delete or edit each user. Note that the link to delete the the
        # logged-in user is not display.
        [factory.make_user() for i in range(3)]
        users = UserProfile.objects.all_users()
        response = self.client.get('/settings/')
        doc = fromstring(response.content)
        tab = doc.cssselect('#users')[0]
        all_links = [elem.get('href') for elem in tab.cssselect('a')]
        # "Add a user" link.
        self.assertIn(reverse('accounts-add'), all_links)
        for user in users:
            rows = tab.cssselect('tr#%s' % user.username)
            # Only one row for the user.
            self.assertEqual(1, len(rows))
            row = rows[0]
            links = [elem.get('href') for elem in row.cssselect('a')]
            # The username is shown...
            self.assertSequenceEqual(
                [user.username],
                [link.text.strip() for link in row.cssselect('a.user')])
            # ...with a link to view the user's profile.
            self.assertSequenceEqual(
                [reverse('accounts-view', args=[user.username])],
                [link.get('href') for link in row.cssselect('a.user')])
            # A link to edit the user is shown.
            self.assertIn(
                reverse('accounts-edit', args=[user.username]), links)
            if user != self.logged_in_user:
                # A link to delete the user is shown.
                self.assertIn(
                    reverse('accounts-del', args=[user.username]), links)
            else:
                # No link to delete the user is shown if the user is the
                # logged-in user.
                self.assertNotIn(
                    reverse('accounts-del', args=[user.username]), links)


class UserManagementTest(AdminLoggedInTestCase):

    def test_add_user_POST(self):
        response = self.client.post(
            reverse('accounts-add'),
            {
                'username': 'my_user',
                'password1': 'pw',
                'password2': 'pw',
            })
        self.assertEqual(httplib.FOUND, response.status_code)
        users = list(User.objects.filter(username='my_user'))
        self.assertEqual(1, len(users))
        self.assertTrue(users[0].check_password('pw'))

    def test_delete_user_GET(self):
        # The user delete page displays a confirmation page with a form.
        user = factory.make_user()
        del_link = reverse('accounts-del', args=[user.username])
        response = self.client.get(del_link)
        doc = fromstring(response.content)
        confirmation_message = (
            'Are you sure you want to delete user %s?' %
            user.username)
        self.assertSequenceEqual(
            [confirmation_message],
            [elem.text.strip() for elem in doc.cssselect('h2')])
        # The page features a form that submits to itself.
        self.assertSequenceEqual(
            ['.'],
            [elem.get('action').strip() for elem in doc.cssselect(
                '#content form')])

    def test_delete_user_POST(self):
        # A POST request to the user delete finally deletes the user.
        user = factory.make_user()
        user_id = user.id
        del_link = reverse('accounts-del', args=[user.username])
        response = self.client.post(
            del_link,
            {
                'post': 'yes',
            })
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertFalse(User.objects.filter(id=user_id).exists())

    def test_view_user(self):
        # The user page feature the basic information about the user.
        user = factory.make_user()
        del_link = reverse('accounts-view', args=[user.username])
        response = self.client.get(del_link)
        doc = fromstring(response.content)
        content_text = doc.cssselect('#content')[0].text_content()
        self.assertIn(user.username, content_text)
        self.assertIn(user.email, content_text)
