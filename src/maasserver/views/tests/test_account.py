# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from http import HTTPStatus
import http.client

from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.urls import reverse

from maasserver.models.event import Event
from maasserver.models.user import create_auth_token, get_auth_tokens
from maasserver.secrets import SecretManager
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import json_load_bytes
from provisioningserver.events import AUDIT


class TestLogin(MAASServerTestCase):
    def test_login_GET_returns_not_authenticated(self):
        self.client.handler.enforce_csrf_checks = True
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(
            json_load_bytes(response.content),
            {
                "authenticated": False,
                "external_auth_url": None,
                "no_users": True,
            },
        )

    def test_login_GET_returns_not_authenticated_with_users(self):
        factory.make_User()
        self.client.handler.enforce_csrf_checks = True
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(
            json_load_bytes(response.content),
            {
                "authenticated": False,
                "external_auth_url": None,
                "no_users": False,
            },
        )

    def test_login_GET_returns_authenticated(self):
        password = factory.make_string()
        user = factory.make_User(password=password)
        self.client.handler.enforce_csrf_checks = True
        self.client.login(username=user.username, password=password)
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(
            json_load_bytes(response.content),
            {
                "authenticated": True,
                "external_auth_url": None,
                "no_users": False,
            },
        )

    def test_login_GET_returns_external_auth_url(self):
        auth_url = "http://candid.example.com"
        SecretManager().set_composite_secret(
            "external-auth", {"url": auth_url}
        )
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(
            json_load_bytes(response.content),
            {
                "authenticated": False,
                "external_auth_url": auth_url,
                "no_users": True,
            },
        )

    def test_login_returns_204_when_already_authenticated(self):
        password = factory.make_string()
        user = factory.make_User(password=password)
        self.client.handler.enforce_csrf_checks = True
        self.client.login(username=user.username, password=password)
        response = self.client.post(reverse("login"))
        self.assertEqual(response.status_code, http.client.NO_CONTENT)

    def test_login_returns_204_on_authentication(self):
        password = factory.make_string()
        user = factory.make_User(password=password)
        self.client.handler.enforce_csrf_checks = True
        response = self.client.post(
            reverse("login"), {"username": user.username, "password": password}
        )
        self.assertEqual(response.status_code, http.client.NO_CONTENT)
        self.assertEqual(response.cookies.keys(), {"csrftoken", "sessionid"})

    def test_login_returns_400_on_bad_authentication(self):
        password = factory.make_string()
        factory.make_User(password=password)
        self.client.handler.enforce_csrf_checks = True
        response = self.client.post(
            reverse("login"),
            {
                "username": factory.make_name("username"),
                "password": factory.make_name("password"),
            },
        )
        self.assertEqual(response.status_code, http.client.BAD_REQUEST)

    def test_login_creates_audit_event(self):
        password = factory.make_string()
        user = factory.make_User(password=password)
        self.client.post(
            reverse("login"), {"username": user.username, "password": password}
        )
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(event.description, "Logged in user.")


class TestLogout(MAASServerTestCase):
    def test_logout_returns_204(self):
        password = factory.make_string()
        user = factory.make_User(password=password)
        self.client.handler.enforce_csrf_checks = True
        self.client.login(username=user.username, password=password)
        self.client.handler.enforce_csrf_checks = False
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, http.client.NO_CONTENT)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_logout_GET_returns_405(self):
        password = factory.make_string()
        user = factory.make_User(password=password)
        self.client.handler.enforce_csrf_checks = True
        self.client.login(username=user.username, password=password)
        self.client.handler.enforce_csrf_checks = False
        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, http.client.METHOD_NOT_ALLOWED)

    def test_logout_creates_audit_event(self):
        password = factory.make_string()
        user = factory.make_User(password=password)
        self.client.handler.enforce_csrf_checks = True
        self.client.login(username=user.username, password=password)
        self.client.handler.enforce_csrf_checks = False
        self.client.post(reverse("logout"))
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(event.description, "Logged out user.")


def token_to_dict(token):
    return {
        "token_key": token.key,
        "token_secret": token.secret,
        "consumer_key": token.consumer.key,
        "name": token.consumer.name,
    }


