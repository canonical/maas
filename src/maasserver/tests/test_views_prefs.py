# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver preferences views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []


import httplib

from apiclient.creds import convert_tuple_to_string
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from lxml.html import fromstring
from maasserver.models import SSHKey
from maasserver.models.user import get_creds_tuple
from maasserver.testing import (
    extract_redirect,
    get_content_links,
    get_data,
    get_prefixed_form_data,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import LoggedInTestCase


class UserPrefsViewTest(LoggedInTestCase):

    def test_prefs_GET_profile(self):
        # The preferences page displays a form with the user's personal
        # information.
        user = self.logged_in_user
        user.last_name = 'Steve Bam'
        user.save()
        response = self.client.get('/account/prefs/')
        doc = fromstring(response.content)
        self.assertSequenceEqual(
            ['Steve Bam'],
            [elem.value for elem in
                doc.cssselect('input#id_profile-last_name')])

    def test_prefs_GET_api(self):
        # The preferences page displays the API access tokens.
        user = self.logged_in_user
        # Create a few tokens.
        for i in range(3):
            user.get_profile().create_authorisation_token()
        response = self.client.get('/account/prefs/')
        doc = fromstring(response.content)
        # The OAuth tokens are displayed.
        for token in user.get_profile().get_authorisation_tokens():
            # The token string is a compact representation of the keys.
            self.assertSequenceEqual(
                [convert_tuple_to_string(get_creds_tuple(token))],
                [elem.value.strip() for elem in
                    doc.cssselect('input#%s' % token.key)])

    def test_prefs_POST_profile(self):
        # The preferences page allows the user the update its profile
        # information.
        params = {
            'last_name': 'John Doe',
            'email': 'jon@example.com',
        }
        response = self.client.post(
            '/account/prefs/', get_prefixed_form_data('profile', params))

        self.assertEqual(httplib.FOUND, response.status_code)
        user = User.objects.get(id=self.logged_in_user.id)
        self.assertAttributes(user, params)

    def test_prefs_POST_password(self):
        # The preferences page allows the user to change his password.
        self.logged_in_user.set_password('password')
        old_pw = self.logged_in_user.password
        response = self.client.post(
            '/account/prefs/',
            get_prefixed_form_data(
                'password',
                {
                    'old_password': 'test',
                    'new_password1': 'new',
                    'new_password2': 'new',
                }))

        self.assertEqual(httplib.FOUND, response.status_code)
        user = User.objects.get(id=self.logged_in_user.id)
        # The password is SHA1ized, we just make sure that it has changed.
        self.assertNotEqual(old_pw, user.password)

    def test_prefs_displays_message_when_no_public_keys_are_configured(self):
        response = self.client.get('/account/prefs/')
        self.assertIn("No SSH key configured.", response.content)

    def test_prefs_displays_add_ssh_key_button(self):
        response = self.client.get('/account/prefs/')
        add_key_link = reverse('prefs-add-sshkey')
        self.assertIn(add_key_link, get_content_links(response))

    def test_prefs_displays_compact_representation_of_users_keys(self):
        _, keys = factory.make_user_with_keys(user=self.logged_in_user)
        response = self.client.get('/account/prefs/')
        for key in keys:
            self.assertIn(key.display_html(), response.content)

    def test_prefs_displays_link_to_delete_ssh_keys(self):
        _, keys = factory.make_user_with_keys(user=self.logged_in_user)
        response = self.client.get('/account/prefs/')
        links = get_content_links(response)
        for key in keys:
            del_key_link = reverse('prefs-delete-sshkey', args=[key.id])
            self.assertIn(del_key_link, links)


class KeyManagementTest(LoggedInTestCase):

    def test_add_key_GET(self):
        # The 'Add key' page displays a form to add a key.
        response = self.client.get(reverse('prefs-add-sshkey'))
        doc = fromstring(response.content)

        self.assertEqual(1, len(doc.cssselect('textarea#id_key')))
        # The page features a form that submits to itself.
        self.assertSequenceEqual(
            ['.'],
            [elem.get('action').strip() for elem in doc.cssselect(
                '#content form')])

    def test_add_key_POST_adds_key(self):
        key_string = get_data('data/test_rsa0.pub')
        response = self.client.post(
            reverse('prefs-add-sshkey'), {'key': key_string})

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertTrue(SSHKey.objects.filter(key=key_string).exists())

    def test_add_key_POST_fails_if_key_already_exists_for_the_user(self):
        key_string = get_data('data/test_rsa0.pub')
        key = SSHKey(user=self.logged_in_user, key=key_string)
        key.save()
        response = self.client.post(
            reverse('prefs-add-sshkey'), {'key': key_string})

        self.assertEqual(httplib.OK, response.status_code)
        self.assertIn(
            "This key has already been added for this user.",
            response.content)
        self.assertItemsEqual([key], SSHKey.objects.filter(key=key_string))

    def test_key_can_be_added_if_same_key_already_setup_for_other_user(self):
        key_string = get_data('data/test_rsa0.pub')
        key = SSHKey(user=factory.make_user(), key=key_string)
        key.save()
        response = self.client.post(
            reverse('prefs-add-sshkey'), {'key': key_string})
        new_key = SSHKey.objects.get(key=key_string, user=self.logged_in_user)

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertItemsEqual(
            [key, new_key], SSHKey.objects.filter(key=key_string))

    def test_delete_key_GET(self):
        # The 'Delete key' page displays a confirmation page with a form.
        key = factory.make_sshkey(self.logged_in_user)
        del_link = reverse('prefs-delete-sshkey', args=[key.id])
        response = self.client.get(del_link)
        doc = fromstring(response.content)

        self.assertIn(
            "Are you sure you want to delete the following key?",
            response.content)
        # The page features a form that submits to itself.
        self.assertSequenceEqual(
            ['.'],
            [elem.get('action').strip() for elem in doc.cssselect(
                '#content form')])

    def test_delete_key_GET_cannot_access_someone_elses_key(self):
        key = factory.make_sshkey(factory.make_user())
        del_link = reverse('prefs-delete-sshkey', args=[key.id])
        response = self.client.get(del_link)

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_delete_key_GET_nonexistent_key_redirects_to_prefs(self):
        # Deleting a nonexistent key requires no confirmation.  It just
        # "succeeds" instantaneously.
        key = factory.make_sshkey(self.logged_in_user)
        del_link = reverse('prefs-delete-sshkey', args=[key.id])
        key.delete()
        response = self.client.get(del_link)
        self.assertEqual('/account/prefs/', extract_redirect(response))

    def test_delete_key_POST(self):
        # A POST request deletes the key, and redirects to the prefs.
        key = factory.make_sshkey(self.logged_in_user)
        del_link = reverse('prefs-delete-sshkey', args=[key.id])
        response = self.client.post(del_link, {'post': 'yes'})

        self.assertEqual('/account/prefs/', extract_redirect(response))
        self.assertFalse(SSHKey.objects.filter(id=key.id).exists())

    def test_delete_key_POST_ignores_nonexistent_key(self):
        # Deleting a key that's already been deleted?  Basically that's
        # success.
        key = factory.make_sshkey(self.logged_in_user)
        del_link = reverse('prefs-delete-sshkey', args=[key.id])
        key.delete()
        response = self.client.post(del_link, {'post': 'yes'})
        self.assertEqual('/account/prefs/', extract_redirect(response))
