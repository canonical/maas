# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver preferences views."""

__all__ = []

import http.client

from apiclient.creds import convert_tuple_to_string
from lxml.html import fromstring
from maasserver.models import Config, Event, SSLKey
from maasserver.models.user import get_creds_tuple
from maasserver.testing import get_data, get_prefixed_form_data
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.django_urls import reverse
from maasserver.utils.orm import reload_object
from provisioningserver.events import AUDIT


class UserPrefsViewTest(MAASServerTestCase):
    def test_prefs_GET_profile(self):
        # The preferences page displays a form with the user's personal
        # information.
        user = factory.make_User()
        user.last_name = "Steve Bam"
        user.save()
        self.client.login(user=user)
        response = self.client.get("/account/prefs/")
        doc = fromstring(response.content)
        self.assertSequenceEqual(
            ["Steve Bam"],
            [
                elem.value
                for elem in doc.cssselect("input#id_profile-last_name")
            ],
        )

    def test_prefs_GET_api(self):
        # The preferences page displays the API access tokens.
        user = factory.make_User()
        self.client.login(user=user)
        # Create a few tokens.
        for _ in range(3):
            user.userprofile.create_authorisation_token()
        response = self.client.get("/account/prefs/")
        doc = fromstring(response.content)
        # The OAuth tokens are displayed.
        for token in user.userprofile.get_authorisation_tokens():
            # The token string is a compact representation of the keys.
            directive = doc.cssselect(
                'li[data-maas-pref-key="%s"]' % token.key
            )[0]
            self.assertSequenceEqual(
                [convert_tuple_to_string(get_creds_tuple(token))],
                [elem.value.strip() for elem in directive.cssselect("input")],
            )

    def test_prefs_POST_profile(self):
        # The preferences page allows the user the update its profile
        # information.
        user = factory.make_User()
        self.client.login(user=user)
        params = {"last_name": "John Doe", "email": "jon@example.com"}
        response = self.client.post(
            "/account/prefs/", get_prefixed_form_data("profile", params)
        )

        self.assertEqual(http.client.FOUND, response.status_code)
        user = reload_object(user)
        self.assertAttributes(user, params)

    def test_prefs_post_profile_external_auth(self):
        user = factory.make_User()
        self.client.login(user=user)
        # log in the user locally so it doesn't need macaroons
        Config.objects.set_config("external_auth_url", "http://example.com")
        params = {"last_name": "John Doe", "email": "jon@example.com"}
        response = self.client.post(
            "/account/prefs/", get_prefixed_form_data("profile", params)
        )
        self.assertEqual(http.client.METHOD_NOT_ALLOWED, response.status_code)

    def test_prefs_GET_profile_does_not_have_autofocus_attributes(self):
        user = factory.make_User()
        self.client.login(user=user)
        response = self.client.get("/account/prefs/")
        self.assertNotIn(b"autofocus", response.content)

    def test_prefs_POST_password(self):
        # The preferences page allows the user to change their password.
        user = factory.make_User()
        self.client.login(username=user.username, password="test")
        user.set_password("password")
        old_pw = user.password
        response = self.client.post(
            "/account/prefs/",
            get_prefixed_form_data(
                "password",
                {
                    "old_password": "test",
                    "new_password1": "new",
                    "new_password2": "new",
                },
            ),
        )

        self.assertEqual(http.client.FOUND, response.status_code)
        user = reload_object(user)
        # The password is SHA1ized, we just make sure that it has changed.
        self.assertNotEqual(old_pw, user.password)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(event.description, "Updated password.")

    def test_prefs_POST_password_external_auth(self):
        user = factory.make_User()
        self.client.login(username=user.username, password="test")
        user.set_password("password")
        # log in the user locally so it doesn't need macaroons
        Config.objects.set_config("external_auth_url", "http://example.com")
        response = self.client.post(
            "/account/prefs/",
            get_prefixed_form_data(
                "password",
                {
                    "old_password": "test",
                    "new_password1": "new",
                    "new_password2": "new",
                },
            ),
        )
        self.assertEqual(http.client.METHOD_NOT_ALLOWED, response.status_code)

    def test_no_password_section_present_with_local_info(self):
        user = factory.make_User()
        self.client.login(user=user)
        response = self.client.get("/account/prefs/")
        doc = fromstring(response.content)
        self.assertEqual(len(doc.cssselect("#password")), 1)

    def test_no_password_section_with_external_auth(self):
        user = factory.make_User()
        self.client.login(user=user)
        # log in the user locally so it doesn't need macaroons
        Config.objects.set_config("external_auth_url", "http://example.com")
        response = self.client.get("/account/prefs/")
        doc = fromstring(response.content)
        self.assertEqual(len(doc.cssselect("#password")), 0)

    def test_profile_readonly_with_external_auth(self):
        user = factory.make_User()
        self.client.login(user=user)
        # log in the user locally so it doesn't need macaroons
        Config.objects.set_config("external_auth_url", "http://example.com")
        response = self.client.get("/account/prefs/")
        doc = fromstring(response.content)
        self.assertEqual(
            doc.cssselect('#profile input[name="profile-last_name"]')[0].get(
                "disabled"
            ),
            "disabled",
        )
        self.assertEqual(
            doc.cssselect('#profile input[name="profile-email"]')[0].get(
                "disabled"
            ),
            "disabled",
        )

    def test_create_ssl_key_POST(self):
        user = factory.make_admin()
        self.client.login(user=user)
        key_string = get_data("data/test_x509_0.pem")
        params = {"key": key_string}
        response = self.client.post(reverse("prefs-add-sslkey"), params)
        sslkey = SSLKey.objects.get(user=user)
        self.assertEqual(http.client.FOUND, response.status_code)
        self.assertIsNotNone(sslkey)
        self.assertEqual(key_string, sslkey.key)

    def test_delete_ssl_key_POST_creates_audit_event(self):
        user = factory.make_admin()
        self.client.login(user=user)
        sslkey = factory.make_SSLKey(user)
        keyid = sslkey.id
        del_link = reverse("prefs-delete-sslkey", args=[keyid])
        self.client.post(del_link, {"post": "yes"})
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(event.description, "Deleted SSL key id='%s'." % keyid)
