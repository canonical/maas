# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver settings views."""

__all__ = []

import http.client
from unittest import skip

from django.contrib.auth.models import User
from lxml.html import fromstring
from maasserver.clusterrpc.testing.osystems import (
    make_rpc_osystem,
    make_rpc_release,
)
from maasserver.models import (
    Config,
    PackageRepository,
    UserProfile,
)
from maasserver.models.event import Event
from maasserver.models.signals import bootsources
from maasserver.storage_layouts import get_storage_layout_choices
from maasserver.testing import (
    extract_redirect,
    get_prefixed_form_data,
)
from maasserver.testing.factory import factory
from maasserver.testing.osystems import (
    make_usable_osystem,
    patch_usable_osystems,
)
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.django_urls import reverse
from maasserver.utils.orm import reload_object
from maasserver.views import settings as settings_view
from provisioningserver.events import AUDIT


class SettingsTest(MAASServerTestCase):

    def test_settings_redirects_to_index_when_intro_not_completed(self):
        self.client_log_in()
        Config.objects.set_config('completed_intro', False)
        response = self.client.get(reverse('settings'))
        self.assertEqual('/', extract_redirect(response))

    def test_settings_list_users(self):
        # The settings page displays a list of the users with links to view,
        # delete or edit each user. Note that the link to delete the the
        # logged-in user is not display.
        self.client_log_in(as_admin=True)
        [factory.make_User() for _ in range(3)]
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

    @skip("XXX: GavinPanella 2016-07-07 bug=1599931: Fails spuriously.")
    def test_settings_maas_POST(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()
        self.client_log_in(as_admin=True)
        new_name = factory.make_string()
        response = self.client.post(
            reverse('settings'),
            get_prefixed_form_data(
                prefix='maas',
                data={
                    'maas_name': new_name,
                }))
        self.assertEqual(
            http.client.FOUND, response.status_code, response.content)
        self.assertEqual(
            new_name, Config.objects.get_config('maas_name'))

    def test_proxy_proxy_POST(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()
        self.client_log_in(as_admin=True)
        new_proxy = "http://%s.example.com:1234/" % factory.make_string()
        response = self.client.post(
            reverse('settings'),
            get_prefixed_form_data(
                prefix='proxy',
                data={
                    'http_proxy': new_proxy,
                    'enable_http_proxy': True,
                    'use_peer_proxy': True,
                }))
        self.assertEqual(
            http.client.FOUND, response.status_code, response.content)
        self.assertEqual(new_proxy, Config.objects.get_config('http_proxy'))
        self.assertTrue(Config.objects.get_config('enable_http_proxy'))
        self.assertTrue(Config.objects.get_config('use_peer_proxy'))

    def test_settings_dns_POST(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()
        self.client_log_in(as_admin=True)
        new_upstream = "8.8.8.8"
        response = self.client.post(
            reverse('settings'),
            get_prefixed_form_data(
                prefix='dns',
                data={
                    'upstream_dns': new_upstream,
                    'dnssec_validation': 'no',
                }))
        self.assertEqual(
            http.client.FOUND, response.status_code, response.content)
        self.assertEqual(
            new_upstream, Config.objects.get_config('upstream_dns'))
        self.assertEqual('no', Config.objects.get_config('dnssec_validation'))

    def test_settings_ntp_POST(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()
        self.client_log_in(as_admin=True)
        new_servers = "ntp.example.com"
        response = self.client.post(
            reverse('settings'),
            get_prefixed_form_data(
                prefix='ntp',
                data={
                    'ntp_servers': new_servers,
                    'ntp_external_only': True,
                }))
        self.assertEqual(
            http.client.FOUND, response.status_code, response.content)
        self.assertEqual(new_servers, Config.objects.get_config('ntp_servers'))
        self.assertTrue(Config.objects.get_config('ntp_external_only'))

    def test_settings_commissioning_POST(self):
        self.client_log_in(as_admin=True)
        release = make_rpc_release(can_commission=True)
        osystem = make_rpc_osystem('ubuntu', releases=[release])
        patch_usable_osystems(self, [osystem])

        new_commissioning = release['name']
        response = self.client.post(
            reverse('settings'),
            get_prefixed_form_data(
                prefix='commissioning',
                data={
                    'commissioning_distro_series': (
                        new_commissioning),
                }))

        self.assertEqual(http.client.FOUND, response.status_code)
        self.assertEqual(
            (
                new_commissioning,
            ),
            (
                Config.objects.get_config('commissioning_distro_series'),
            ))

    def test_settings_hides_license_keys_if_no_OS_supporting_keys(self):
        self.client_log_in(as_admin=True)
        response = self.client.get(reverse('settings'))
        doc = fromstring(response.content)
        license_keys = doc.cssselect('#license_keys')
        self.assertEqual(
            0, len(license_keys), "Didn't hide the license key section.")

    def test_settings_shows_license_keys_if_OS_supporting_keys(self):
        self.client_log_in(as_admin=True)
        release = make_rpc_release(requires_license_key=True)
        osystem = make_rpc_osystem(releases=[release])
        self.patch(
            settings_view,
            'gen_all_known_operating_systems').return_value = [osystem]
        response = self.client.get(reverse('settings'))
        doc = fromstring(response.content)
        license_keys = doc.cssselect('#license_keys')
        self.assertEqual(
            1, len(license_keys), "Didn't show the license key section.")

    def test_settings_third_party_drivers_POST(self):
        self.client_log_in(as_admin=True)
        new_enable_third_party_drivers = factory.pick_bool()
        response = self.client.post(
            reverse('settings'),
            get_prefixed_form_data(
                prefix='third_party_drivers',
                data={
                    'enable_third_party_drivers': (
                        new_enable_third_party_drivers),
                }))

        self.assertEqual(http.client.FOUND, response.status_code)
        self.assertEqual(
            (
                new_enable_third_party_drivers,
            ),
            (
                Config.objects.get_config('enable_third_party_drivers'),
            ))

    def test_settings_storage_POST(self):
        self.client_log_in(as_admin=True)
        new_storage_layout = factory.pick_choice(get_storage_layout_choices())
        new_enable_disk_erasing_on_release = factory.pick_bool()
        response = self.client.post(
            reverse('settings'),
            get_prefixed_form_data(
                prefix='storage_settings',
                data={
                    'default_storage_layout': new_storage_layout,
                    'enable_disk_erasing_on_release': (
                        new_enable_disk_erasing_on_release),
                }))

        self.assertEqual(http.client.FOUND, response.status_code)
        self.assertEqual(
            (
                new_storage_layout,
                new_enable_disk_erasing_on_release,
            ),
            (
                Config.objects.get_config('default_storage_layout'),
                Config.objects.get_config('enable_disk_erasing_on_release'),
            ))

    def test_settings_deploy_POST(self):
        self.client_log_in(as_admin=True)
        osystem = make_usable_osystem(self)
        osystem_name = osystem['name']
        release_name = osystem['default_release']
        response = self.client.post(
            reverse('settings'),
            get_prefixed_form_data(
                prefix='deploy',
                data={
                    'default_osystem': osystem_name,
                    'default_distro_series': '%s/%s' % (
                        osystem_name,
                        release_name,
                        ),
                }))

        self.assertEqual(
            http.client.FOUND, response.status_code, response.content)
        self.assertEqual(
            (
                osystem_name,
                release_name,
            ),
            (
                Config.objects.get_config('default_osystem'),
                Config.objects.get_config('default_distro_series'),
            ))

    def test_settings_ubuntu_POST(self):
        self.client_log_in(as_admin=True)
        new_main_archive = 'http://test.example.com/archive'
        new_ports_archive = 'http://test2.example.com/archive'
        response = self.client.post(
            reverse('settings'),
            get_prefixed_form_data(
                prefix='ubuntu',
                data={
                    'main_archive': new_main_archive,
                    'ports_archive': new_ports_archive,
                }))

        self.assertEqual(
            http.client.FOUND, response.status_code, response.content)
        self.assertEqual(
            (
                new_main_archive,
                new_ports_archive,
            ),
            (
                PackageRepository.get_main_archive().url,
                PackageRepository.get_ports_archive().url,
            ))

    def test_settings_kernelopts_POST(self):
        self.client_log_in(as_admin=True)
        new_kernel_opts = "--new='arg' --flag=1 other"
        response = self.client.post(
            reverse('settings'),
            get_prefixed_form_data(
                prefix='kernelopts',
                data={
                    'kernel_opts': new_kernel_opts,
                }))

        self.assertEqual(http.client.FOUND, response.status_code)
        self.assertEqual(
            new_kernel_opts,
            Config.objects.get_config('kernel_opts'))


class NonAdminSettingsTest(MAASServerTestCase):

    def test_settings_import_boot_images_reserved_to_admin(self):
        self.client_log_in()
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


class UserManagementTest(MAASServerTestCase):

    def test_add_user_POST(self):
        self.client_log_in(as_admin=True)
        params = {
            'username': factory.make_string(),
            'last_name': factory.make_string(30),
            'email': factory.make_email_address(),
            'is_superuser': factory.pick_bool(),
        }
        password = factory.make_string()
        params.update(make_password_params(password))

        response = self.client.post(reverse('accounts-add'), params)
        self.assertEqual(http.client.FOUND, response.status_code)
        user = User.objects.get(username=params['username'])
        self.assertAttributes(user, subset_dict(params, user_attributes))
        self.assertTrue(user.check_password(password))

    def test_add_user_POST_creates_audit_event(self):
        self.client_log_in(as_admin=True)
        username = factory.make_string()
        params = {
            'username': username,
            'last_name': factory.make_string(30),
            'email': factory.make_email_address(),
            'is_superuser': False,
        }
        password = factory.make_string()
        params.update(make_password_params(password))

        self.client.post(reverse('accounts-add'), params)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEquals(
            event.description,
            "User %s" % username + " created by '%(username)s'.")

    def test_add_admin_POST_creates_audit_event(self):
        self.client_log_in(as_admin=True)
        username = factory.make_string()
        params = {
            'username': username,
            'last_name': factory.make_string(30),
            'email': factory.make_email_address(),
            'is_superuser': True,
        }
        password = factory.make_string()
        params.update(make_password_params(password))

        self.client.post(reverse('accounts-add'), params)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEquals(
            event.description,
            "Admin %s" % username + " created by '%(username)s'.")

    def test_edit_user_POST_profile_updates_attributes(self):
        self.client_log_in(as_admin=True)
        user = factory.make_User()
        params = make_user_attribute_params(user)
        params.update({
            'last_name': factory.make_name('Newname'),
            'email': 'new-%s@example.com' % factory.make_string(),
            'is_superuser': True,
            'username': factory.make_name('newname'),
            })

        response = self.client.post(
            reverse('accounts-edit', args=[user.username]),
            get_prefixed_form_data('profile', params))

        self.assertEqual(http.client.FOUND, response.status_code)
        self.assertAttributes(
            reload_object(user), subset_dict(params, user_attributes))

    def test_edit_user_POST_profile_update_creates_audit_event(self):
        self.client_log_in(as_admin=True)
        user = factory.make_User()
        new_username = factory.make_name('newname')
        params = make_user_attribute_params(user)
        last_name = factory.make_name('Newname')
        email = 'new-%s@example.com' % factory.make_string()
        is_superuser = True
        params.update({
            'last_name': last_name,
            'email': email,
            'is_superuser': is_superuser,
            'username': new_username,
            })

        self.client.post(
            reverse('accounts-edit', args=[user.username]),
            get_prefixed_form_data('profile', params))
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEquals(
            event.description, (
                "User profile (username: %s, full name: %s, email: %s, "
                "administrator: %s)"
            ) % (new_username, last_name, email, is_superuser) +
            " updated by '%(username)s'.")

    def test_edit_user_POST_updates_password(self):
        self.client_log_in(as_admin=True)
        user = factory.make_User()
        new_password = factory.make_string()
        params = make_password_params(new_password)
        response = self.client.post(
            reverse('accounts-edit', args=[user.username]),
            get_prefixed_form_data('password', params))
        self.assertEqual(http.client.FOUND, response.status_code)
        self.assertTrue(reload_object(user).check_password(new_password))

    def test_edit_user_POST_password_update_creates_audit_event(self):
        self.client_log_in(as_admin=True)
        user = factory.make_User()
        new_password = factory.make_string()
        params = make_password_params(new_password)
        self.client.post(
            reverse('accounts-edit', args=[user.username]),
            get_prefixed_form_data('password', params))
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEquals(
            event.description, "Password changed for '%(username)s'.")

    def test_delete_user_GET(self):
        # The user delete page displays a confirmation page with a form.
        self.client_log_in(as_admin=True)
        user = factory.make_User()
        del_link = reverse('accounts-del', args=[user.username])
        response = self.client.get(del_link)
        doc = fromstring(response.content)
        confirmation_message = (
            'Are you sure you want to delete the user "%s"?' %
            user.username)
        self.assertSequenceEqual(
            [confirmation_message],
            [elem.text.strip() for elem in doc.cssselect('h2')])

    def test_delete_user_POST(self):
        # A POST request to the user delete finally deletes the user.
        self.client_log_in(as_admin=True)
        user = factory.make_User()
        user_id = user.id
        del_link = reverse('accounts-del', args=[user.username])
        response = self.client.post(del_link, {'post': 'yes'})
        self.assertEqual(http.client.FOUND, response.status_code)
        self.assertItemsEqual([], User.objects.filter(id=user_id))

    def test_delete_user_POST_creates_audit_event(self):
        self.client_log_in(as_admin=True)
        user = factory.make_User()
        del_link = reverse('accounts-del', args=[user.username])
        self.client.post(del_link, {'post': 'yes'})
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEquals(
            event.description,
            "User %s" % user.username + " deleted by '%(username)s'.")

    def test_delete_admin_POST_creates_audit_event(self):
        self.client_log_in(as_admin=True)
        user = factory.make_admin()
        del_link = reverse('accounts-del', args=[user.username])
        self.client.post(del_link, {'post': 'yes'})
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEquals(
            event.description,
            "Admin %s" % user.username + " deleted by '%(username)s'.")

    def test_view_user(self):
        # The user page feature the basic information about the user.
        self.client_log_in(as_admin=True)
        user = factory.make_User()
        del_link = reverse('accounts-view', args=[user.username])
        response = self.client.get(del_link)
        doc = fromstring(response.content)
        content_text = doc.cssselect('#content')[0].text_content()
        self.assertIn(user.username, content_text)
        self.assertIn(user.email, content_text)

    def test_account_views_are_routable_for_full_range_of_usernames(self):
        # Usernames can include characters in the regex [\w.@+-].
        self.client_log_in(as_admin=True)
        user = factory.make_User(username="abc-123@example.com")
        for view in "edit", "view", "del":
            path = reverse("accounts-%s" % view, args=[user.username])
            self.assertIsInstance(path, (bytes, str))
