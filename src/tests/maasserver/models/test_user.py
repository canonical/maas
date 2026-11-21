# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import sentinel

from django.contrib.auth.models import User
from django.db import IntegrityError
from piston3.models import KEY_SIZE, SECRET_SIZE

from apiclient.creds import convert_string_to_tuple, convert_tuple_to_string
from maasserver import models
from maasserver.models.user import (
    create_auth_token,
    get_auth_tokens,
    get_creds_tuple,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestUser(MAASServerTestCase):
    def test_user_email_null(self):
        user = User.objects.create_user(username=factory.make_string())
        self.assertIsNone(user.email)

    def test_user_email_blank(self):
        user = User.objects.create_user(
            username=factory.make_string(), email=""
        )
        self.assertIsNone(user.email)

    def test_user_email_unique(self):
        email = factory.make_email()
        User.objects.create_user(username=factory.make_string(), email=email)
        self.assertRaises(
            IntegrityError,
            User.objects.create_user,
            username=factory.make_string(),
            email=email,
        )

    def test_has_perm_is_patched(self):
        mock_has_perm = self.patch(models, "_user_has_perm")
        user = factory.make_User()
        user.has_perm(sentinel.perm, sentinel.obj)
        mock_has_perm.assert_called_once_with(
            user, sentinel.perm, sentinel.obj
        )


class TestAuthTokens(MAASServerTestCase):
    """Test creation and retrieval of auth tokens."""

    def assertTokenValid(self, token):
        self.assertIsInstance(token.key, str)
        self.assertEqual(KEY_SIZE, len(token.key))
        self.assertIsInstance(token.secret, str)
        self.assertEqual(SECRET_SIZE, len(token.secret))

    def assertConsumerValid(self, consumer):
        self.assertIsInstance(consumer.key, str)
        self.assertEqual(KEY_SIZE, len(consumer.key))
        self.assertEqual("", consumer.secret)

    def test_create_auth_token(self):
        user = factory.make_User()
        token = create_auth_token(user)
        self.assertEqual(user, token.user)
        self.assertEqual(user, token.consumer.user)
        self.assertTrue(token.is_approved)
        self.assertConsumerValid(token.consumer)
        self.assertTokenValid(token)

    def test_get_auth_tokens_finds_tokens_for_user(self):
        user = factory.make_User()
        token = create_auth_token(user)
        self.assertIn(token, get_auth_tokens(user))

    def test_get_auth_tokens_ignores_other_users(self):
        user, other_user = factory.make_User(), factory.make_User()
        unrelated_token = create_auth_token(other_user)
        self.assertNotIn(unrelated_token, get_auth_tokens(user))

    def test_get_auth_tokens_ignores_unapproved_tokens(self):
        user = factory.make_User()
        token = create_auth_token(user)
        token.is_approved = False
        token.save()
        self.assertNotIn(token, get_auth_tokens(user))

    def test_get_creds_tuple_returns_creds(self):
        token = create_auth_token(factory.make_User())
        self.assertEqual(
            (token.consumer.key, token.key, token.secret),
            get_creds_tuple(token),
        )

    def test_get_creds_tuple_integrates_with_api_client(self):
        creds_tuple = get_creds_tuple(create_auth_token(factory.make_User()))
        self.assertEqual(
            creds_tuple,
            convert_string_to_tuple(convert_tuple_to_string(creds_tuple)),
        )
