# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.user`"""

__all__ = []

from django.contrib.auth.models import User
from maasserver.models.user import SYSTEM_USERS
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import HandlerDoesNotExistError
from maasserver.websockets.handlers.user import UserHandler


class TestUserHandler(MAASServerTestCase):

    def dehydrate_user(self, user, sshkeys_count=0):
        data = {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "is_superuser": user.is_superuser,
            "sshkeys_count": sshkeys_count,
        }
        return data

    def test_get_for_admin(self):
        user = factory.make_User()
        admin = factory.make_admin()
        handler = UserHandler(admin, {})
        self.assertEqual(
            self.dehydrate_user(user),
            handler.get({"id": user.id}))

    def test_get_for_user_getting_self(self):
        user = factory.make_User()
        handler = UserHandler(user, {})
        self.assertEqual(
            self.dehydrate_user(user),
            handler.get({"id": user.id}))

    def test_get_for_user_not_getting_self(self):
        user = factory.make_User()
        other_user = factory.make_User()
        handler = UserHandler(user, {})
        self.assertRaises(
            HandlerDoesNotExistError, handler.get, {"id": other_user.id})

    def test_list_for_admin(self):
        admin = factory.make_admin()
        handler = UserHandler(admin, {})
        factory.make_User()
        expected_users = [
            self.dehydrate_user(user)
            for user in User.objects.exclude(username__in=SYSTEM_USERS)
        ]
        self.assertItemsEqual(
            expected_users,
            handler.list({}))

    def test_list_for_standard_user(self):
        user = factory.make_User()
        handler = UserHandler(user, {})
        # Other users
        for _ in range(3):
            factory.make_User()
        self.assertItemsEqual(
            [self.dehydrate_user(user)],
            handler.list({}))

    def test_auth_user(self):
        user = factory.make_User()
        handler = UserHandler(user, {})
        self.assertEqual(
            self.dehydrate_user(user),
            handler.auth_user({}))
