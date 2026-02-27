# Copyright 2017-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the behaviour of user signals."""

from django.db import connection

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestUserUsername(MAASServerTestCase):
    """Test that event's `username` is set when the user is
    going to be deleted."""

    def test_deleting_user_updates_event_username(self):
        user = factory.make_admin()
        username = user.username
        events = [factory.make_Event(user=user) for _ in range(3)]
        user.delete()
        for event in events:
            self.assertEqual(event.username, username)


class TestPostSaveUserSignal(MAASServerTestCase):
    scenarios = (
        ("user", {"user_factory": factory.make_User}),
        ("admin", {"user_factory": factory.make_admin}),
    )

    def test_save_creates_openfga_tuple(self):
        user = self.user_factory()

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT object_type, object_id, relation FROM openfga.tuple WHERE _user = 'user:%s'",
                [user.id],
            )
            openfga_tuple = cursor.fetchone()

        self.assertEqual("group", openfga_tuple[0])
        self.assertEqual(
            "administrators" if user.is_superuser else "users",
            openfga_tuple[1],
        )
        self.assertEqual("member", openfga_tuple[2])


class TestPostDeleteUserSignal(MAASServerTestCase):
    def test_delete_removes_openfga_tuple(self):
        user = factory.make_User()
        user_id = user.id

        user.delete()

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT object_type, object_id, relation FROM openfga.tuple WHERE _user = 'user:%s'",
                [user_id],
            )
            openfga_tuple = cursor.fetchone()

        self.assertIsNone(openfga_tuple)
