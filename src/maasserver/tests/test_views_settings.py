# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver settings views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib

from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from lxml.html import fromstring
from maasserver.enum import (
    DISTRO_SERIES,
    NODE_AFTER_COMMISSIONING_ACTION,
    NODEGROUP_STATUS,
    )
from maasserver.models import (
    Config,
    nodegroup as nodegroup_module,
    UserProfile,
    )
from maasserver.testing import (
    extract_redirect,
    get_prefixed_form_data,
    reload_object,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    AdminLoggedInTestCase,
    LoggedInTestCase,
    )
from mock import (
    ANY,
    call,
    )


class SettingsTest(AdminLoggedInTestCase):

    def test_settings_list_users(self):
        # The settings page displays a list of the users with links to view,
        # delete or edit each user. Note that the link to delete the the
        # logged-in user is not display.
        [factory.make_user() for i in range(3)]
        users = UserProfile.objects.all_users()
        response = self.client.get(reverse('settings'))
        doc = fromstring(response.content)
        tab = doc.cssselect('#users')[0]
        all_links = [elem.get('href') for elem in tab.cssselect('a')]
        # "Add a user" link.
        self.assertIn(reverse('accounts-add'), all_links)
        for user in users:
            # Use the longhand way of matching an ID here - instead of tr#id -
            # because the ID may contain non [a-zA-Z-]+ characters. These are
            # not allowed in symbols, which is how cssselect treats text
            # following "#" in a selector.
            rows = tab.cssselect('tr[id="%s"]' % user.username)
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
        new_proxy = "http://%s.example.com:1234/" % factory.getRandomString()
        response = self.client.post(
            reverse('settings'),
            get_prefixed_form_data(
                prefix='maas_and_network',
                data={
                    'maas_name': new_name,
                    'enlistment_domain': new_domain,
                    'http_proxy': new_proxy,
                }))
        self.assertEqual(httplib.FOUND, response.status_code, response.content)
        self.assertEqual(
            (new_name,
             new_domain,
             new_proxy),
            (Config.objects.get_config('maas_name'),
             Config.objects.get_config('enlistment_domain'),
             Config.objects.get_config('http_proxy')))

    def test_settings_commissioning_POST(self):
        new_after_commissioning = factory.getRandomEnum(
            NODE_AFTER_COMMISSIONING_ACTION)
        new_check_compatibility = factory.getRandomBoolean()
        new_commissioning_distro_series = factory.getRandomEnum(DISTRO_SERIES)
        response = self.client.post(
            reverse('settings'),
            get_prefixed_form_data(
                prefix='commissioning',
                data={
                    'after_commissioning': new_after_commissioning,
                    'check_compatibility': new_check_compatibility,
                    'commissioning_distro_series': (
                        new_commissioning_distro_series),
                }))

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(
            (
                new_after_commissioning,
                new_check_compatibility,
                new_commissioning_distro_series,
            ),
            (
                Config.objects.get_config('after_commissioning'),
                Config.objects.get_config('check_compatibility'),
                Config.objects.get_config('commissioning_distro_series'),
            ))

    def test_settings_ubuntu_POST(self):
        new_main_archive = 'http://test.example.com/archive'
        new_ports_archive = 'http://test2.example.com/archive'
        new_cloud_images_archive = 'http://test3.example.com/archive'
        new_default_distro_series = factory.getRandomEnum(DISTRO_SERIES)
        response = self.client.post(
            reverse('settings'),
            get_prefixed_form_data(
                prefix='ubuntu',
                data={
                    'main_archive': new_main_archive,
                    'ports_archive': new_ports_archive,
                    'cloud_images_archive': new_cloud_images_archive,
                    'default_distro_series': new_default_distro_series,
                }))

        self.assertEqual(httplib.FOUND, response.status_code, response.content)
        self.assertEqual(
            (
                new_main_archive,
                new_ports_archive,
                new_cloud_images_archive,
                new_default_distro_series,
            ),
            (
                Config.objects.get_config('main_archive'),
                Config.objects.get_config('ports_archive'),
                Config.objects.get_config('cloud_images_archive'),
                Config.objects.get_config('default_distro_series'),
            ))

    def test_settings_kernelopts_POST(self):
        new_kernel_opts = "--new='arg' --flag=1 other"
        response = self.client.post(
            reverse('settings'),
            get_prefixed_form_data(
                prefix='kernelopts',
                data={
                    'kernel_opts': new_kernel_opts,
                }))

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(
            new_kernel_opts,
            Config.objects.get_config('kernel_opts'))

    def test_settings_contains_form_to_accept_all_nodegroups(self):
        factory.make_node_group(status=NODEGROUP_STATUS.PENDING),
        response = self.client.get(reverse('settings'))
        doc = fromstring(response.content)
        forms = doc.cssselect('form#accept_all_pending_nodegroups')
        self.assertEqual(1, len(forms))

    def test_settings_contains_form_to_reject_all_nodegroups(self):
        factory.make_node_group(status=NODEGROUP_STATUS.PENDING),
        response = self.client.get(reverse('settings'))
        doc = fromstring(response.content)
        forms = doc.cssselect('form#reject_all_pending_nodegroups')
        self.assertEqual(1, len(forms))

    def test_settings_accepts_all_pending_nodegroups_POST(self):
        nodegroups = {
            factory.make_node_group(status=NODEGROUP_STATUS.PENDING),
            factory.make_node_group(status=NODEGROUP_STATUS.PENDING),
        }
        response = self.client.post(
            reverse('settings'), {'mass_accept_submit': 1})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(
            [reload_object(nodegroup).status for nodegroup in nodegroups],
            [NODEGROUP_STATUS.ACCEPTED] * 2)

    def test_settings_rejects_all_pending_nodegroups_POST(self):
        nodegroups = {
            factory.make_node_group(status=NODEGROUP_STATUS.PENDING),
            factory.make_node_group(status=NODEGROUP_STATUS.PENDING),
        }
        response = self.client.post(
            reverse('settings'), {'mass_reject_submit': 1})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(
            [reload_object(nodegroup).status for nodegroup in nodegroups],
            [NODEGROUP_STATUS.REJECTED] * 2)

    def test_settings_import_boot_images_calls_tasks(self):
        recorder = self.patch(nodegroup_module, 'import_boot_images')
        accepted_nodegroups = [
            factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED),
            factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED),
        ]
        response = self.client.post(
            reverse('settings'), {'import_all_boot_images': 1})
        self.assertEqual(httplib.FOUND, response.status_code)
        calls = [
            call(queue=nodegroup.work_queue, kwargs=ANY)
            for nodegroup in accepted_nodegroups
        ]
        self.assertItemsEqual(calls, recorder.apply_async.call_args_list)

    def test_cluster_no_boot_images_message_displayed_if_no_boot_images(self):
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED)
        response = self.client.get(reverse('settings'))
        document = fromstring(response.content)
        nodegroup_row = document.xpath("//tr[@id='%s']" % nodegroup.uuid)[0]
        self.assertIn('no boot images', nodegroup_row.text_content())


class NonAdminSettingsTest(LoggedInTestCase):

    def test_settings_import_boot_images_reserved_to_admin(self):
        response = self.client.post(
            reverse('settings'), {'import_all_boot_images': 1})
        self.assertEqual(reverse('login'), extract_redirect(response))


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

    def test_account_views_are_routable_for_full_range_of_usernames(self):
        # Usernames can include characters in the regex [\w.@+-].
        user = factory.make_user(username="abc-123@example.com")
        for view in "edit", "view", "del":
            path = reverse("accounts-%s" % view, args=[user.username])
            self.assertIsInstance(path, (bytes, unicode))
