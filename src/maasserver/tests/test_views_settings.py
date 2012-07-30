# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver settings views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import httplib

from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from lxml.html import fromstring
from maasserver.enum import NODE_AFTER_COMMISSIONING_ACTION
from maasserver.models import (
    Config,
    UserProfile,
    )
from maasserver.testing import (
    get_prefixed_form_data,
    reload_object,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import AdminLoggedInTestCase


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

    def test_settings_maas_and_network_POST(self):
        # Disable the DNS machinery so that we can skip the required
        # setup.
        self.patch(settings, "DNS_CONNECT", False)
        new_name = factory.getRandomString()
        new_domain = factory.getRandomString()
        new_enable_dns = factory.getRandomBoolean()
        response = self.client.post(
            reverse('settings'),
            get_prefixed_form_data(
                prefix='maas_and_network',
                data={
                    'maas_name': new_name,
                    'enlistment_domain': new_domain,
                    'enable_dns ': new_enable_dns,
                }))

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(new_name, Config.objects.get_config('maas_name'))
        self.assertEqual(
            new_domain, Config.objects.get_config('enlistment_domain'))
        self.assertEqual(
            new_enable_dns, Config.objects.get_config('enable_dns'))

    def test_settings_commissioning_POST(self):
        new_after_commissioning = factory.getRandomEnum(
            NODE_AFTER_COMMISSIONING_ACTION)
        new_check_compatibility = factory.getRandomBoolean()
        response = self.client.post(
            '/settings/',
            get_prefixed_form_data(
                prefix='commissioning',
                data={
                    'after_commissioning': new_after_commissioning,
                    'check_compatibility': new_check_compatibility,
                }))

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(
            new_after_commissioning,
            Config.objects.get_config('after_commissioning'))
        self.assertEqual(
            new_check_compatibility,
            Config.objects.get_config('check_compatibility'))

    def test_settings_ubuntu_POST(self):
        new_fallback_master_archive = factory.getRandomBoolean()
        new_keep_mirror_list_uptodate = factory.getRandomBoolean()
        new_fetch_new_releases = factory.getRandomBoolean()
        choices = Config.objects.get_config('update_from_choice')
        new_update_from = factory.getRandomChoice(choices)
        response = self.client.post(
            '/settings/',
            get_prefixed_form_data(
                prefix='ubuntu',
                data={
                    'fallback_master_archive': new_fallback_master_archive,
                    'keep_mirror_list_uptodate': new_keep_mirror_list_uptodate,
                    'fetch_new_releases': new_fetch_new_releases,
                    'update_from': new_update_from,
                }))

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(
            new_fallback_master_archive,
            Config.objects.get_config('fallback_master_archive'))
        self.assertEqual(
            new_keep_mirror_list_uptodate,
            Config.objects.get_config('keep_mirror_list_uptodate'))
        self.assertEqual(
            new_fetch_new_releases,
            Config.objects.get_config('fetch_new_releases'))
        self.assertEqual(
            new_update_from, Config.objects.get_config('update_from'))

    def test_settings_add_archive_POST(self):
        choices = Config.objects.get_config('update_from_choice')
        response = self.client.post(
            '/settings/archives/add/',
            data={'archive_name': 'my.hostname.com'}
        )
        new_choices = Config.objects.get_config('update_from_choice')

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertItemsEqual(
            choices + [['my.hostname.com', 'my.hostname.com']],
            new_choices)


# Settable attributes on User.
user_attributes = [
    'email',
    'is_superuser',
    'last_name',
    'username',
    ]


def make_user_attribute_params(user):
    """Compose a dict of form parameters for a user's account data.

    By default, each attribute in the dict maps to the user's existing value
    for that atrribute.
    """
    return {
        attr: getattr(user, attr)
        for attr in user_attributes
        }


def make_password_params(password):
    """Create a dict of parameters for setting a given password."""
    return {
        'password1': password,
        'password2': password,
    }


def subset_dict(input_dict, keys_subset):
    """Return a subset of `input_dict` restricted to `keys_subset`.

    All keys in `keys_subset` must be in `input_dict`.
    """
    return {key: input_dict[key] for key in keys_subset}


class UserManagementTest(AdminLoggedInTestCase):

    def test_add_user_POST(self):
        params = {
            'username': factory.getRandomString(),
            'last_name': factory.getRandomString(30),
            'email': factory.getRandomEmail(),
            'is_superuser': factory.getRandomBoolean(),
        }
        password = factory.getRandomString()
        params.update(make_password_params(password))

        response = self.client.post(reverse('accounts-add'), params)
        self.assertEqual(httplib.FOUND, response.status_code)
        user = User.objects.get(username=params['username'])
        self.assertAttributes(user, subset_dict(params, user_attributes))
        self.assertTrue(user.check_password(password))

    def test_edit_user_POST_profile_updates_attributes(self):
        user = factory.make_user()
        params = make_user_attribute_params(user)
        params.update({
            'last_name': factory.make_name('Newname'),
            'email': 'new-%s@example.com' % factory.getRandomString(),
            'is_superuser': True,
            'username': factory.make_name('newname'),
            })

        response = self.client.post(
            reverse('accounts-edit', args=[user.username]),
            get_prefixed_form_data('profile', params))

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertAttributes(
            reload_object(user), subset_dict(params, user_attributes))

    def test_edit_user_POST_updates_password(self):
        user = factory.make_user()
        new_password = factory.getRandomString()
        params = make_password_params(new_password)
        response = self.client.post(
            reverse('accounts-edit', args=[user.username]),
            get_prefixed_form_data('password', params))
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertTrue(reload_object(user).check_password(new_password))

    def test_delete_user_GET(self):
        # The user delete page displays a confirmation page with a form.
        user = factory.make_user()
        del_link = reverse('accounts-del', args=[user.username])
        response = self.client.get(del_link)
        doc = fromstring(response.content)
        confirmation_message = (
            'Are you sure you want to delete the user "%s"?' %
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
        response = self.client.post(del_link, {'post': 'yes'})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertItemsEqual([], User.objects.filter(id=user_id))

    def test_view_user(self):
        # The user page feature the basic information about the user.
        user = factory.make_user()
        del_link = reverse('accounts-view', args=[user.username])
        response = self.client.get(del_link)
        doc = fromstring(response.content)
        content_text = doc.cssselect('#content')[0].text_content()
        self.assertIn(user.username, content_text)
        self.assertIn(user.email, content_text)
