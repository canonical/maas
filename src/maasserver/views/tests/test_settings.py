# Copyright 2012-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver settings views."""

__all__ = []

import http.client
import random
from unittest import skip

from django.contrib.auth.models import User
from lxml.html import fromstring
from maasserver.enum import BOOT_RESOURCE_TYPE
from maasserver.models import Config, PackageRepository, UserProfile
from maasserver.models.event import Event
from maasserver.models.signals import bootsources
from maasserver.storage_layouts import get_storage_layout_choices
from maasserver.testing import extract_redirect, get_prefixed_form_data
from maasserver.testing.factory import factory
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.django_urls import reverse
from maasserver.utils.orm import reload_object
from provisioningserver.drivers.osystem import (
    OperatingSystemRegistry,
    WindowsOS,
)
from provisioningserver.drivers.osystem.windows import REQUIRE_LICENSE_KEY
from provisioningserver.events import AUDIT


class SettingsTest(MAASServerTestCase):
    def test_settings_redirects_to_index_when_intro_not_completed(self):
        self.client.login(user=factory.make_admin())
        Config.objects.set_config("completed_intro", False)
        response = self.client.get(reverse("settings"))
        self.assertEqual(reverse("index"), extract_redirect(response))

    def test_settings_redirects_to_settings_user(self):
        admin = factory.make_admin()
        self.client.login(user=admin)
        response = self.client.get(reverse("settings"))
        self.assertEqual(reverse("settings_users"), extract_redirect(response))

    def test_settings_list_users(self):
        # The settings page displays a list of the users with links to view,
        # delete or edit each user. Note that the link to delete the the
        # logged-in user is not display.
        admin = factory.make_admin()
        self.client.login(user=admin)
        [factory.make_User() for _ in range(3)]
        users = UserProfile.objects.all_users()
        response = self.client.get(reverse("settings_users"))
        doc = fromstring(response.content)
        tab = doc.cssselect("#users")[0]
        all_links = [elem.get("href") for elem in tab.cssselect("a")]
        # "Add a user" link.
        self.assertIn(reverse("accounts-add"), all_links)
        for user in users:
            # Use the longhand way of matching an ID here - instead of tr#id -
            # because the ID may contain non [a-zA-Z-]+ characters. These are
            # not allowed in symbols, which is how cssselect treats text
            # following "#" in a selector.
            rows = tab.cssselect('tr[id="%s"]' % user.username)
            # Only one row for the user.
            self.assertEqual(1, len(rows))
            row = rows[0]
            links = [elem.get("href") for elem in row.cssselect("a")]
            # The username is shown...
            self.assertSequenceEqual(
                [user.username],
                [link.text.strip() for link in row.cssselect("a.user")],
            )
            # ...with a link to view the user's profile.
            self.assertSequenceEqual(
                [reverse("accounts-view", args=[user.username])],
                [link.get("href") for link in row.cssselect("a.user")],
            )
            if user != admin:
                # A link to edit the user is shown.
                self.assertIn(
                    reverse("accounts-edit", args=[user.username]), links
                )
                # A link to delete the user is shown.
                self.assertIn(
                    reverse("accounts-del", args=[user.username]), links
                )
            else:
                # No link to delete the user is shown if the user is the
                # logged-in user.
                self.assertNotIn(
                    reverse("accounts-del", args=[user.username]), links
                )
                # A link to user preferences page is shown
                self.assertIn(reverse("prefs", args=None), links)
            # account type is reported
            self.assertIn(
                "Local", [elem.text.strip() for elem in row.cssselect("td")]
            )

    def test_setting_list_external_users(self):
        admin = factory.make_admin()
        # login before external auth is enabled to avoid requiring macaroons
        self.client.login(user=admin)
        Config.objects.set_config(
            "external_auth_url", "http://auth.example.com"
        )
        user = factory.make_User()
        response = self.client.get(reverse("settings_users"))
        doc = fromstring(response.content)
        tab = doc.cssselect("#users")[0]
        rows = tab.cssselect('tr[id="%s"]' % user.username)
        # Only one row for the user.
        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertIn(
            "External", [elem.text.strip() for elem in row.cssselect("td")]
        )

    def test_settings_external_auth_include_users_message(self):
        admin = factory.make_admin()
        # login before external auth is enabled to avoid requiring macaroons
        self.client.login(user=admin)
        Config.objects.set_config(
            "external_auth_url", "http://auth.example.com"
        )
        response = self.client.get(reverse("settings_users"))
        doc = fromstring(response.content)
        [notification] = doc.cssselect(".p-notification__response")
        self.assertIn(
            "MAAS is configured with external authentication",
            notification.text,
        )

    def test_settings_no_users_message_without_external_auth(self):
        self.client.login(user=factory.make_admin())
        response = self.client.get(reverse("settings_users"))
        doc = fromstring(response.content)
        self.assertEqual(doc.cssselect(".p-notification__response"), [])

    @skip("XXX: GavinPanella 2016-07-07 bug=1599931: Fails spuriously.")
    def test_settings_maas_POST(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()
        self.client.login(user=factory.make_admin())
        new_name = factory.make_string()
        response = self.client.post(
            reverse("settings_general"),
            get_prefixed_form_data(
                prefix="maas", data={"maas_name": new_name}
            ),
        )
        self.assertEqual(
            http.client.FOUND, response.status_code, response.content
        )
        self.assertEqual(new_name, Config.objects.get_config("maas_name"))

    def test_proxy_proxy_POST(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()
        self.client.login(user=factory.make_admin())
        new_proxy = "http://%s.example.com:1234/" % factory.make_string()
        response = self.client.post(
            reverse("settings_network"),
            get_prefixed_form_data(
                prefix="proxy",
                data={
                    "http_proxy": new_proxy,
                    "enable_http_proxy": True,
                    "use_peer_proxy": True,
                },
            ),
        )
        self.assertEqual(
            http.client.FOUND, response.status_code, response.content
        )
        self.assertEqual(new_proxy, Config.objects.get_config("http_proxy"))
        self.assertTrue(Config.objects.get_config("enable_http_proxy"))
        self.assertTrue(Config.objects.get_config("use_peer_proxy"))

    def test_settings_dns_POST(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()
        self.client.login(user=factory.make_admin())
        new_upstream = "8.8.8.8 8.8.4.4"
        new_ipv4_subnet = factory.make_ipv4_network()
        new_ipv6_subnet = factory.make_ipv6_network()
        new_subnets = "%s %s" % (new_ipv4_subnet, new_ipv6_subnet)
        response = self.client.post(
            reverse("settings_network"),
            get_prefixed_form_data(
                prefix="dns",
                data={
                    "upstream_dns": new_upstream,
                    "dnssec_validation": "no",
                    "dns_trusted_acl": new_subnets,
                },
            ),
        )
        self.assertEqual(
            http.client.FOUND, response.status_code, response.content
        )
        self.assertEqual(
            new_upstream, Config.objects.get_config("upstream_dns")
        )
        self.assertEqual("no", Config.objects.get_config("dnssec_validation"))
        self.assertEqual(
            new_subnets, Config.objects.get_config("dns_trusted_acl")
        )

    def test_settings_ntp_POST(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()
        self.client.login(user=factory.make_admin())
        new_servers = "ntp.example.com"
        response = self.client.post(
            reverse("settings_network"),
            get_prefixed_form_data(
                prefix="ntp",
                data={"ntp_servers": new_servers, "ntp_external_only": True},
            ),
        )
        self.assertEqual(
            http.client.FOUND, response.status_code, response.content
        )
        self.assertEqual(new_servers, Config.objects.get_config("ntp_servers"))
        self.assertTrue(Config.objects.get_config("ntp_external_only"))

    def test_settings_commissioning_POST(self):
        self.client.login(user=factory.make_admin())
        ubuntu = factory.make_default_ubuntu_release_bootable()

        new_commissioning = ubuntu.name.split("/")[1]
        response = self.client.post(
            reverse("settings_general"),
            get_prefixed_form_data(
                prefix="commissioning",
                data={"commissioning_distro_series": new_commissioning},
            ),
        )

        self.assertEqual(http.client.FOUND, response.status_code)
        self.assertEqual(
            (new_commissioning,),
            (Config.objects.get_config("commissioning_distro_series"),),
        )

    def test_settings_vcenter_POST(self):
        self.client.login(user=factory.make_admin())
        vcenter = {
            "vcenter_server": factory.make_name("vcenter_server"),
            "vcenter_username": factory.make_name("vcenter_username"),
            "vcenter_password": factory.make_name("vcenter_password"),
            "vcenter_datacenter": factory.make_name("vcenter_datacenter"),
        }
        response = self.client.post(
            reverse("settings_general"),
            get_prefixed_form_data(prefix="vcenter", data=vcenter),
        )
        self.assertEqual(http.client.FOUND, response.status_code)
        self.assertDictEqual(
            vcenter, Config.objects.get_configs(vcenter.keys())
        )

    def test_settings_hides_license_keys_if_no_OS_supporting_keys(self):
        self.client.login(user=factory.make_admin())
        response = self.client.get(reverse("settings_general"))
        doc = fromstring(response.content)
        license_keys = doc.cssselect('a[href="/MAAS/settings/license-keys/"]')
        self.assertEqual(
            0, len(license_keys), "Didn't hide the license key section."
        )

    def test_settings_shows_license_keys_if_OS_supporting_keys(self):
        self.client.login(user=factory.make_admin())
        osystem = factory.make_name("osystem")
        release = random.choice(REQUIRE_LICENSE_KEY)
        distro_series = "%s/%s" % (osystem, release)
        drv = WindowsOS()
        drv.title = osystem
        OperatingSystemRegistry.register_item(osystem, drv)
        factory.make_BootResource(
            name=distro_series,
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            extra={"title": drv.get_release_title(release)},
        )
        self.addCleanup(OperatingSystemRegistry.unregister_item, osystem)
        response = self.client.get(reverse("settings_general"))
        doc = fromstring(response.content)
        license_keys = doc.cssselect('a[href="/MAAS/settings/license-keys/"]')
        self.assertEqual(
            1, len(license_keys), "Didn't show the license key section."
        )

    def test_settings_third_party_drivers_POST(self):
        self.client.login(user=factory.make_admin())
        new_enable_third_party_drivers = factory.pick_bool()
        response = self.client.post(
            reverse("settings_general"),
            get_prefixed_form_data(
                prefix="third_party_drivers",
                data={
                    "enable_third_party_drivers": (
                        new_enable_third_party_drivers
                    )
                },
            ),
        )

        self.assertEqual(http.client.FOUND, response.status_code)
        self.assertEqual(
            (new_enable_third_party_drivers,),
            (Config.objects.get_config("enable_third_party_drivers"),),
        )

    def test_settings_storage_POST(self):
        self.client.login(user=factory.make_admin())
        new_storage_layout = factory.pick_choice(get_storage_layout_choices())
        new_enable_disk_erasing_on_release = factory.pick_bool()
        response = self.client.post(
            reverse("settings_storage"),
            get_prefixed_form_data(
                prefix="storage_settings",
                data={
                    "default_storage_layout": new_storage_layout,
                    "enable_disk_erasing_on_release": (
                        new_enable_disk_erasing_on_release
                    ),
                },
            ),
        )

        self.assertEqual(http.client.FOUND, response.status_code)
        self.assertEqual(
            (new_storage_layout, new_enable_disk_erasing_on_release),
            (
                Config.objects.get_config("default_storage_layout"),
                Config.objects.get_config("enable_disk_erasing_on_release"),
            ),
        )

    def test_settings_deploy_POST(self):
        self.client.login(user=factory.make_admin())
        osystem = make_usable_osystem(self)
        osystem_name = osystem["name"]
        release_name = osystem["default_release"]
        response = self.client.post(
            reverse("settings_general"),
            get_prefixed_form_data(
                prefix="deploy",
                data={
                    "default_osystem": osystem_name,
                    "default_distro_series": "%s/%s"
                    % (osystem_name, release_name),
                },
            ),
        )

        self.assertEqual(
            http.client.FOUND, response.status_code, response.content
        )
        self.assertEqual(
            (osystem_name, release_name),
            (
                Config.objects.get_config("default_osystem"),
                Config.objects.get_config("default_distro_series"),
            ),
        )

    def test_settings_ubuntu_POST(self):
        self.client.login(user=factory.make_admin())
        new_main_archive = "http://test.example.com/archive"
        new_ports_archive = "http://test2.example.com/archive"
        response = self.client.post(
            reverse("settings_general"),
            get_prefixed_form_data(
                prefix="ubuntu",
                data={
                    "main_archive": new_main_archive,
                    "ports_archive": new_ports_archive,
                },
            ),
        )

        self.assertEqual(
            http.client.FOUND, response.status_code, response.content
        )
        self.assertEqual(
            (new_main_archive, new_ports_archive),
            (
                PackageRepository.get_main_archive().url,
                PackageRepository.get_ports_archive().url,
            ),
        )

    def test_settings_kernelopts_POST(self):
        self.client.login(user=factory.make_admin())
        new_kernel_opts = "--new='arg' --flag=1 other"
        response = self.client.post(
            reverse("settings_general"),
            get_prefixed_form_data(
                prefix="kernelopts", data={"kernel_opts": new_kernel_opts}
            ),
        )

        self.assertEqual(http.client.FOUND, response.status_code)
        self.assertEqual(
            new_kernel_opts, Config.objects.get_config("kernel_opts")
        )


class NonAdminSettingsTest(MAASServerTestCase):
    def test_settings_import_boot_images_reserved_to_admin(self):
        self.client.login(user=factory.make_User())
        response = self.client.post(
            reverse("settings"), {"import_all_boot_images": 1}
        )
        self.assertEqual(reverse("login"), extract_redirect(response))


# Settable attributes on User.
user_attributes = ["email", "is_superuser", "last_name", "username"]


def make_user_attribute_params(user):
    """Compose a dict of form parameters for a user's account data.

    By default, each attribute in the dict maps to the user's existing value
    for that atrribute.
    """
    return {attr: getattr(user, attr) for attr in user_attributes}


def make_password_params(password):
    """Create a dict of parameters for setting a given password."""
    return {"password1": password, "password2": password}


def subset_dict(input_dict, keys_subset):
    """Return a subset of `input_dict` restricted to `keys_subset`.

    All keys in `keys_subset` must be in `input_dict`.
    """
    return {key: input_dict[key] for key in keys_subset}


class UserManagementTest(MAASServerTestCase):
    def test_add_user_POST(self):
        self.client.login(user=factory.make_admin())
        params = {
            "username": factory.make_string(),
            "last_name": factory.make_string(30),
            "email": factory.make_email_address(),
            "is_superuser": factory.pick_bool(),
        }
        password = factory.make_string()
        params.update(make_password_params(password))

        response = self.client.post(reverse("accounts-add"), params)
        self.assertEqual(http.client.FOUND, response.status_code)
        user = User.objects.get(username=params["username"])
        self.assertAttributes(user, subset_dict(params, user_attributes))
        self.assertTrue(user.check_password(password))
        self.assertTrue(user.userprofile.is_local)

    def test_add_user_with_external_auth_not_local(self):
        admin = factory.make_admin()
        # login before external auth is enabled to avoid requiring macaroons
        self.client.login(user=admin)
        Config.objects.set_config(
            "external_auth_url", "http://auth.example.com"
        )
        params = {
            "username": factory.make_string(),
            "last_name": factory.make_string(30),
            "email": factory.make_email_address(),
            "is_superuser": factory.pick_bool(),
        }
        password = factory.make_string()
        params.update(make_password_params(password))
        self.client.post(reverse("accounts-add"), params)
        user = User.objects.get(username=params["username"])
        self.assertFalse(user.userprofile.is_local)

    def test_add_user_POST_creates_audit_event(self):
        self.client.login(user=factory.make_admin())
        username = factory.make_string()
        params = {
            "username": username,
            "last_name": factory.make_string(30),
            "email": factory.make_email_address(),
            "is_superuser": False,
        }
        password = factory.make_string()
        params.update(make_password_params(password))

        self.client.post(reverse("accounts-add"), params)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEquals(event.description, "Created user '%s'." % username)

    def test_add_admin_POST_creates_audit_event(self):
        self.client.login(user=factory.make_admin())
        username = factory.make_string()
        params = {
            "username": username,
            "last_name": factory.make_string(30),
            "email": factory.make_email_address(),
            "is_superuser": True,
        }
        password = factory.make_string()
        params.update(make_password_params(password))

        self.client.post(reverse("accounts-add"), params)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEquals(event.description, "Created admin '%s'." % username)

    def test_edit_user_POST_profile_updates_attributes(self):
        self.client.login(user=factory.make_admin())
        user = factory.make_User()
        params = make_user_attribute_params(user)
        params.update(
            {
                "last_name": factory.make_name("Newname"),
                "email": "new-%s@example.com" % factory.make_string(),
                "is_superuser": True,
                "username": factory.make_name("newname"),
            }
        )

        response = self.client.post(
            reverse("accounts-edit", args=[user.username]),
            get_prefixed_form_data("profile", params),
        )

        self.assertEqual(http.client.FOUND, response.status_code)
        self.assertAttributes(
            reload_object(user), subset_dict(params, user_attributes)
        )

    def test_edit_user_POST_profile_update_creates_audit_event(self):
        self.client.login(user=factory.make_admin())
        user = factory.make_User()
        new_username = factory.make_name("newname")
        params = make_user_attribute_params(user)
        last_name = factory.make_name("Newname")
        email = "new-%s@example.com" % factory.make_string()
        is_superuser = True
        params.update(
            {
                "last_name": last_name,
                "email": email,
                "is_superuser": is_superuser,
                "username": new_username,
            }
        )

        self.client.post(
            reverse("accounts-edit", args=[user.username]),
            get_prefixed_form_data("profile", params),
        )
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEquals(
            event.description,
            (
                "Updated user profile (username: %s, full name: %s, "
                + "email: %s, administrator: %s)"
            )
            % (new_username, last_name, email, is_superuser),
        )

    def test_edit_user_POST_updates_password(self):
        self.client.login(user=factory.make_admin())
        user = factory.make_User()
        new_password = factory.make_string()
        params = make_password_params(new_password)
        response = self.client.post(
            reverse("accounts-edit", args=[user.username]),
            get_prefixed_form_data("password", params),
        )
        self.assertEqual(http.client.FOUND, response.status_code)
        self.assertTrue(reload_object(user).check_password(new_password))

    def test_edit_user_POST_password_update_creates_audit_event(self):
        self.client.login(user=factory.make_admin())
        user = factory.make_User()
        new_password = factory.make_string()
        params = make_password_params(new_password)
        self.client.post(
            reverse("accounts-edit", args=[user.username]),
            get_prefixed_form_data("password", params),
        )
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEquals(event.description, "Updated password.")

    def test_delete_user_GET(self):
        # The user delete page displays a confirmation page with a form.
        self.client.login(user=factory.make_admin())
        user = factory.make_User()
        del_link = reverse("accounts-del", args=[user.username])
        response = self.client.get(del_link)
        doc = fromstring(response.content)
        confirmation_message = (
            'Are you sure you want to delete the user "%s"?' % user.username
        )
        self.assertSequenceEqual(
            [confirmation_message],
            [elem.text.strip() for elem in doc.cssselect("h2")],
        )

    def test_delete_user_POST(self):
        # A POST request to the user delete finally deletes the user.
        self.client.login(user=factory.make_admin())
        user = factory.make_User()
        user_id = user.id
        del_link = reverse("accounts-del", args=[user.username])
        response = self.client.post(del_link, {"post": "yes"})
        self.assertEqual(http.client.FOUND, response.status_code)
        self.assertItemsEqual([], User.objects.filter(id=user_id))

    def test_delete_user_POST_creates_audit_event(self):
        self.client.login(user=factory.make_admin())
        user = factory.make_User()
        del_link = reverse("accounts-del", args=[user.username])
        self.client.post(del_link, {"post": "yes"})
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEquals(
            event.description, "Deleted user '%s'." % user.username
        )

    def test_delete_admin_POST_creates_audit_event(self):
        self.client.login(user=factory.make_admin())
        user = factory.make_admin()
        del_link = reverse("accounts-del", args=[user.username])
        self.client.post(del_link, {"post": "yes"})
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEquals(
            event.description, "Deleted admin '%s'." % user.username
        )

    def test_view_user(self):
        # The user page feature the basic information about the user.
        self.client.login(user=factory.make_admin())
        user = factory.make_User()
        del_link = reverse("accounts-view", args=[user.username])
        response = self.client.get(del_link)
        doc = fromstring(response.content)
        content_text = doc.cssselect("#content")[0].text_content()
        self.assertIn(user.username, content_text)
        self.assertIn(user.email, content_text)

    def test_account_views_are_routable_for_full_range_of_usernames(self):
        # Usernames can include characters in the regex [\w.@+-].
        self.client.login(user=factory.make_admin())
        user = factory.make_User(username="abc-123@example.com")
        for view in "edit", "view", "del":
            path = reverse("accounts-%s" % view, args=[user.username])
            self.assertIsInstance(path, (bytes, str))