class TestAuthenticate(MAASServerTestCase):
    """Tests for the `authenticate` view."""

    def test_returns_existing_credentials(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        user = factory.make_User(username, password)
        [token] = get_auth_tokens(user)
        response = self.client.post(
            reverse("authenticate"),
            data={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(
            token_to_dict(token), json_load_bytes(response.content)
        )

    def test_returns_first_of_existing_credentials(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        user = factory.make_User(username, password)
        [token] = get_auth_tokens(user)
        for i in range(1, 6):
            create_auth_token(user, "Token #%d" % i)
        response = self.client.post(
            reverse("authenticate"),
            data={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(
            token_to_dict(token), json_load_bytes(response.content)
        )

    def test_returns_existing_named_credentials(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        consumer = factory.make_name("consumer")
        user = factory.make_User(username, password)
        token = create_auth_token(user, consumer)
        response = self.client.post(
            reverse("authenticate"),
            data={
                "username": username,
                "password": password,
                "consumer": consumer,
            },
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            token_to_dict(token), json_load_bytes(response.content)
        )

    def test_returns_first_of_existing_named_credentials(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        consumer = factory.make_name("consumer")
        user = factory.make_User(username, password)
        tokens = [create_auth_token(user, consumer) for _ in range(1, 6)]
        response = self.client.post(
            reverse("authenticate"),
            data={
                "username": username,
                "password": password,
                "consumer": consumer,
            },
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            token_to_dict(tokens[0]), json_load_bytes(response.content)
        )

    def test_returns_new_credentials(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        user = factory.make_User(username, password)
        get_auth_tokens(user).delete()  # Delete all tokens.
        response = self.client.post(
            reverse("authenticate"),
            data={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        [token] = get_auth_tokens(user)
        self.assertEqual(
            token_to_dict(token), json_load_bytes(response.content)
        )

    def test_returns_new_named_credentials(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        consumer = factory.make_name("consumer")
        user = factory.make_User(username, password)
        get_auth_tokens(user).delete()  # Delete all tokens.
        response = self.client.post(
            reverse("authenticate"),
            data={
                "username": username,
                "password": password,
                "consumer": consumer,
            },
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            json_load_bytes(response.content).get("name"), consumer
        )

    def test_rejects_unknown_username(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        response = self.client.post(
            reverse("authenticate"),
            data={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_rejects_incorrect_password(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        factory.make_User(username, password)
        response = self.client.post(
            reverse("authenticate"),
            data={"username": username, "password": password + "-garbage"},
        )
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_rejects_inactive_user(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        user = factory.make_User(username, password)
        user.is_active = False
        user.save()
        response = self.client.post(
            reverse("authenticate"),
            data={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_rejects_GET(self):
        response = self.client.get(reverse("authenticate"))
        self.assertEqual(response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)
        self.assertEqual("POST", response["Allow"])

    def test_authenticate_creates_audit_event_with_tokens(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        user = factory.make_User(username, password)
        user.save()
        self.client.post(
            reverse("authenticate"),
            data={"username": username, "password": password},
        )
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(event.description, "Retrieved API (OAuth) token.")

    def test_authenticate_creates_audit_event_without_tokens(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        consumer = factory.make_name("consumer")
        user = factory.make_User(username, password)
        user.save()
        self.client.post(
            reverse("authenticate"),
            data={
                "username": username,
                "password": password,
                "consumer": consumer,
            },
        )
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(event.description, "Created API (OAuth) token.")


class TestCSRF(MAASServerTestCase):
    def test_method_not_allowed_on_get(self):
        response = self.client.get(reverse("csrf"))
        self.assertEqual(response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)

    def test_method_not_allowed_on_put(self):
        response = self.client.put(reverse("csrf"))
        self.assertEqual(response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)

    def test_method_not_allowed_on_delete(self):
        response = self.client.delete(reverse("csrf"))
        self.assertEqual(response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)

    def test_forbidden_when_not_authenticated(self):
        response = self.client.post(reverse("csrf"))
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_returns_csrf(self):
        # Force the client to test for CSRF because the view should be CSRF
        # exempt. If not exempt then the `client.post` would fail.
        self.client.handler.enforce_csrf_checks = True
        self.client.login(user=factory.make_User())
        response = self.client.post(reverse("csrf"))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        body = json_load_bytes(response.content)
        self.assertIn("csrf", body)
        # Should not have an updated CSRF cookie, because it was marked as
        # not used.
        self.assertIsNone(response.cookies.get(settings.CSRF_COOKIE_NAME))
