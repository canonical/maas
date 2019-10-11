# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.user`"""

__all__ = []

import datetime

from django.contrib.auth.models import User
from maasserver.models.event import Event
from maasserver.models.user import SYSTEM_USERS
from maasserver.permissions import (
    NodePermission,
    PodPermission,
    ResourcePoolPermission,
)
from maasserver.testing.factory import factory
from maasserver.testing.fixtures import RBACForceOffFixture
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.views.tests.test_settings import (
    make_password_params,
    make_user_attribute_params,
    subset_dict,
    user_attributes,
)
from maasserver.websockets.base import (
    DATETIME_FORMAT,
    dehydrate_datetime,
    HandlerDoesNotExistError,
    HandlerPermissionError,
    HandlerValidationError,
)
from maasserver.websockets.handlers.user import UserHandler
from maastesting.djangotestcase import count_queries
from piston3.models import Token
from provisioningserver.events import AUDIT
from testtools.testcase import TestCase


class TestUserHandler(MAASServerTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # testtools' assertRaises predates unittest's which has
        # support for context-manager
        self.assertRaises = super(TestCase, self).assertRaises

    def dehydrate_user(self, user, sshkeys_count=0, for_self=False):
        data = {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "is_superuser": user.is_superuser,
            "sshkeys_count": sshkeys_count,
            "last_login": dehydrate_datetime(user.last_login),
            "is_local": user.userprofile.is_local,
            "completed_intro": user.userprofile.completed_intro,
            "machines_count": user.node_set.count(),
        }
        if for_self:
            permissions = []
            if user.has_perm(NodePermission.admin):
                permissions.append("machine_create")
            if user.has_perm(NodePermission.view):
                permissions.append("device_create")
            if user.has_perm(ResourcePoolPermission.create):
                permissions.append("resource_pool_create")
            if user.has_perm(ResourcePoolPermission.delete):
                permissions.append("resource_pool_delete")
            if user.has_perm(PodPermission.create):
                permissions.append("pod_create")
            data["global_permissions"] = permissions
        return data

    def test_get_for_admin(self):
        user = factory.make_User()
        admin = factory.make_admin()
        handler = UserHandler(admin, {}, None)
        self.assertEqual(
            self.dehydrate_user(user), handler.get({"id": user.id})
        )

    def test_get_for_user_getting_self(self):
        user = factory.make_User()
        handler = UserHandler(user, {}, None)
        self.assertEqual(
            self.dehydrate_user(user, for_self=True),
            handler.get({"id": user.id}),
        )

    def test_get_for_user_not_getting_self(self):
        user = factory.make_User()
        other_user = factory.make_User()
        handler = UserHandler(user, {}, None)
        self.assertRaises(
            HandlerDoesNotExistError, handler.get, {"id": other_user.id}
        )

    def test_list_for_admin(self):
        admin = factory.make_admin()
        handler = UserHandler(admin, {}, None)
        factory.make_User()
        expected_users = [
            self.dehydrate_user(user, for_self=(user == admin))
            for user in User.objects.exclude(username__in=SYSTEM_USERS)
        ]
        self.assertItemsEqual(expected_users, handler.list({}))

    def test_list_num_queries_is_the_expected_number(self):
        # Prevent RBAC from making a query.
        self.useFixture(RBACForceOffFixture())

        admin = factory.make_admin()
        handler = UserHandler(admin, {}, None)
        for _ in range(3):
            factory.make_User()
        queries_one, _ = count_queries(handler.list, {"limit": 1})
        queries_total, _ = count_queries(handler.list, {})
        # This check is to notify the developer that a change was made that
        # affects the number of queries performed when doing a user listing.
        # It is important to keep this number as low as possible. A larger
        # number means regiond has to do more work slowing down its process
        # and slowing down the client waiting for the response.
        self.assertEqual(
            queries_one,
            1,
            "Number of queries has changed; make sure this is expected.",
        )
        self.assertEqual(
            queries_total,
            1,
            "Number of queries has changed; make sure this is expected.",
        )

    def test_list_for_standard_user(self):
        user = factory.make_User()
        handler = UserHandler(user, {}, None)
        # Other users
        for _ in range(3):
            factory.make_User()
        self.assertItemsEqual(
            [self.dehydrate_user(user, for_self=True)], handler.list({})
        )

    def test_auth_user(self):
        user = factory.make_User()
        handler = UserHandler(user, {}, None)
        self.assertEqual(
            self.dehydrate_user(user, for_self=True), handler.auth_user({})
        )

    def test_create_authorisation_token(self):
        user = factory.make_User()
        handler = UserHandler(user, {}, None)
        observed = handler.create_authorisation_token({})
        self.assertItemsEqual(["key", "secret", "consumer"], observed.keys())
        self.assertItemsEqual(["key", "name"], observed["consumer"].keys())
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(event.description, "Created token.")

    def test_update_token_name(self):
        user = factory.make_User()
        handler = UserHandler(user, {}, None)
        new_token_name = factory.make_string()
        observed = handler.create_authorisation_token({})
        handler.update_token_name(
            {"key": observed["key"], "name": new_token_name}
        )
        auth_token = user.userprofile.get_authorisation_tokens().get(
            key=observed["key"]
        )
        self.assertEqual(auth_token.consumer.name, new_token_name)
        event = (
            Event.objects.filter(type__level=AUDIT)
            .order_by("-created")
            .first()
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.description, "Modified consumer name of token.")

    def test_delete_authorisation_token(self):
        user = factory.make_User()
        handler = UserHandler(user, {}, None)
        observed = handler.create_authorisation_token({})
        handler.delete_authorisation_token({"key": observed["key"]})
        self.assertIsNone(Token.objects.filter(key=observed["key"]).first())
        event = Event.objects.filter(type__level=AUDIT).last()
        self.assertIsNotNone(event)
        self.assertEqual(event.description, "Deleted token.")

    def test_create_as_unprivileged(self):
        unpriv_user = factory.make_User()
        handler = UserHandler(unpriv_user, {}, None)

        params = {
            "username": factory.make_string(),
            "last_name": factory.make_string(30),
            "email": factory.make_email_address(),
            "is_superuser": factory.pick_bool(),
        }
        password = factory.make_string()
        params.update(make_password_params(password))

        with self.assertRaises(HandlerPermissionError):
            handler.create(params)

    def test_create_as_admin(self):
        admin_user = factory.make_admin()
        handler = UserHandler(admin_user, {}, None)

        params = {
            "username": factory.make_string(),
            "last_name": factory.make_string(30),
            "email": factory.make_email_address(),
            "is_superuser": factory.pick_bool(),
        }
        password = factory.make_string()
        params.update(make_password_params(password))

        handler.create(params)

        user = User.objects.get(username=params["username"])
        self.assertAttributes(user, subset_dict(params, user_attributes))
        self.assertTrue(user.check_password(password))
        self.assertTrue(user.userprofile.is_local)

    def test_create_as_admin_event_log(self):
        admin_user = factory.make_admin()
        handler = UserHandler(admin_user, {}, None)
        params = {
            "username": factory.make_string(),
            "last_name": factory.make_string(30),
            "email": factory.make_email_address(),
            "is_superuser": False,
        }
        password = factory.make_string()
        params.update(make_password_params(password))

        handler.create(params)

        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description, "Created user '{username}'.".format(**params)
        )

    def test_delete_as_unprivileged(self):
        unpriv_user = factory.make_User()
        handler = UserHandler(unpriv_user, {}, None)
        user = factory.make_User()

        with self.assertRaises(HandlerPermissionError):
            handler.delete({"id": user.id})

    def test_delete_as_admin(self):
        admin_user = factory.make_admin()
        handler = UserHandler(admin_user, {}, None)
        user = factory.make_User()

        handler.delete({"id": user.id})

        self.assertItemsEqual([], User.objects.filter(id=user.id))

    def test_delete_as_admin_event_log(self):
        admin_user = factory.make_admin()
        handler = UserHandler(admin_user, {}, None)
        user = factory.make_User()

        handler.delete({"id": user.id})

        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description, "Deleted user '{}'.".format(user.username)
        )

    def test_update_other_as_unprivileged(self):
        unpriv_user = factory.make_User()
        handler = UserHandler(unpriv_user, {}, None)
        user = factory.make_User()
        params = make_user_attribute_params(user)
        params.update(
            {
                "id": user.id,
                "last_name": factory.make_name("Newname"),
                "email": "new-{}@example.com".format(factory.make_string()),
                "is_superuser": True,
                "username": factory.make_name("newname"),
            }
        )

        with self.assertRaises(HandlerPermissionError):
            handler.update(params)

    def test_update_self_as_unprivileged(self):
        user = factory.make_User()
        handler = UserHandler(user, {}, None)
        params = make_user_attribute_params(user)
        params.update(
            {
                "id": user.id,
                "last_name": factory.make_name("Newname"),
                "email": "new-{}@example.com".format(factory.make_string()),
                "is_superuser": True,
                "username": factory.make_name("newname"),
            }
        )

        handler.update(params)
        self.assertAttributes(
            reload_object(user), subset_dict(params, user_attributes)
        )

    def test_update_other_as_admin(self):
        admin_user = factory.make_admin()
        handler = UserHandler(admin_user, {}, None)
        user = factory.make_User()
        params = make_user_attribute_params(user)
        params.update(
            {
                "id": user.id,
                "last_name": factory.make_name("Newname"),
                "email": "new-{}@example.com".format(factory.make_string()),
                "is_superuser": True,
                "username": factory.make_name("newname"),
            }
        )

        handler.update(params)

        self.assertAttributes(
            reload_object(user), subset_dict(params, user_attributes)
        )

    def test_update_as_admin_event_log(self):
        admin_user = factory.make_admin()
        handler = UserHandler(admin_user, {}, None)
        user = factory.make_User()
        params = make_user_attribute_params(user)
        params.update(
            {
                "id": user.id,
                "last_name": factory.make_name("Newname"),
                "email": "new-{}@example.com".format(factory.make_string()),
                "is_superuser": True,
                "username": factory.make_name("newname"),
            }
        )

        handler.update(params)

        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description,
            (
                "Updated user profile (username: {username}, "
                "full name: {last_name}, "
                "email: {email}, administrator: True)"
            ).format(**params),
        )

    def test_last_login(self):
        user = factory.make_User()
        now = datetime.datetime.utcnow()
        user.last_login = now
        user.save()
        handler = UserHandler(user, {}, None)
        last_login_serialised = handler.get({"id": user.id})["last_login"]
        self.assertEqual(last_login_serialised, now.strftime(DATETIME_FORMAT))

    def test_change_password_invalid(self):
        user = factory.make_User()
        user.set_password("oldpassword")
        handler = UserHandler(user, {}, None)
        self.assertRaises(
            HandlerValidationError,
            handler.change_password,
            {
                "new_password1": "newpassword",
                "new_password2": "mismatchpassword",
                "old_password": "oldpassword",
            },
        )

    def test_change_password(self):
        user = factory.make_User()
        user.set_password("oldpassword")
        handler = UserHandler(user, {}, None)
        observed = handler.change_password(
            {
                "new_password1": "newpassword",
                "new_password2": "newpassword",
                "old_password": "oldpassword",
            }
        )
        self.assertEqual(self.dehydrate_user(user, for_self=True), observed)
        self.assertTrue(user.check_password("newpassword"))
