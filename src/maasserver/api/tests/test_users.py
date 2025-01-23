# Copyright 2013-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the user accounts API."""


import http.client
import json

from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse

from maascommon.events import AUDIT
import maasserver.api.auth
from maasserver.enum import IPADDRESS_TYPE, NODE_STATUS
from maasserver.models import Node, SSHKey, SSLKey, StaticIPAddress
from maasserver.models.event import Event
from maasserver.secrets import SecretManager
from maasserver.testing import get_data
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.orm import get_one


def get_user_uri(user):
    """Return a User URI."""
    return reverse("user_handler", args=[user.username])


class TestUsers(APITestCase.ForUser):
    def setUp(self):
        self.mock_validate = self.patch(
            maasserver.api.auth, "validate_user_external_auth"
        )
        self.mock_validate.return_value = True
        super().setUp()

    def test_handler_path(self):
        self.assertEqual("/MAAS/api/2.0/users/", reverse("users_handler"))

    def test_POST_creates_user(self):
        self.become_admin()
        username = factory.make_name("user")
        email = factory.make_email_address()
        password = factory.make_string()

        response = self.client.post(
            reverse("users_handler"),
            {
                "username": username,
                "email": email,
                "password": password,
                "is_superuser": "0",
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        self.assertEqual(
            username,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "username"
            ],
        )
        created_user = User.objects.get(username=username)
        self.assertEqual(
            (email, False), (created_user.email, created_user.is_superuser)
        )
        self.assertTrue(created_user.userprofile.is_local)

    def test_POST_creates_user_external_auth_not_local(self):
        SecretManager().set_composite_secret(
            "external-auth", {"url": "http://auth.example.com"}
        )
        self.become_admin()
        username = factory.make_name("user")
        email = factory.make_email_address()
        password = factory.make_string()
        self.client.post(
            reverse("users_handler"),
            {
                "username": username,
                "email": email,
                "password": password,
                "is_superuser": "0",
            },
        )
        created_user = User.objects.get(username=username)
        self.assertFalse(created_user.userprofile.is_local)

    def test_POST_creates_admin(self):
        self.become_admin()
        username = factory.make_name("user")
        email = factory.make_email_address()
        password = factory.make_string()

        response = self.client.post(
            reverse("users_handler"),
            {
                "username": username,
                "email": email,
                "password": password,
                "is_superuser": "1",
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        self.assertEqual(
            username,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "username"
            ],
        )
        created_user = User.objects.get(username=username)
        self.assertEqual(
            (email, True), (created_user.email, created_user.is_superuser)
        )

    def test_POST_creates_admin_with_ssh_key(self):
        self.become_admin()
        username = factory.make_name("user")
        email = factory.make_email_address()
        password = factory.make_string()
        key_string = get_data("data/test_rsa0.pub")
        response = self.client.post(
            reverse("users_handler"),
            {
                "username": username,
                "email": email,
                "password": password,
                "is_superuser": "1",
                "key": key_string,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        self.assertEqual(
            username,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "username"
            ],
        )
        created_user = User.objects.get(username=username)
        self.assertEqual(
            (email, True), (created_user.email, created_user.is_superuser)
        )
        added_key = get_one(SSHKey.objects.filter(user=created_user))
        self.assertEqual(key_string, added_key.key)

    def test_POST_requires_admin(self):
        response = self.client.post(
            reverse("users_handler"),
            {
                "username": factory.make_name("user"),
                "email": factory.make_email_address(),
                "password": factory.make_string(),
                "is_superuser": "1" if factory.pick_bool() else "0",
            },
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_POST_creates_audit_event_for_user(self):
        self.become_admin()
        username = factory.make_name("user")
        self.client.post(
            reverse("users_handler"),
            {
                "username": username,
                "email": factory.make_email_address(),
                "password": factory.make_string(),
                "is_superuser": "0",
            },
        )
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(event.description, "Created user '%s'." % username)

    def test_POST_creates_audit_event_for_admin(self):
        self.become_admin()
        username = factory.make_name("user")
        self.client.post(
            reverse("users_handler"),
            {
                "username": username,
                "email": factory.make_email_address(),
                "password": factory.make_string(),
                "is_superuser": "1",
            },
        )
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(event.description, "Created admin '%s'." % username)

    def test_POST_password_required_without_external_auth(self):
        self.become_admin()
        username = factory.make_name("user")
        response = self.client.post(
            reverse("users_handler"),
            {
                "username": username,
                "email": factory.make_email_address(),
                "is_superuser": "0",
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            response.content.decode("utf8"), "No provided password!"
        )

    def test_POST_password_optional_with_external_auth(self):
        SecretManager().set_composite_secret(
            "external-auth", {"url": "http://auth.example.com"}
        )
        self.become_admin()
        username = factory.make_name("user")
        response = self.client.post(
            reverse("users_handler"),
            {
                "username": username,
                "email": factory.make_email_address(),
                "is_superuser": "0",
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        created_user = User.objects.get(username=username)
        self.assertFalse(created_user.has_usable_password())

    def test_GET_lists_users(self):
        users = [factory.make_User() for counter in range(2)]

        response = self.client.get(reverse("users_handler"))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        listing = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertGreater(
            {user["username"] for user in listing},
            {user.username for user in users},
        )

    def test_whoami_returns_user(self):
        factory.make_User()
        response = self.client.get(reverse("users_handler"), {"op": "whoami"})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(self.user.username, result["username"])

    def test_whoami_returns_forbidden_if_not_logged_in(self):
        self.client.logout()
        factory.make_User()
        response = self.client.get(reverse("users_handler"), {"op": "whoami"})
        self.assertEqual(
            http.client.UNAUTHORIZED, response.status_code, response.content
        )

    def test_GET_orders_by_name(self):
        # Create some users.  Give them lower-case names, because collation
        # algorithms may differ on how mixed-case names should be sorted.
        # The implementation may sort in the database or in Python code, and
        # the two may use different collations.
        users = [factory.make_name("user").lower() for counter in range(5)]
        for user in users:
            factory.make_User(username=user)

        response = self.client.get(reverse("users_handler"))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        listing = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        # The listing may also contain built-in users and/or a test user.
        # Restrict it to the users we created ourselves.
        users_as_returned = [
            user["username"] for user in listing if user["username"] in users
        ]
        self.assertEqual(sorted(users), users_as_returned)


class TestUser(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/users/username/",
            reverse("user_handler", args=["username"]),
        )

    def test_GET_finds_user(self):
        user = factory.make_User()

        response = self.client.get(
            reverse("user_handler", args=[user.username])
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        returned_user = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(user.username, returned_user["username"])
        self.assertEqual(user.email, returned_user["email"])
        self.assertFalse(returned_user["is_superuser"])
        self.assertTrue(returned_user["is_local"])
        self.assertEqual(get_user_uri(user), returned_user["resource_uri"])

    def test_GET_shows_expected_fields(self):
        user = factory.make_User()

        response = self.client.get(
            reverse("user_handler", args=[user.username])
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        returned_user = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            {"username", "email", "resource_uri", "is_superuser", "is_local"},
            returned_user.keys(),
        )

    def test_GET_identifies_superuser_as_such(self):
        user = factory.make_admin()

        response = self.client.get(
            reverse("user_handler", args=[user.username])
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        self.assertTrue(
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "is_superuser"
            ]
        )

    def test_GET_identifies_non_local_user_as_such(self):
        user = factory.make_User(is_local=False)
        response = self.client.get(
            reverse("user_handler", args=[user.username])
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertFalse(
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "is_local"
            ]
        )

    def test_GET_returns_404_if_user_not_found(self):
        nonuser = factory.make_name("nonuser")
        response = self.client.get(reverse("user_handler", args=[nonuser]))
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.status_code
        )
        self.assertCountEqual([], User.objects.filter(username=nonuser))

    def test_DELETE_requires_admin_privileges(self):
        user = factory.make_User()
        response = self.client.delete(
            reverse("user_handler", args=[user.username])
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.status_code
        )
        self.assertTrue(User.objects.filter(username=user.username).exists())

    def test_DELETE_requires_admin_privileges_with_invalid_user(self):
        """If the user has no admin privileges, it doesn't matter if the user
        being deleted exists or not, we will return a 403."""
        nonuser = factory.make_name("nonuser")
        response = self.client.delete(reverse("user_handler", args=[nonuser]))
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.status_code
        )

    def test_DELETE_keeps_quiet_if_user_not_found(self):
        self.become_admin()
        nonuser = factory.make_name("nonuser")
        response = self.client.delete(reverse("user_handler", args=[nonuser]))
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.status_code
        )

    def test_DELETE_admin_cannot_delete_self(self):
        self.become_admin()
        user = self.user
        response = self.client.delete(
            reverse("user_handler", args=[user.username])
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.status_code
        )
        self.assertTrue(User.objects.filter(username=user.username).exists())
        self.assertIn(b"cannot self-delete", response.content)

    def test_DELETE_deletes_user(self):
        self.become_admin()
        user = factory.make_User()
        response = self.client.delete(
            reverse("user_handler", args=[user.username])
        )
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.status_code
        )
        self.assertCountEqual([], User.objects.filter(username=user.username))

    def test_DELETE_deletes_admin(self):
        self.become_admin()
        user = factory.make_admin()
        response = self.client.delete(
            reverse("user_handler", args=[user.username])
        )
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.status_code
        )
        self.assertCountEqual([], User.objects.filter(username=user.username))

    def test_DELETE_user_with_node_fails(self):
        self.become_admin()
        user = factory.make_User()
        factory.make_Node(owner=user, status=NODE_STATUS.DEPLOYED)
        response = self.client.delete(
            reverse("user_handler", args=[user.username])
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.status_code
        )
        self.assertIn(b"1 node(s) are still allocated", response.content)

    def test_DELETE_user_with_node_and_transfer(self):
        self.become_admin()
        user = factory.make_User()
        new_owner = factory.make_User()
        node = factory.make_Node(owner=user, status=NODE_STATUS.DEPLOYED)
        response = self.client.delete(
            reverse("user_handler", args=[user.username]),
            query={"transfer_resources_to": new_owner.username},
        )
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.status_code
        )
        self.assertCountEqual([], User.objects.filter(username=user.username))
        self.assertEqual(Node.objects.get(owner=new_owner), node)

    def test_DELETE_user_with_staticaddress_fails(self):
        self.become_admin()
        user = factory.make_User()
        factory.make_StaticIPAddress(
            user=user, alloc_type=IPADDRESS_TYPE.USER_RESERVED
        )
        response = self.client.delete(
            reverse("user_handler", args=[user.username])
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.status_code
        )
        self.assertIn(
            b"1 static IP address(es) are still allocated", response.content
        )

    def test_DELETE_user_with_iprange_fails(self):
        self.become_admin()
        user = factory.make_User()
        factory.make_IPRange(user=user)
        response = self.client.delete(
            reverse("user_handler", args=[user.username])
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.status_code
        )
        self.assertIn(b"1 IP range(s) are still allocated", response.content)

    def test_DELETE_user_with_staticaddress_and_transfer(self):
        self.become_admin()
        user = factory.make_User()
        new_owner = factory.make_User()
        ip_address = factory.make_StaticIPAddress(
            user=user, alloc_type=IPADDRESS_TYPE.USER_RESERVED
        )
        response = self.client.delete(
            reverse("user_handler", args=[user.username]),
            query={"transfer_resources_to": new_owner.username},
        )
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.status_code
        )
        self.assertCountEqual([], User.objects.filter(username=user.username))
        self.assertEqual(
            StaticIPAddress.objects.get(user=new_owner), ip_address
        )

    def test_DELETE_user_with_transfer_unknown_user(self):
        self.become_admin()
        user = factory.make_User()
        factory.make_Node(owner=user, status=NODE_STATUS.DEPLOYED)
        response = self.client.delete(
            reverse("user_handler", args=[user.username]),
            query={"transfer_resources_to": "unknown-user"},
        )
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.status_code
        )
        self.assertEqual(user, User.objects.get(username=user.username))

    def test_DELETE_user_with_sslkey_deletes_key(self):
        self.become_admin()
        user = factory.make_User()
        key_id = factory.make_SSLKey(user=user).id
        response = self.client.delete(
            reverse("user_handler", args=[user.username])
        )
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.status_code
        )
        self.assertFalse(SSLKey.objects.filter(id=key_id).exists())

    def test_DELETE_user_with_sshkey_deletes_key(self):
        self.become_admin()
        user = factory.make_User()
        key_id = factory.make_SSHKey(user=user).id
        response = self.client.delete(
            reverse("user_handler", args=[user.username])
        )
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.status_code
        )
        self.assertFalse(SSHKey.objects.filter(id=key_id).exists())

    def test_DELETE_user_creates_audit_event(self):
        self.become_admin()
        user = factory.make_User()
        self.client.delete(reverse("user_handler", args=[user.username]))
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description, "Deleted user '%s'." % user.username
        )

    def test_DELETE_admin_creates_audit_event(self):
        self.become_admin()
        user = factory.make_admin()
        self.client.delete(reverse("user_handler", args=[user.username]))
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description, "Deleted admin '%s'." % user.username
        )
