# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver account views."""

__all__ = []

from http import HTTPStatus
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
from maasserver.models.user import (
    create_auth_token,
    get_auth_tokens,
)
from maasserver.testing import (
    extract_redirect,
    get_content_links,
)
from maasserver.testing.factory import factory
from maasserver.testing.matchers import HasStatusCode
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import json_load_bytes
from testtools.matchers import (
    ContainsDict,
    Equals,
)


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


def token_to_dict(token):
    return {
        "token_key": token.key,
        "token_secret": token.secret,
        "consumer_key": token.consumer.key,
        "name": token.consumer.name,
    }


class TestAuthenticate(MAASServerTestCase):
    """Tests for the `authenticate` view."""

    def test__returns_existing_credentials(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        user = factory.make_User(username, password)
        [token] = get_auth_tokens(user)
        response = self.client.post(
            reverse("authenticate"), data={
                "username": username,
                "password": password,
            })
        self.assertThat(response, HasStatusCode(HTTPStatus.OK))
        self.assertThat(
            json_load_bytes(response.content),
            Equals(token_to_dict(token)))

    def test__returns_first_of_existing_credentials(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        user = factory.make_User(username, password)
        [token] = get_auth_tokens(user)
        for i in range(1, 6):
            create_auth_token(user, "Token #%d" % i)
        response = self.client.post(
            reverse("authenticate"), data={
                "username": username,
                "password": password,
            })
        self.assertThat(response, HasStatusCode(HTTPStatus.OK))
        self.assertThat(
            json_load_bytes(response.content),
            Equals(token_to_dict(token)))

    def test__returns_existing_named_credentials(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        consumer = factory.make_name("consumer")
        user = factory.make_User(username, password)
        token = create_auth_token(user, consumer)
        response = self.client.post(
            reverse("authenticate"), data={
                "username": username,
                "password": password,
                "consumer": consumer,
            })
        self.assertThat(response, HasStatusCode(HTTPStatus.OK))
        self.assertThat(
            json_load_bytes(response.content),
            Equals(token_to_dict(token)))

    def test__returns_first_of_existing_named_credentials(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        consumer = factory.make_name("consumer")
        user = factory.make_User(username, password)
        tokens = [create_auth_token(user, consumer) for _ in range(1, 6)]
        response = self.client.post(
            reverse("authenticate"), data={
                "username": username,
                "password": password,
                "consumer": consumer,
            })
        self.assertThat(response, HasStatusCode(HTTPStatus.OK))
        self.assertThat(
            json_load_bytes(response.content),
            Equals(token_to_dict(tokens[0])))

    def test__returns_new_credentials(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        user = factory.make_User(username, password)
        get_auth_tokens(user).delete()  # Delete all tokens.
        response = self.client.post(
            reverse("authenticate"), data={
                "username": username,
                "password": password,
            })
        self.assertThat(response, HasStatusCode(HTTPStatus.OK))
        [token] = get_auth_tokens(user)
        self.assertThat(
            json_load_bytes(response.content),
            Equals(token_to_dict(token)))

    def test__returns_new_named_credentials(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        consumer = factory.make_name("consumer")
        user = factory.make_User(username, password)
        get_auth_tokens(user).delete()  # Delete all tokens.
        response = self.client.post(
            reverse("authenticate"), data={
                "username": username,
                "password": password,
                "consumer": consumer,
            })
        self.assertThat(response, HasStatusCode(HTTPStatus.OK))
        self.assertThat(
            json_load_bytes(response.content),
            ContainsDict({"name": Equals(consumer)}))

    def test__rejects_unknown_username(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        response = self.client.post(
            reverse("authenticate"), data={
                "username": username,
                "password": password,
            })
        self.assertThat(response, HasStatusCode(HTTPStatus.FORBIDDEN))

    def test__rejects_incorrect_password(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        factory.make_User(username, password)
        response = self.client.post(
            reverse("authenticate"), data={
                "username": username,
                "password": password + "-garbage",
            })
        self.assertThat(response, HasStatusCode(HTTPStatus.FORBIDDEN))

    def test__rejects_inactive_user(self):
        username = factory.make_name("username")
        password = factory.make_name("password")
        user = factory.make_User(username, password)
        user.is_active = False
        user.save()
        response = self.client.post(
            reverse("authenticate"), data={
                "username": username,
                "password": password,
            })
        self.assertThat(response, HasStatusCode(HTTPStatus.FORBIDDEN))

    def test__rejects_GET(self):
        response = self.client.get(reverse("authenticate"))
        self.assertThat(response, HasStatusCode(HTTPStatus.METHOD_NOT_ALLOWED))
        self.assertThat(response["Allow"], Equals("POST"))
